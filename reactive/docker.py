import os
import json
import requests
from shlex import split
from subprocess import check_call
from subprocess import check_output
from subprocess import CalledProcessError
from subprocess import Popen, PIPE


from charmhelpers.core import host
from charmhelpers.core import hookenv
from charmhelpers.core.hookenv import status_set
from charmhelpers.core.hookenv import config
from charmhelpers.core.templating import render
from charmhelpers.fetch import apt_install
from charmhelpers.fetch import apt_purge
from charmhelpers.fetch import apt_update
from charmhelpers.fetch import apt_hold
from charmhelpers.fetch import apt_unhold
from charmhelpers.fetch import filter_installed_packages
from charmhelpers.contrib.charmsupport import nrpe

from charms.reactive import hook
from charms.reactive import remove_state
from charms.reactive import set_state
from charms.reactive import when
from charms.reactive import when_any
from charms.reactive import when_not
from charms.reactive.helpers import data_changed

from charms.docker import Docker
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

dockerpackages = {'apt': ['docker.io'],
                  'upstream': ['docker-ce'],
                  'nvidia': ['docker-ce',
                             'nvidia-docker2',
                             'nvidia-container-runtime',
                             'nvidia-container-runtime-hook']}


def holdall():
    for k in dockerpackages.keys():
        apt_hold(dockerpackages[k])


def unholdall():
    for k in dockerpackages.keys():
        apt_unhold(dockerpackages[k])


def set_custom_docker_package():
    """
    If a custom Docker package is defined, add it to
    the object.

    :return: None
    """
    runtime = determineAptSource()
    if runtime == 'custom':
        hookenv.log(
            'Adding custom package {} to environment'.format(
                config('docker_runtime_package')))
        dockerpackages['custom'] = [config('docker_runtime_package')]


@hook('upgrade-charm')
def upgrade():
    holdall()
    hookenv.log('Holding docker packages' +
                ' at current revision.')


def determineAptSource():
    docker_runtime = config('docker_runtime')

    if config('install_from_upstream'):
        docker_runtime = 'upstream'

    if docker_runtime == "auto":
        out = check_output(['lspci', '-nnk']).rstrip()
        if arch() == 'amd64' \
                and out.decode('utf-8').lower().count("nvidia") > 0:
            docker_runtime = "nvidia"
        else:
            docker_runtime = "apt"

    hookenv.log('Setting runtime to {0}'.format(docker_runtime))
    return docker_runtime


@when_not('docker.ready')
def install():
    ''' Install the docker daemon, and supporting tooling '''
    # switching runtimes causes a reinstall so remove any holds that exist
    unholdall()

    # Often when building layer-docker based subordinates, you dont need to
    # incur the overhead of installing docker. This tuneable layer option
    # allows you to disable the exec of that install routine, and instead short
    # circuit immediately to docker.available, so you can charm away!
    layer_opts = layer.options('docker')
    if layer_opts['skip-install']:
        set_state('docker.available')
        set_state('docker.ready')
        return

    status_set('maintenance', 'Installing AUFS and other tools.')
    kernel_release = check_output(['uname', '-r']).rstrip()
    packages = [
        'aufs-tools',
        'git',
        'linux-image-extra-{0}'.format(kernel_release.decode('utf-8')),
    ]
    apt_update()
    apt_install(packages)

    # Install Docker from apt.
    remove_state('nvidia-docker.supported')
    remove_state('nvidia-docker.installed')
    runtime = determineAptSource()
    if runtime == "upstream":
        install_from_upstream_apt()
    elif runtime == "nvidia":
        set_state('nvidia-docker.supported')
        install_from_nvidia_apt()
        set_state('nvidia-docker.installed')
    elif runtime == "apt":
        install_from_archive_apt()
    elif runtime == "custom":
        install_from_custom_apt()
    else:
        hookenv.log('unknown runtime {0}'.format(runtime))
        return False

    validate_config()
    opts = DockerOpts()
    render('docker.defaults', '/etc/default/docker',
           {'opts': opts.to_s(), 'docker_runtime': runtime})
    render('docker.systemd', '/lib/systemd/system/docker.service', config())
    reload_system_daemons()

    holdall()
    hookenv.log('Holding docker-engine and docker.io packages' +
                ' at current revision.')

    host.service_restart('docker')
    hookenv.log('Docker installed, setting "docker.ready" state.')
    set_state('docker.ready')

    # Make with the adding of the users to the groups
    check_call(['usermod', '-aG', 'docker', 'ubuntu'])


