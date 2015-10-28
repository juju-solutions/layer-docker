from charmhelpers.core import hookenv
from charmhelpers.core import host
from charmhelpers.core.templating import render
from charms.reactive import when
from charms.reactive import when_not
from charms import reactive

from dockeropts import DockerOpts

from shlex import split
from subprocess import check_call


@when('etcd.available', 'docker.available')
@when_not('swarm.available')
def swarm_etcd_cluster_setup(etcd):
    """
    Expose the Docker TCP port, and begin swarm cluster configuration. Always
    leading with the agent, connecting to the discovery service, then follow
    up with the manager container on the leader node.
    """
    bind_docker_daemon()
    start_swarm_etcd_agent(etcd.connection_string())
    if hookenv.is_leader():
        start_swarm_etcd_manager(etcd.connection_string())
    reactive.set_state('swarm.available')
    hookenv.status_set('active', 'Swarm configured. Happy swarming')


@when_not('etcd.connected')
def user_notice():
    """
    Notify the user they need to relate the charm with ETCD to trigger the
    swarm cluster configuration.
    """
    hookenv.status_set('blocked', 'Pending ETCD connection for swarm')


@when('swarm.available')
@when_not('etcd.available')
def swarm_relation_broken():
    """
    Destroy the swarm agent, and optionally the manager.
    This state should only be entered if the Docker host relation with ETCD has
    been broken, thus leaving the cluster without a discovery service
    """
    cmd = "docker kill swarmagent"
    try:
        check_call(split(cmd))
    except:
        pass
    if hookenv.is_leader():
        cmd = "docker kill swarmmanger"
        try:
            check_call(split(cmd))
        except:
            pass


def start_swarm_etcd_agent(connection_string):
    hookenv.status_set('maintenance', 'starting swarm agent')
    addr = hookenv.unit_private_ip()
    # TODO: refactor to be process run
    cmd = "docker run -d --name swarmagent swarm join --advertise={0}:{1} {2}/swarm".format(addr, 2375, connection_string)  # noqa
    check_call(split(cmd))
    hookenv.open_port(2375)


def start_swarm_etcd_manager(connection_string):
    hookenv.status_set('maintenance', 'Starting swarm manager')
    # TODO: refactor to be process run
    cmd = "docker run -d --name swarmmanager -p 2377:2375 swarm manage {}/swarm".format(connection_string)  # noqa
    check_call(split(cmd))
    hookenv.open_port(2377)


def bind_docker_daemon():
    hookenv.status_set('maintenance', 'Configuring Docker for TCP connections')
    opts = DockerOpts()
    opts.add('host', 'tcp://{}:2375'.format(hookenv.unit_private_ip()))
    opts.add('host', 'unix:///var/run/docker.sock')
    render('docker.defaults', '/etc/default/docker', {'opts': opts.to_s()})
    host.service_restart('docker')
