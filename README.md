# Charm for Docker

This charm deploys the [Docker](http://docker.com) engine within Juju. Docker 
is an open platform for developers and sysadmins to build, ship, and run 
distributed applications in containers.

Docker containers wrap a piece of software in a complete file system that 
contains everything needed to run an application on a server.

Docker focuses on distributing applications as containers that can be quickly 
assembled from components that are run the same on different servers without 
environmental dependencies. This eliminates the friction between development, 
QA, and production environments.

Most people will want to extend this charm to make their Docker container or 
application deployable from Juju. The 
[Charm layer](https://github.com/juju-solutions/layer-docker) can be extended to
include docker container along with additional operational code. Please refer
to the [Charm Layers](https://jujucharms.com/docs/devel/developer-layers)
documentation on [jujucharms.com](https://jujucharms.com/docs) for more 
information.

# States

The following states are set by this layer:

* `nvidia-docker.supported`

  This state is set when supported GPU hardware is detected.

* `nvidia-docker.installed`

  This state is set once CUDA-related packages are installed and configured.


## Using the Docker Charm

Docker does not require anything by default so you can deploy the Charm by the 
following command.

```
juju deploy docker
```

**NOTE**: You can ask Juju to deploy a different release of Ubuntu by using the
`--series` and the code name of the release "trusty" for 14.04 and "xenial" for
16.04.

Once deployed you have a docker-engine running on a unit in Juju. You can open
a session to that unit and issue the `docker` command to start using it 
right away.

```
juju ssh docker/0
...
$ docker run hello-world
```

## Scale out Usage

Scaling out the Charm is as simple as adding additional docker units
with Juju `add-unit` command to expand your cluster. However, you will need an
SDN solution to provide cross host networking. See the Known Limitations and 
issues about this.

# Configuration

See [config.yaml](config.yaml) for
list of configuration options.

## Docker Compose

This Charm also installs the 'docker-compose' python package using pip. So
once the Charm has finished installing you have the ability to use [Docker
Compose](https://docs.docker.com/compose/) functionality such as control files,
and logging.

# Contact Information

This Charm is available at <https://jujucharms.com/docker> and contains the 
open source operations code to deploy on all public clouds in the Juju 
ecosystem.

## Docker links

  - The [Docker homepage](https://www.docker.com/)
  - Docker [documentation](https://docs.docker.com/) for help with Docker 
  commands.
  - Docker [forums](https://forums.docker.com/) for community discussions.
  - Check the Docker [issue tracker](https://github.com/docker/docker/issues) 
  for bugs or problems with the Docker software.
  - The [layer-docker](https://github.com/juju-solutions/layer-docker) is
  the GitHub repository that contains the reactive code to build this Charm.
  - Check the layer-docker
  [issue-tracker](https://github.com/juju-solutions/layer-docker/issues) for
  bugs or problems related to the Charm.