@when('config.changed.install_from_upstream', 'docker.ready')
def toggle_install_from_upstream():
    toggle_docker_daemon_source()


@when('config.changed.apt-key-server', 'docker.ready')
def toggle_install_with_new_keyserver():
    toggle_docker_daemon_source()


@when('config.changed.docker_runtime', 'docker.ready')
def toggle_docker_daemon_source():
    ''' A disruptive reaction to config changing that will remove the existing
    docker daemon and install the latest available deb from the upstream PPA,
    Nvidia PPA, or Universe depending on the docker_runtime setting. '''

    set_custom_docker_package()

    # this returns a list of packages not currently installed on the system
    # based on the parameters input. Use this to check if we have taken
    # prior action against a docker deb package.
    installed = []
    for k in dockerpackages.keys():
        packages = filter_installed_packages(dockerpackages[k])
        if packages == []:
            installed.append(k)

    # none of the docker packages are installed
    if len(installed) == 0:
        # we have not reached installation phase, return until
        # we can reasonably re-test this scenario
        hookenv.log('No supported docker runtime is installed. Noop.')
        return

    runtime = determineAptSource()
    if not dockerpackages.get(runtime):
        hookenv.log('unknown runtime {0}'.format(runtime))
        return False

    hookenv.log('runtime to install {0}'.format(runtime))

    # workaround
    # https://bugs.launchpad.net/ubuntu/+source/docker.io/+bug/1724353
    if os.path.exists('/var/lib/docker/nuke-graph-directory.sh'):
        hookenv.log('workaround bug 1724353')
        cmd = "sed -i '1i#!/bin/bash' /var/lib/docker/nuke-graph-directory.sh"
        check_call(split(cmd))

    # the package we want is not installed
    # so we need to uninstall either of the others that are installed
    # and reset the state to forcea reinstall
    if runtime not in installed:
        host.service_stop('docker')
        for k in dockerpackages.keys():
            pkglist = " ".join(dockerpackages[k])
            hookenv.log('Removing package(s): {0}'.format(pkglist))
            apt_unhold(dockerpackages[k])
            apt_purge(dockerpackages[k])
            remove_state('docker.ready')
            remove_state('docker.available')
    else:
        hookenv.log('Not touching packages.')


@when_any('config.changed.http_proxy', 'config.changed.https_proxy',
          'config.changed.no_proxy')
@when('docker.ready')
def proxy_changed():
    '''The proxy information has changed, render templates and restart the
    docker daemon.'''
    recycle_daemon()


def install_from_archive_apt():
    status_set('maintenance', 'Installing docker.io from universe.')
    apt_install(['docker.io'], fatal=True)


def install_from_upstream_apt():
    ''' Install docker from the apt repository. This is a pyton adaptation of
    the shell script found at https://get.docker.com/ '''
    status_set('maintenance', 'Installing docker-ce from upstream PPA.')
    key_url = 'https://download.docker.com/linux/ubuntu/gpg'
    add_apt_key_url(key_url)
    # The url to the server that contains the docker apt packages.
    apt_url = 'https://download.docker.com/linux/ubuntu'
    # Get the package architecture (amd64), not the machine hardware (x86_64)
    architecture = arch()
    # Get the lsb information as a dictionary.
    lsb = host.lsb_release()
    # The codename for the release.
    code = lsb['DISTRIB_CODENAME']
    # repo can be: stable, edge or test.
    repo = 'stable'
    # deb [arch=amd64] https://download.docker.com/linux/ubuntu bionic stable
    deb = list()
    deb.append('deb [arch={0}] {1} {2} {3}'.format(
        architecture, apt_url, code, repo))
    write_docker_sources(deb)
    apt_update(fatal=True)
    # apt-get install -y -q docker-ce
    apt_install(['docker-ce'], fatal=True)


