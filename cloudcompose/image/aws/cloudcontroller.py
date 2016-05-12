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
        instance_id = self._create_instance(cloud_init)
        self._wait_for_instance_start(instance_id)
        self._create_ami(instance_id)
        self._terminate_instance(instance_id)

    def _create_instance(self, cloud_init):
        instance_id = None
        kwargs = self._create_instance_args()
        kwargs['SubnetId'] = self.aws["subnet"]

        if cloud_init:
            cloud_init_script = cloud_init.build(self.config_data)
            kwargs['UserData'] = cloud_init_script

        max_retries = 6
        retries = 0
        while retries < max_retries:
            retries += 1
            try:
                response = self._ec2_run_instances(**kwargs)
                if response:
                    instance_id = response['Instances'][0]['InstanceId']
                break
            except botocore.exceptions.ClientError as ex:
                print(ex.response["Error"]["Message"])

        self._tag_instance(self.aws.get("tags", {}), instance_id)
        return instance_id

    def _create_instance_args(self):
        ami = self.aws['ami']
        keypair = self.aws['keypair']
        security_groups = self.aws.get('security_groups', '').split(',')
        instance_type = self.aws.get('instance_type', 't2.micro')
        detailed_monitoring = self.aws.get('detailed_monitoring', False)
        ebs_optimized = self.aws.get('ebs_optimized', False)
        kwargs = {
            'ImageId': ami,
            'MinCount': 1,
            'MaxCount': 1,
            'KeyName': keypair,
            'InstanceType': instance_type,
            'Monitoring': { 'Enabled': detailed_monitoring },
            'EbsOptimized': ebs_optimized
        }

        if len(security_groups) > 0:
            kwargs['SecurityGroupIds'] = security_groups
        return kwargs

    def _create_ami(self, instance_id):
        pass

    def _terminate_instance(self, instance_id):
        pass

    def _wait_for_instance_start(self, instance_id):
        while True:
            status = self._find_instance_status(instance_id)
            if status == 'running':
                print "\n"
                break
            elif status == 'pending':
                sys.stdout.write('.')
                sys.stdout.flush()
                time.sleep(self.polling_interval)
                continue
            else:
                print "\ninstance %s has entered an unexpected state and will be terminated" % instance_id
                self._ec2_terminate_instances(InstanceIds=[instance_id])
                break

    def _tag_instance(self, tags, instance_id):
        instance_tags = self._build_instance_tags(tags)
        self._ec2_create_tags(Resources=[instance_id], Tags=instance_tags)

    def _build_instance_tags(self, tags):
        instance_tags = [
            {
                'Key': 'ImageName',
                'Value': self.image_name
            }, {
                'Key': 'Name',
                'Value' : ('%s:%s' % (self.image_name, self.image_version)),
            }
        ]

        for key, value in tags.items():
            instance_tags.append({
                "Key": key,
                "Value" : str(value),
            })

        return instance_tags

    def _is_retryable_exception(exception):
        return isinstance(exception, botocore.exceptions.ClientError) and \
           (exception.response["Error"]["Code"] in ['InvalidIPAddress.InUse', 'InvalidInstanceID.NotFound'] or
            'Invalid IAM Instance Profile name' in exception.response["Error"]["Message"])

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
    def _ec2_create_tags(self, **kwargs):
        return self.ec2.create_tags(**kwargs)

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _ec2_terminate_instances(self, **kwargs):
        return self.ec2.terminate_instances(**kwargs)

    @retry(retry_on_exception=_is_retryable_exception, stop_max_delay=10000, wait_exponential_multiplier=500, wait_exponential_max=2000)
    def _ec2_describe_instances(self, **kwargs):
        return self.ec2.describe_instances(**kwargs)
