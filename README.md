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

### Docker Compose

This layer also installs the 'docker-compose' python package. So once the
Docker layer is installed you have the ability to use
[Docker Compose](https://docs.docker.com/compose/) functionality such as
control files, and logging.

### Memory Accounting
The charm supports altering the GRUB2 options enabling cgroups and memory
accounting. Changing this value will reboot the host, and any running workloads
are at the mery of the charm author inhereting from this charm. Please use
`--restart=always` on your container runs that need to be persistent.

## Credit

This charm contains a slightly modified copy of the script contained at:
[https://get.docker.io](https://get.docker.io)

The modifications were raising status messages for Juju so its apparent what is
happening to the end user following along with Juju's extended status feature.