def install_from_nvidia_apt():
    ''' Install cuda docker from the nvidia apt repository. '''
    status_set('maintenance', 'Installing docker-engine from Nvidia PPA.')
    # Get the server and key in the apt-key management tool.
    add_apt_key("9DC858229FC7DD38854AE2D88D81803C0EBFCD88")
    # Install key for nvidia-docker. This key changes frequently
    # ([expires: 2019-09-20]) so we should do what the official docs say and
    # not try to get it through its fingerprint.
    add_apt_key_url("https://nvidia.github.io/nvidia-container-runtime/gpgkey")

    # Get the package architecture (amd64), not the machine hardware (x86_64)
    architecture = arch()
    # Get the lsb information as a dictionary.
    lsb = host.lsb_release()
    code = lsb['DISTRIB_CODENAME']
    rel = lsb['DISTRIB_RELEASE']
    ubuntu = str(lsb['DISTRIB_ID']).lower()
    dockurl = "https://download.docker.com/linux/ubuntu"
    nvidurl = 'https://nvidia.github.io'
    repo = 'stable'

    deb = list()
    deb.append('deb [arch={0}] {1} {2} {3}'.format(architecture,
                                                   dockurl, code, repo))
    for i in ['libnvidia-container',
              'nvidia-container-runtime',
              'nvidia-docker']:
        deb.append('deb {0}/{1}/ubuntu{2}/{3} /'.format(nvidurl,
                                                        i, rel, architecture))

    write_docker_sources(deb)

    install_cuda_drivers_repo(architecture, rel, ubuntu)

    apt_update(fatal=True)
    # actually install the required packages docker-ce nvidia-docker2

    docker_ce = hookenv.config('docker-ce-package')
    nvidia_docker2 = hookenv.config('nvidia-docker-package')
    nv_container_runtime = hookenv.config('nvidia-container-runtime-package')
    apt_install(['cuda-drivers', docker_ce, nvidia_docker2,
                 nv_container_runtime], fatal=True)

    fix_docker_runtime_nvidia()


def install_from_custom_apt():
    ''' Install docker from custom repository. '''
    status_set('maintenance', 'Installing Docker from custom repository.')

    repo_string = config('docker_runtime_repo')
    key_url = config('docker_runtime_key_url')
    package_name = config('docker_runtime_package')

    if not repo_string:
        message = '`docker_runtime_repo` must be set'
        hookenv.log(message)
        hookenv.status_set('blocked', message)
        return False

    if not key_url:
        message = '`docker_runtime_key_url` must be set'
        hookenv.log(message)
        hookenv.status_set('blocked', message)
        return False

    if not package_name:
        message = '`docker_runtime_package` must be set'
        hookenv.log(message)
        hookenv.status_set('blocked', message)
        return False

    lsb = host.lsb_release()

    format_dictionary = {
        'ARCH': arch(),
        'CODE': lsb['DISTRIB_CODENAME']
    }

    add_apt_key_url(key_url)
    write_docker_sources([repo_string.format(**format_dictionary)])
    apt_update()
    apt_install([package_name])


def install_cuda_drivers_repo(architecture, rel, ubuntu):
    ''' Install cuda drivers this is xenial only.
     We want to install cuda-drivers only this means that the
     cuda version plays no role. Any repo will do. '''
    key_file = '7fa2af80.pub'
    # distribution should be something like ubuntu1604
    distribution = '{}{}'.format(ubuntu, str(rel).replace('.', ''))
    repo_path = 'developer.download.nvidia.com/compute/' \
                'cuda/repos/{}/x86_64'.format(distribution)
    cmd = 'apt-key adv --fetch-keys http://{}/{}'.format(repo_path, key_file)
    check_call(split(cmd))
    cuda_repo_version = config('cuda_repo')
    cuda_repo_pkg = 'cuda-repo-{}_{}_{}.deb'.format(distribution,
                                                    cuda_repo_version,
                                                    architecture)
    repo_url = 'https://{}/{}'.format(repo_path, cuda_repo_pkg)
    r = requests.get(repo_url)
    r.raise_for_status()
    with open(cuda_repo_pkg, "wb") as repo_file:
        for chunk in r.iter_content(chunk_size=1024):
            repo_file.write(chunk)
    r.close()
    cmd = 'dpkg -i  {}'.format(cuda_repo_pkg)
    check_call(split(cmd))


def fix_docker_runtime_nvidia():
    """
    The default runtime needs setting
    to `nvidia` after Docker installation.

    :return: None
    """
    with open('/etc/docker/daemon.json') as f:
        data = json.load(f)
    data['default-runtime'] = 'nvidia'
    with open('/etc/docker/daemon.json', 'w') as f:
        json.dump(data, f)

    host.service_restart('docker')


