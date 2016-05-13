from os import environ
from os.path import abspath, dirname, join, isfile
import logging
from cloudcompose.exceptions import CloudComposeException
from cloudcompose.util import require_env_var
import boto3
import botocore
from time import sleep
import time, datetime
from retrying import retry
from pprint import pprint
import sys

class CloudController:
    def __init__(self, cloud_config):
        logging.basicConfig(level=logging.ERROR)
        self.logger = logging.getLogger(__name__)
        self.cloud_config = cloud_config
        self.config_data = cloud_config.config_data('image')
        self.aws = self.config_data['aws']
        self.image_name = self.config_data['name']
        self.image_version = self.config_data['version']
        self.ec2 = self._get_ec2_client()
        self.polling_interval = 20

    def _get_ec2_client(self):
        return boto3.client('ec2', aws_access_key_id=require_env_var('AWS_ACCESS_KEY_ID'),
                            aws_secret_access_key=require_env_var('AWS_SECRET_ACCESS_KEY'),
                            region_name=environ.get('AWS_REGION', 'us-east-1'))

    def up(self, cloud_init=None):
        self._remove_unused_images()
        instance_id = self._create_instance(cloud_init)
        self._wait_for_instance_stop(instance_id)
        self._create_image(instance_id)
        self._terminate_instance(instance_id)

    def down(self):
        filters = [
            {'Name': 'tag:ImageName', 'Values': [self.image_name] },
            {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
        ]
        instance_ids = self._instance_ids_from_filters(filters)
        if len(instance_ids) > 0:
            self._ec2_terminate_instances(InstanceIds=instance_ids)
            print 'terminated %s' % ','.join(instance_ids)

    def _instance_ids_from_filters(self, filters):
        instance_ids = []
        instances = self._ec2_describe_instances(Filters=filters)
        for reservation in instances.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                if 'InstanceId' in instance:
                    instance_ids.append(instance['InstanceId'])

        return instance_ids

    def _create_instance(self, cloud_init):
        instance = None
        kwargs = self._create_instance_args()
        kwargs['SubnetId'] = self.aws["subnet"]

        if cloud_init:
            cloud_init_script = cloud_init.build(self.config_data)
            kwargs['UserData'] = cloud_init_script + '\nshutdown -h now'
        else:
            kwargs['UserData'] = '#!/bin/bash\nshutdown -h now'

        max_retries = 6
        retries = 0
        while retries < max_retries:
            retries += 1
            try:
                response = self._ec2_run_instances(**kwargs)
                if response:
                    instance = response['Instances'][0]
                break
            except botocore.exceptions.ClientError as ex:
                print(ex.response["Error"]["Message"])

        instance_id = instance['InstanceId']
        private_ip = instance['PrivateIpAddress']
        self._tag_resource(self.aws.get("tags", {}), instance_id)
        print 'created instance %s %s (%s)' % (instance_id, self._instance_name(), private_ip)
        return instance_id

    def _create_instance_args(self):
        ami = self.aws['ami']
        keypair = self.aws.get('keypair')
        security_groups = self.aws.get('security_groups')
        instance_type = self.aws.get('instance_type', 't2.micro')
        detailed_monitoring = self.aws.get('detailed_monitoring', False)
        ebs_optimized = self.aws.get('ebs_optimized', False)
        kwargs = {
            'ImageId': ami,
            'MinCount': 1,
            'MaxCount': 1,
            'InstanceType': instance_type,
            'Monitoring': { 'Enabled': detailed_monitoring },
            'EbsOptimized': ebs_optimized
        }

        if security_groups:
            kwargs['SecurityGroupIds'] = security_groups.split(',')
        if keypair:
            kwargs['KeyName'] = keypair

        return kwargs

    def _create_image(self, instance_id):
        date = datetime.datetime.now()
        image_date = date.strftime('%Y-%m-%d-%H-%M-%S')
        image_name = "%s_%s_%s" % (self.image_name, self.image_version, image_date)
        image_desc = "%s image created by cloud-compose." % (image_name)
        image_id = self._ec2_create_image(InstanceId=instance_id, Name=image_name, Description=image_desc)
        self._tag_resource(self.aws.get("tags", {}), image_id)
        print 'created %s %s' % (image_id, image_name)

    def _terminate_instance(self, instance_id):
        self._ec2_terminate_instances(InstanceIds=[instance_id])

    def _wait_for_instance_stop(self, instance_id):
        while True:
            status = self._find_instance_status(instance_id)
            if status == 'stopped':
                print "\n"
                break
            elif status == 'pending' or status == 'running' or status == 'stopping':
                sys.stdout.write('.')
                sys.stdout.flush()
                time.sleep(self.polling_interval)
                continue
            else:
                print "\ninstance %s has entered an unexpected state and will be terminated" % instance_id
                self._ec2_terminate_instances(InstanceIds=[instance_id])
                break

    def _tag_resource(self, tags, resource_id):
        resource_tags = self._build_tags(tags)
        self._ec2_create_tags(Resources=[resource_id], Tags=resource_tags)

    def _instance_name(self):
        return '%s:%s' % (self.image_name, self.image_version)

    def _build_tags(self, tags):
        instance_tags = [
            {
                'Key': 'ImageName',
                'Value': self.image_name
            }, {
                'Key': 'ImageVersion',
                'Value': str(self.image_version)
            }, {
                'Key': 'Name',
                'Value' : self._instance_name()
            }
        ]

        for key, value in tags.items():
            instance_tags.append({
                "Key": key,
                "Value" : str(value),
            })

        return instance_tags

    def _remove_unused_images(self):
        image_ids = self._find_unused_images(self._find_available_image_ids())
        for image_id in image_ids:
            self._ec2_deregister_image(ImageId=image_id)
            print 'deleted unused image %s' % image_id

    def _find_available_image_ids(self):
        image_ids = []
        filters = [
            {"Name": "state", "Values": ["available"]},
            {"Name": "tag:ImageName", "Values": [self.image_name]}
        ]
        for image in self._ec2_describe_images(Filters=filters):
            image_id = image['ImageId']
            if len(image_id) == 0:
                continue
            image_ids.append(image_id)
        return image_ids

    def _find_unused_images(self, image_ids):
        unused_image_ids = []
        for image_id in image_ids:
            filters = [
                {"Name": "image-id", "Values": [image_id]},
                {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
            ]
            reservations = self._ec2_describe_instances(Filters=filters).get('Reservations', [])
            if len(reservations) == 0:
                unused_image_ids.append(image_id)

        return unused_image_ids

    def _is_retryable_exception(exception):
        return not isinstance(exception, botocore.exceptions.ClientError)

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _find_instance_status(self, instance_id):
        instances = self._ec2_describe_instances(InstanceIds=[instance_id])
        for reservation in instances.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                if 'State' in instance:
                    return instance['State']['Name']

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _ec2_run_instances(self, **kwargs):
        return self.ec2.run_instances(**kwargs)

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _ec2_deregister_image(self, **kwargs):
        return self.ec2.deregister_image(**kwargs)

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _ec2_create_tags(self, **kwargs):
        return self.ec2.create_tags(**kwargs)

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _ec2_create_image(self, **kwargs):
        return self.ec2.create_image(**kwargs)['ImageId']

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _ec2_terminate_instances(self, **kwargs):
        return self.ec2.terminate_instances(**kwargs)

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _ec2_describe_instances(self, **kwargs):
        return self.ec2.describe_instances(**kwargs)

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _ec2_describe_images(self, **kwargs):
        return self.ec2.describe_images(**kwargs)['Images']
