# Cloud Compose image plugin
The Cloud Compose image plugin is used to create a base image for launching instances from. The base image should have all the package install commands applied to it, but none of the configuration changes. This ensures that all nodes in a cluster have exactly the same packages in them, but a base image can be reused across many projects by changing the configuration options.

To create a new image you need the following items
1. cloud-compose.yml 
1. image.sh script for updating the image

Once you have the configuration files run the following commands to create a new image: 
```
cd my-configs
pip install cloud-compose cloud-compose-image
pip freeze -r > requirements.txt
cloud-compose image up
```

See the example folder for a basic docker 1.10 image configuration.

Although the cluster plugins is designed to be cloud agnostic, AWS is the only cloud provider currently supported.  Support for other cloud providers is welcomed as pull requests.

### AWS backend
If you are using the AWS backend the image plugin uses the [Boto](http://boto3.readthedocs.io/en/latest/) client which requires the following environment variables:

* AWS_REGION
* AWS_ACCESS_KEY_ID
* AWS_SECRET_ACCESS_KEY

If you are using multiple AWS accounts it is convenient to use [Envdir](https://pypi.python.org/pypi/envdir) to easily switch between AWS accounts.

## Configuration 
To understand the purpose of each configuration file consider the follow examples with an explanation of each element.

### cloud-compose.yml
```yaml
image:
  name: docker
  version: '1.10'
  search_path:
    - ../templates
  aws:
    ami: ami-6d1c2007
    subnet: subnet-9f0074c6
    keypair: drydock
    instance_type: t2.micro
    security_groups: sg-35c74951
```

#### name
The ``name`` is the name of image. This name will be used along with the version and a timestamp to create unique image names.  

#### version 
The ``version`` is used in conjuction with the name to allow clients to .

#### search_path 
The ``search_path`` is the directories that will be examined when looking for configuration files like the ``image.sh`` file.

#### AWS
The AWS section contains information needed to create the cluster on AWS.

##### ami
The ``ami`` is the Amazon Machine Image to start image creation process from.

##### subnet 
The ``subnet`` to launch the instance in.

##### security_groups (optional)
The list of ``security_groups`` that should be added to the EC2 servers. If you do not want to ssh into the instance to troubleshoot, this is not needed.

##### instance_type (optional)
The ``instance_type`` you want to use for the image creation process. Defaults to t2.micro.

##### keypair (optional)
The ``keypair`` is the SSH key that will be added to the EC2 servers. If you do not want to ssh into the instance to troubleshoot, this is not needed.

## Cleanup
Everytime an image is created, unused images with the same ``name`` are delete. The delete process uses the ImageName tag attribute to find and delete old images that are not currently being used by running instances.

## Contributing 
To work on the code locally, checkout both cloud-compose and cloud-compose-image to the same parent directory. Then use a virtualenv and pip install editable to start working on them locally.
```
mkvirtualenv cloud-compose
pip install --editable cloud-compose
pip install --editable cloud-compose-image
```
