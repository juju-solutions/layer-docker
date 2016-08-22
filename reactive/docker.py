import os
from shlex import split
from subprocess import check_call
from subprocess import check_output

from charmhelpers.core.hookenv import status_set
from charmhelpers.core.hookenv import config
from charmhelpers.core.host import lsb_release
from charmhelpers.core.host import service_restart
from charmhelpers.core.templating import render
from charmhelpers.fetch import apt_install
from charmhelpers.fetch import apt_update

from charms.reactive import remove_state
from charms.reactive import set_state
from charms.reactive import when
from charms.reactive import when_any
from charms.reactive import when_not

from charms.docker import DockerOpts

from charms import layer

# 2 Major events are emitted from this layer.
#
# `docker.ready` is an event intended to signal other layers that need to
# plug into the plumbing to extend the docker daemon. Such as fire up a
# bootstrap docker daemon, or predependency fetch + dockeropt rendering
#
# `docker.available` means the docker daemon setup has settled and is prepared
# to run workloads. This is a broad state that has large implications should
# you decide to remove it. Production workloads can be lost if no restart flag
# is provided.

# Be sure you bind to it appropriately in your workload layer and
# react to the proper event.


@when_not('docker.ready')
def install():
    ''' Install the docker daemon, and supporting tooling '''
    # Often when building layer-docker based subordinates, you dont need to
    # incur the overhead of installing docker. This tuneable layer option
    # allows you to disable the exec of that install routine, and instead short
    # circuit immediately to docker.available, so you can charm away!
    layer_opts = layer.options('docker')
    if layer_opts['skip-install']:
        set_state('docker.available')
        set_state('docker.ready')
        return

    status_set('maintenance', 'Installing AUFS and other tools')
    kernel_release = check_output(['uname', '-r']).rstrip()
    packages = [
        'aufs-tools',
        'git',
        'linux-image-extra-{0}'.format(kernel_release),
    ]
    apt_update()
    apt_install(packages)
    # Install docker-engine from apt.
    install_from_apt()

    opts = DockerOpts()
    render('docker.defaults', '/etc/default/docker', {'opts': opts.to_s()})
    render('docker.systemd', '/lib/systemd/system/docker.service', config())
    reload_system_daemons()

    status_set('active', 'Docker installed, cycling for extensions')
    set_state('docker.ready')

    # Make with the adding of the users to the groups
    check_call(['usermod', '-aG', 'docker', 'ubuntu'])


@when_any('config.http_proxy.changed', 'config.https_proxy.changed')
def restart_docker():
    set_state('docker.restart')


def install_from_apt():
    ''' Install docker from the apt repository. This is a pyton adaptation of
    the shell script found at https://get.docker.com/ '''
    status_set('maintenance', 'Installing docker-engine from apt')
    keyserver = 'hkp://p80.pool.sks-keyservers.net:80'
    key = '58118E89F3A912897C070ADBF76221572C52609D'
    # Enter the server and key in the apt-key management tool.
    cmd = 'apt-key adv --keyserver {0} --recv-keys {1}'.format(keyserver, key)
    # "apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80
    # --recv-keys 58118E89F3A912897C070ADBF76221572C52609D"
    check_call(split(cmd))
    # The url to the server that contains the docker apt packages.
    apt_url = 'https://apt.dockerproject.org'
    # Get the package architecture (amd64), not the machine hardware (x86_64)
    arch = check_output(split('dpkg --print-architecture'))
    arch = arch.decode('utf-8').rstrip()
    # Get the lsb information as a dictionary.
    lsb = lsb_release()
    # Ubuntu must be lowercased.
    dist = lsb['DISTRIB_ID'].lower()
    # The codename for the release.
    code = lsb['DISTRIB_CODENAME']
    # repo can be: main, testing or experimental
    repo = 'main'
    # deb [arch=amd64] https://apt.dockerproject.org/repo ubuntu-xenial main
    deb = 'deb [arch={0}] {1}/repo {2}-{3} {4}'.format(
            arch, apt_url, dist, code, repo)
    # mkdir -p /etc/apt/sources.list.d
    if not os.path.isdir('/etc/apt/sources.list.d'):
        os.makedirs('/etc/apt/sources.list.d')
    # Write the docker source file to the apt sources.list.d directory.
    with(open('/etc/apt/sources.list.d/docker.list', 'w+')) as stream:
        stream.write(deb)
    apt_update(fatal=True)
    # apt-get install -y -q docker-engine
    apt_install(['docker-engine'], fatal=True)


@when('docker.ready')
@when_not('cgroups.modified')
def enable_grub_cgroups():
    cfg = config()
    if cfg.get('enable-cgroups'):
        check_call(['scripts/enable_grub_cgroups.sh'])
        set_state('cgroups.modified')


@when('docker.ready')
@when_not('docker.available')
def signal_workloads_start():
    ''' We can assume the pre-workload bits have completed now that docker.ready
    has been reacted to. Lets remove the predep work and continue on to being
    available '''
    status_set('active', 'Docker installed')
    set_state('docker.available')


@when('docker.restart')
def recycle_daemon():
    ''' Other layers should be able to trigger a daemon restart '''
    status_set('maintenance', 'Restarting docker daemon')

    # Re-render our docker daemon template at this time... because we're
    # restarting. And its nice to play nice with others. Isn't that nice?
    opts = DockerOpts()
    render('docker.defaults', '/etc/default/docker', {'opts': opts.to_s()})
    render('docker.systemd', '/lib/systemd/system/docker.service', config())
    reload_system_daemons()
    service_restart('docker')
    remove_state('docker.restart')


def reload_system_daemons():
    ''' Reload the system daemons from on-disk configuration changes '''
    command = ['systemctl', 'daemon-reload']
    check_call(command)