def write_docker_sources(deb):
    '''Write docker.list under etc/apt/sources.list.d'''
    # mkdir -p /etc/apt/sources.list.d
    if not os.path.isdir('/etc/apt/sources.list.d'):
        os.makedirs('/etc/apt/sources.list.d')
    # Write the docker source file to the apt sources.list.d directory.
    with(open('/etc/apt/sources.list.d/docker.list', 'w+')) as stream:
        stream.write("\n".join(deb))


def add_apt_key_url(url):
    '''Add a key from a URL'''
    curl_cmd = "curl -s -L {}".format(url).split()
    curl = Popen(curl_cmd, stdout=PIPE)
    apt_cmd = "apt-key add -".split()
    check_call(apt_cmd, stdin=curl.stdout)
    curl.wait()


def add_apt_key(key):
    '''Enter the server and key in the apt-key management tool.'''
    keyserver = config('apt-key-server')
    cmd = 'apt-key adv --keyserver {0} --recv-keys {1}'.format(keyserver, key)
    # "apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80
    # --recv-keys 58118E89F3A912897C070ADBF76221572C52609D"
    check_call(split(cmd))


@when('docker.ready')
@when_not('cgroups.modified')
def enable_grub_cgroups():
    cfg = config()
    if cfg.get('enable-cgroups'):
        hookenv.log('Calling enable_grub_cgroups.sh and rebooting machine.')
        check_call(['scripts/enable_grub_cgroups.sh'])
        set_state('cgroups.modified')


@when('docker.ready')
@when_not('docker.available')
def signal_workloads_start():
    ''' Signal to higher layers the container runtime is ready to run
        workloads. At this time the only reasonable thing we can do
        is determine if the container runtime is active. '''

    # before we switch to active, probe the runtime to determine if
    # it is available for workloads. Assumine response from daemon
    # to be sufficient

    if not _probe_runtime_availability():
        status_set('waiting', 'Container runtime not available.')
        return

    status_set('active', 'Container runtime available.')
    set_state('docker.available')


@when('sdn-plugin.available', 'docker.available')
def container_sdn_setup(sdn):
    ''' Receive the information from the SDN plugin, and render the docker
    engine options. '''
    sdn_config = sdn.get_sdn_config()
    bind_ip = sdn_config['subnet']
    mtu = sdn_config['mtu']
    if data_changed('bip', bind_ip) or data_changed('mtu', mtu):
        status_set('maintenance', 'Configuring container runtime with SDN.')
        opts = DockerOpts()
        # This is a great way to misconfigure a docker daemon. Remove the
        # existing bind ip and mtu values of the SDN
        if opts.exists('bip'):
            opts.pop('bip')
        if opts.exists('mtu'):
            opts.pop('mtu')
        opts.add('bip', bind_ip)
        opts.add('mtu', mtu)
        _remove_docker_network_bridge()
        set_state('docker.sdn.configured')


@when_not('sdn-plugin.available')
@when('docker.sdn.configured')
def scrub_sdn_config():
    ''' If this scenario of states is true, we have likely broken a
    relationship to our once configured SDN provider. This necessitates a
    cleanup of the Docker Options for BIP and MTU of the presumed dead SDN
    interface. '''

    opts = DockerOpts()
    try:
        opts.pop('bip')
    except KeyError:
        hookenv.log('Unable to locate bip in Docker config.')
        hookenv.log('Assuming no action required.')

    try:
        opts.pop('mtu')
    except KeyError:
        hookenv.log('Unable to locate mtu in Docker config.')
        hookenv.log('Assuming no action required.')

    # This method does everything we need to ensure the bridge configuration
    # has been removed. restarting the daemon restores docker with its default
    # networking mode.
    _remove_docker_network_bridge()
    recycle_daemon()
    remove_state('docker.sdn.configured')


@when('docker.restart')
def docker_restart():
    '''Other layers should be able to trigger a daemon restart. Invoke the
    method that recycles the docker daemon.'''
    recycle_daemon()
    remove_state('docker.restart')


@when('config.changed.docker-opts', 'docker.ready')
def docker_template_update():
    ''' The user has passed configuration that directly effects our running
    docker engine instance. Re-render the systemd files and recycle the
    service. '''
    recycle_daemon()


