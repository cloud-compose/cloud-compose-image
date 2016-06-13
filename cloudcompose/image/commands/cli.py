import click
from cloudcompose.cloudinit import CloudInit
from cloudcompose.image.aws.cloudcontroller import CloudController
from cloudcompose.config import CloudConfig
from cloudcompose.exceptions import CloudComposeException

@click.group()
def cli():
    pass

@cli.command()
@click.option('--cloud-init/--no-cloud-init', default=True, help="Initialize the instance with a cloud init script. Otherwise the instance will just stop once it starts.")
def up(cloud_init):
    """
    creates a new cluster
    """
    try:
        cloud_config = CloudConfig()
        ci = None

        if cloud_init:
            ci = CloudInit('image')

        cloud_controller = CloudController(cloud_config)
        cloud_controller.up(ci)
    except CloudComposeException as ex:
        print ex.message

@cli.command()
def down():
    """
    destroys an existing cluster
    """
    try:
        cloud_config = CloudConfig()
        cloud_controller = CloudController(cloud_config)
        cloud_controller.down()
    except CloudComposeException as ex:
        print ex.message

@cli.command()
def build():
    """
    builds the cloud_init script
    """
    try:
        cloud_config = CloudConfig()
        config_data = cloud_config.config_data('image')
        cloud_init = CloudInit('image')
        print cloud_init.build(config_data)
    except CloudComposeException as ex:
        print ex.message
