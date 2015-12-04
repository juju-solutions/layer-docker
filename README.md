# Charm Layer for Docker

This repository contains the Charm layer for docker, which can be used as a
base layer for other Charms that use docker.  Please refer to the
[Juju composer docs](https://jujucharms.com/docs/devel/authors-charm-composing).

## Usage

In a charm that wants to use docker, the integration can be as simple as placing
the following in your charm's `compose.yaml`:

    includes: ['layer:docker']

From here, you simply amend any hooks/reactive patterns you require to deliver
and manage the lifecycle of your applications docker image.

### States

The docker layer raises a few synthetic events:

- docker.ready

- docker.available

##### docker.ready

When docker.ready is set, this event is before we signify to other
layers that we are ready to start workloads, which should allow for
docker extensions to be installed free of disrupting active workloads.

For example, installing SDN support and getting the daemon configured
for TCP connections.

```
@when('docker.ready')
def start_flannel_networking():
    # do something here
```

##### docker.available

When docker.available is set, the daemon is considered fully configured
and ready to accept workloads.

```
@when('docker.available')
def start_my_workload():
    # do something with docker
```

### Docker Compose

 This layer installs the 'docker-compose' python package from pypi. So
once the Docker layer is installed you have the ability to use [Docker
Compose](https://docs.docker.com/compose/) functionality such as control files,
and logging.

### Memory Accounting
The charm supports altering the GRUB2 options enabling CGROUPS and memory
accounting. Changing this value will reboot the host, and any running workloads
are at the mercy of the charm author inheriting from this charm. Please use
`--restart=always` on your container runs that need to be persistent.

### charms.docker

This layer also includes a wheelhouse of `charms.docker` a python library to make
charming with docker, and configuring the docker daemon much easier, and syntactically
enjoyable. For more information about this library see the [project](http://github.com/juju-solutions/charms.docker)

## Credit

This charm contains a slightly modified copy of the script contained at:
[https://get.docker.io](https://get.docker.io)

The modifications were raising status messages for Juju so its apparent what is
happening to the end user following along with Juju's extended status feature.