@when('docker.ready', 'dockerhost.connected')
@when_not('dockerhost.configured')
def dockerhost_connected(dockerhost):
    '''Transmits the docker url to any subordinates requiring it'''
    dockerhost.configure(Docker().socket)


@when('nrpe-external-master.available')
@when_not('nrpe-external-master.docker.initial-config')
def initial_nrpe_config(nagios=None):
    set_state('nrpe-external-master.docker.initial-config')
    update_nrpe_config(nagios)


@when('docker.ready')
@when('nrpe-external-master.available')
@when_any('config.changed.nagios_context',
          'config.changed.nagios_servicegroups')
def update_nrpe_config(unused=None):
    # List of systemd services that will be checked
    services = ('docker',)

    # The current nrpe-external-master interface doesn't handle a lot of logic,
    # use the charm-helpers code for now.
    hostname = nrpe.get_nagios_hostname()
    current_unit = nrpe.get_nagios_unit_name()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe.add_init_service_checks(nrpe_setup, services, current_unit)
    nrpe_setup.write()


@when_not('nrpe-external-master.available')
@when('nrpe-external-master.docker.initial-config')
def remove_nrpe_config(nagios=None):
    remove_state('nrpe-external-master.docker.initial-config')

    # List of systemd services for which the checks will be removed
    services = ('docker',)

    # The current nrpe-external-master interface doesn't handle a lot of logic,
    # use the charm-helpers code for now.
    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname, primary=False)

    for service in services:
        nrpe_setup.remove_check(shortname=service)


class ConfigError(Exception):
    pass


def validate_config():
    '''Check that config is valid.'''
    MAX_LINE = 2048
    line_prefix_len = len("Environment=\"NO_PROXY=\"\"")
    remain_len = MAX_LINE - line_prefix_len
    if len(config('no_proxy')) > remain_len:
        raise ConfigError('no_proxy longer than {} chars.'.format(remain_len))


def recycle_daemon():
    '''Render the docker template files and restart the docker daemon on this
    system.'''
    validate_config()
    hookenv.log('Restarting docker service.')
    # Re-render our docker daemon template at this time... because we're
    # restarting. And its nice to play nice with others. Isn't that nice?
    opts = DockerOpts()
    runtime = determineAptSource()
    render('docker.defaults', '/etc/default/docker',
           {'opts': opts.to_s(),
            'manual': config('docker-opts'),
            'docker_runtime': runtime})
    render('docker.systemd', '/lib/systemd/system/docker.service', config())
    reload_system_daemons()
    host.service_restart('docker')

    if not _probe_runtime_availability():
        status_set('waiting', 'Container runtime not available.')
        return


def reload_system_daemons():
    ''' Reload the system daemons from on-disk configuration changes '''
    hookenv.log('Reloading system daemons.')
    lsb = host.lsb_release()
    code = lsb['DISTRIB_CODENAME']
    if code != 'trusty':
        command = ['systemctl', 'daemon-reload']
        check_call(command)
    else:
        host.service_reload('docker')


def _probe_runtime_availability():
    ''' Determine if the workload daemon is active and responding '''
    try:
        cmd = ['docker', 'info']
        check_call(cmd)
        return True
    except CalledProcessError:
        # Remove the availability state if we fail reachability
        remove_state('docker.available')
        return False


def _remove_docker_network_bridge():
    ''' By default docker uses the docker0 bridge for container networking.
    This method removes the default docker bridge, and reconfigures the
    DOCKER_OPTS to use the SDN networking bridge. '''
    status_set('maintenance',
               'Reconfiguring container runtime network bridge.')
    host.service_stop('docker')
    apt_install(['bridge-utils'], fatal=True)
    # cmd = "ifconfig docker0 down"
    # ifconfig doesn't always work. use native linux networking commands to
    # mark the bridge as inactive.
    cmd = ['ip', 'link', 'set', 'docker0', 'down']
    check_call(cmd)

    cmd = ['brctl', 'delbr', 'docker0']
    check_call(cmd)

    # Render the config and restart docker.
    recycle_daemon()


def arch():
    '''Return the package architecture as a string.'''
    # Get the package architecture for this system.
    if not arch.architecture:
        arch.architecture = check_output(['dpkg',
                                          '--print-architecture']).rstrip()
        arch.architecture = arch.architecture.decode('utf-8')
    return arch.architecture
arch.architecture = None # noqa: E261, E305
