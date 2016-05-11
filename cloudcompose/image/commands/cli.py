import click
from cloudcompose.cloudinit import CloudInit
#from cloudcompose.aws.cloudcontroller import CloudController
from cloudcompose.config import CloudConfig

@click.group()
def cli():
    pass

@cli.command()
def up(cloud_init, use_snapshots):
    """
    creates a new cluster
    """
    #cloud_config = CloudConfig()
    #ci = None

    #if cloud_init:
    #    ci = CloudInit()

    #cloud_controller = CloudController(cloud_config)
    #cloud_controller.up(ci, use_snapshots)

@cli.command()
def build():
    """
    builds the cloud_init script
    """
    cloud_config = CloudConfig()
    config_data = cloud_config.config_data('image')
    cloud_init = CloudInit('image')
    print cloud_init.build(config_data)
