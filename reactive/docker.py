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

from charms.layer.docker import arch
from charms.layer.docker import docker_packages
from charms.layer.docker import determine_apt_source
from charms.layer.docker import render_configuration_template

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


def hold_all():
    """
    Hold packages.

    :return: None
    """
    for k in docker_packages.keys():
        apt_hold(docker_packages[k])


def unhold_all():
    """
    Unhold Packages.

    :return: None
    """
    for k in docker_packages.keys():
        apt_unhold(docker_packages[k])


@hook('upgrade-charm')
def upgrade():
    """
    :return: None
    """
    hold_all()
    hookenv.log(
        'Holding docker packages at current revision.')


def set_custom_docker_package():
    """
    If a custom Docker package is defined, add it to
    the object.

    :return: None
    """
    runtime = determine_apt_source()
    if runtime == 'custom':
        hookenv.log(
            'Adding custom package {} to environment'.format(
                config('docker_runtime_package')))
        docker_packages['custom'] = [config('docker_runtime_package')]


@when_not('docker.ready')
def install():
    """
    Install the docker daemon, and supporting tooling.

    :return: None or False
    """
    # Switching runtimes causes a reinstall so remove any holds that exist.
    unhold_all()

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
        'linux-image-extra-{}'.format(kernel_release.decode('utf-8')),
    ]
    apt_update()
    apt_install(packages)

    # Install docker-engine from apt.
    runtime = determine_apt_source()
    remove_state('nvidia-docker.supported')
    remove_state('nvidia-docker.installed')
    if runtime == 'upstream':
        install_from_upstream_apt()
    elif runtime == 'nvidia':
        set_state('nvidia-docker.supported')
        install_from_nvidia_apt()
        set_state('nvidia-docker.installed')
    elif runtime == 'apt':
        install_from_archive_apt()
    elif runtime == 'custom':
        if not install_from_custom_apt():
            return False  # If install fails, stop.
    else:
        hookenv.log('Unknown runtime {}'.format(runtime))
        return False

    validate_config()
    render_configuration_template(service=True)
    reload_system_daemons()

    hold_all()
    hookenv.log(
        'Holding docker-engine and docker.io packages at current revision.')

    host.service_restart('docker')
    hookenv.log('Docker installed, setting "docker.ready" state.')
    set_state('docker.ready')

    # Make with the adding of the users to the groups
    check_call(['usermod', '-aG', 'docker', 'ubuntu'])


@when('config.changed.install_from_upstream', 'docker.ready')
def toggle_install_from_upstream():
    """
    :return: None
    """
    toggle_docker_daemon_source()


@when('config.changed.apt-key-server', 'docker.ready')
def toggle_install_with_new_keyserver():
    """
    :return: None
    """
    toggle_docker_daemon_source()


@when('config.changed.docker_runtime', 'docker.ready')
def toggle_docker_daemon_source():
    """
    A disruptive reaction to config changing that will remove the existing
    docker daemon and install the latest available deb from the upstream PPA,
    Nvidia PPA, or Universe depending on the docker_runtime setting.

    :return: None or False
    """

    # This returns a list of packages not currently installed on the system
    # based on the parameters input. Use this to check if we have taken
    # prior action against a docker deb package.
    installed = []
    for k in docker_packages.keys():
        packages = filter_installed_packages(docker_packages[k])
        if packages == []:
            installed.append(k)

    # None of the docker packages are installed.
    if len(installed) == 0:
        # We have not reached installation phase, return until
        # we can reasonably re-test this scenario.
        hookenv.log('No supported docker runtime is installed. Noop.')
        return

    runtime = determine_apt_source()
    if not docker_packages.get(runtime):
        hookenv.log('Unknown runtime {}'.format(runtime))
        return False

    hookenv.log('Runtime to install {}'.format(runtime))

    # Workaround
    # https://bugs.launchpad.net/ubuntu/+source/docker.io/+bug/1724353.
    if os.path.exists('/var/lib/docker/nuke-graph-directory.sh'):
        hookenv.log('Workaround bug 1724353')
        cmd = "sed -i '1i#!/bin/bash' /var/lib/docker/nuke-graph-directory.sh"
        check_call(split(cmd))

    # The package we want is not installed
    # so we need to uninstall either of the others that are installed
    # and reset the state to forcea reinstall.
    if runtime not in installed:
        host.service_stop('docker')
        for k in docker_packages.keys():
            package_list = " ".join(docker_packages[k])
            hookenv.log('Removing package(s): {}.'.format(package_list))
            apt_unhold(docker_packages[k])
            apt_purge(docker_packages[k])
            remove_state('docker.ready')
            remove_state('docker.available')
    else:
        hookenv.log('Not touching packages.')


@when_any('config.changed.http_proxy', 'config.changed.https_proxy',
          'config.changed.no_proxy')
@when('docker.ready')
def proxy_changed():
    """
    The proxy information has changed, render templates and restart the
    docker daemon.

    :return: None
    """
    recycle_daemon()


def install_from_archive_apt():
    """
    Install Docker from Ubuntu universe.

    :return: None
    """
    status_set('maintenance', 'Installing docker.io from universe.')
    apt_install(['docker.io'], fatal=True)


def install_from_upstream_apt():
    """
    Install docker from the apt repository. This is a pyton adaptation of
    the shell script found at https://get.docker.com/.

    :return: None
    """
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

    # Repo can be: stable, edge or test.
    repo = 'stable'

    # E.g.
    # deb [arch=amd64] https://download.docker.com/linux/ubuntu bionic stable
    debs = list()
    debs.append('deb [arch={}] {} {} {}'.format(
        architecture,
        apt_url,
        code,
        repo
    ))
    write_docker_sources(debs)
    apt_update(fatal=True)

    # Install Docker via apt.
    apt_install(
        docker_packages['upstream'],
        fatal=True
    )


def install_from_nvidia_apt():
    """
    Install cuda docker from the nvidia apt repository.

    :return: None
    """
    status_set('maintenance', 'Installing docker-engine from Nvidia PPA.')

    # Get the server and key in the apt-key management tool.
    add_apt_key('9DC858229FC7DD38854AE2D88D81803C0EBFCD88')

    # Install key for nvidia-docker. This key changes frequently
    # ([expires: 2019-09-20]) so we should do what the official docs say and
    # not try to get it through its fingerprint.
    add_apt_key_url('https://nvidia.github.io/nvidia-container-runtime/gpgkey')

    # Get the package architecture (amd64), not the machine hardware (x86_64)
    architecture = arch()

    # Get the lsb information as a dictionary.
    lsb = host.lsb_release()
    code = lsb['DISTRIB_CODENAME']
    release = lsb['DISTRIB_RELEASE']
    ubuntu = str(lsb['DISTRIB_ID']).lower()
    docker_url = 'https://download.docker.com/linux/ubuntu'
    nvidia_url = 'https://nvidia.github.io'
    repo = 'stable'

    debs = list()
    debs.append('deb [arch={}] {} {} {}'.format(
        architecture,
        docker_url,
        code,
        repo
    ))

    packages = [
        'libnvidia-container',
        'nvidia-container-runtime',
        'nvidia-docker'
    ]

    for package in packages:
        debs.append('deb {}/{}/ubuntu{}/{} /'.format(
            nvidia_url,
            package,
            release,
            architecture
        ))

    write_docker_sources(debs)

    install_cuda_drivers_repo(architecture, release, ubuntu)

    apt_update(fatal=True)

    # Actually install the required packages docker-ce nvidia-docker2.
    docker_ce = hookenv.config('docker-ce-package')
    nvidia_docker2 = hookenv.config('nvidia-docker-package')
    nv_container_runtime = hookenv.config('nvidia-container-runtime-package')
    apt_install(['cuda-drivers', docker_ce, nvidia_docker2,
                 nv_container_runtime], fatal=True)

    fix_docker_runtime_nvidia()


def install_from_custom_apt():
    """
    Install docker from custom repository.

    :return: None or False
    """
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


def install_cuda_drivers_repo(architecture, release, ubuntu):
    """
    Install cuda drivers this is xenial only.
    We want to install cuda-drivers only this means that the
    cuda version plays no role. Any repo will do.

    :param architecture: String
    :param release: String
    :param ubuntu: String
    :return: None
    """
    key_file = '7fa2af80.pub'

    # Distribution should be something like 'ubuntu1604'.
    distribution = '{}{}'.format(
        ubuntu,
        str(release).replace('.', '')
    )
    repository_path = \
        'developer.download.nvidia.com/compute/cuda/repos/{}/x86_64'.format(
            distribution
        )
    command = 'apt-key adv --fetch-keys http://{}/{}'.format(
        repository_path,
        key_file
    )
    check_call(split(command))

    cuda_repository_version = config('cuda_repo')
    cuda_repository_package = 'cuda-repo-{}_{}_{}.deb'.format(
        distribution,
        cuda_repository_version,
        architecture
    )
    repository_url = 'https://{}/{}'.format(
        repository_path,
        cuda_repository_package
    )

    r = requests.get(repository_url)
    r.raise_for_status()
    with open(cuda_repository_package, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)
    r.close()

    command = 'dpkg -i {}'.format(cuda_repository_package)
    check_call(split(command))


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


def write_docker_sources(debs):
    """
    Write docker.list under etc/apt/sources.list.d.

    :param debs: List String
    :return: None
    """
    # Run mkdir -p /etc/apt/sources.list.d.
    if not os.path.isdir('/etc/apt/sources.list.d'):
        os.makedirs('/etc/apt/sources.list.d')

    # Write the docker source file to the apt sources.list.d directory.
    with open('/etc/apt/sources.list.d/docker.list', 'w+') as stream:
        stream.write('\n'.join(debs))


def add_apt_key_url(url):
    """
    Add a key from a URL.

    :param url: String
    :return: None
    """
    curl_command = 'curl -s -L {}'.format(url).split()
    curl = Popen(curl_command, stdout=PIPE)
    apt_command = 'apt-key add -'.split()
    check_call(apt_command, stdin=curl.stdout)
    curl.wait()


def add_apt_key(key):
    """
    Enter the server and key in the apt-key management tool.

    :param key: String
    :return: None
    """
    keyserver = config('apt-key-server')
    http_proxy = config('http_proxy')
    cmd = 'apt-key adv --keyserver {0}'.format(keyserver)
    if http_proxy:
        cmd = '{0} --keyserver-options http-proxy={1}'.format(cmd, http_proxy)
    cmd = '{0} --recv-keys {1}'.format(cmd, key)

    # "apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80
    # --recv-keys 58118E89F3A912897C070ADBF76221572C52609D"
    check_call(split(cmd))


@when('docker.ready')
@when_not('cgroups.modified')
def enable_grub_cgroups():
    """
    :return: None
    """
    cfg = config()
    if cfg.get('enable-cgroups'):
        hookenv.log('Calling enable_grub_cgroups.sh and rebooting machine.')
        check_call(['scripts/enable_grub_cgroups.sh'])
        set_state('cgroups.modified')


@when('docker.ready')
@when_not('docker.available')
def signal_workloads_start():
    """
    Signal to higher layers the container runtime is ready to run
    workloads. At this time the only reasonable thing we can do
    is determine if the container runtime is active.

    :return: None
    """
    # Before we switch to active, probe the runtime to determine if
    # it is available for workloads. Assuming response from daemon
    # to be sufficient.
    if not _probe_runtime_availability():
        status_set('waiting', 'Container runtime not available.')
        return

    status_set('active', 'Container runtime available.')
    set_state('docker.available')


@when('sdn-plugin.available', 'docker.available')
def container_sdn_setup(sdn):
    """
    Receive the information from the SDN plugin, and render the docker
    engine options.

    :param sdn: SDNPluginProvider
    :return: None
    """
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
    """
    If this scenario of states is true, we have likely broken a
    relationship to our once configured SDN provider. This necessitates a
    cleanup of the Docker Options for BIP and MTU of the presumed dead SDN
    interface.

    :return: None
    """
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
    """
    Other layers should be able to trigger a daemon restart. Invoke the
    method that recycles the docker daemon.

    :return: None
    """
    recycle_daemon()
    remove_state('docker.restart')


@when('config.changed.docker-opts', 'docker.ready')
def docker_template_update():
    """
    The user has passed configuration that directly effects our running
    docker engine instance. Re-render the systemd files and recycle the
    service.

    :return: None
    """
    recycle_daemon()


@when('docker.ready', 'dockerhost.connected')
@when_not('dockerhost.configured')
def dockerhost_connected(dockerhost):
    """
    Transmits the docker url to any subordinates requiring it.

    :return: None
    """
    dockerhost.configure(Docker().socket)


@when('nrpe-external-master.available')
@when_not('nrpe-external-master.docker.initial-config')
def initial_nrpe_config():
    """
    :return: None
    """
    set_state('nrpe-external-master.docker.initial-config')
    update_nrpe_config()


@when('docker.ready')
@when('nrpe-external-master.available')
@when_any('config.changed.nagios_context',
          'config.changed.nagios_servicegroups')
def update_nrpe_config():
    """
    :return: None
    """
    # List of systemd services that will be checked.
    services = ['docker']

    # The current nrpe-external-master interface doesn't handle a lot of logic,
    # use the charm-helpers code for now.
    hostname = nrpe.get_nagios_hostname()
    current_unit = nrpe.get_nagios_unit_name()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe.add_init_service_checks(nrpe_setup, services, current_unit)
    nrpe_setup.write()


@when_not('nrpe-external-master.available')
@when('nrpe-external-master.docker.initial-config')
def remove_nrpe_config():
    """
    :return: None
    """
    remove_state('nrpe-external-master.docker.initial-config')

    # List of systemd services for which the checks will be removed.
    services = ['docker']

    # The current nrpe-external-master interface doesn't handle a lot of logic,
    # use the charm-helpers code for now.
    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname, primary=False)

    for service in services:
        nrpe_setup.remove_check(shortname=service)


class ConfigError(Exception):
    pass


def validate_config():
    """
    Check that config is valid.

    :return: None
    """
    max_line = 2048
    line_prefix_len = len('Environment="NO_PROXY=""')
    remain_len = max_line - line_prefix_len
    if len(config('no_proxy')) > remain_len:
        raise ConfigError('no_proxy longer than {} chars.'.format(remain_len))


def recycle_daemon():
    """
    Render the docker template files and restart the docker daemon on this
    system.

    :return: None
    """
    validate_config()
    hookenv.log('Restarting docker service.')

    # Re-render our docker daemon template at this time... because we're
    # restarting. And its nice to play nice with others. Isn't that nice?
    render_configuration_template(service=True)
    reload_system_daemons()
    host.service_restart('docker')

    if not _probe_runtime_availability():
        status_set('waiting', 'Container runtime not available.')
        return


def reload_system_daemons():
    """
    Reload the system daemons from on-disk configuration changes.

    :return: None
    """
    hookenv.log('Reloading system daemons.')
    lsb = host.lsb_release()
    code = lsb['DISTRIB_CODENAME']
    if code != 'trusty':
        command = ['systemctl', 'daemon-reload']
        check_call(command)
    else:
        host.service_reload('docker')


def _probe_runtime_availability():
    """
    Determine if the workload daemon is active and responding.

    :return: Boolean
    """
    try:
        command = ['docker', 'info']
        check_call(command)
        return True
    except CalledProcessError:
        # Remove the availability state if we fail reachability.
        remove_state('docker.available')
        return False


def _remove_docker_network_bridge():
    """
    By default docker uses the docker0 bridge for container networking.
    This method removes the default docker bridge, and reconfigures the
    DOCKER_OPTS to use the SDN networking bridge.

    :return: None
    """
    status_set('maintenance',
               'Reconfiguring container runtime network bridge.')
    host.service_stop('docker')
    apt_install(['bridge-utils'], fatal=True)

    # cmd = "ifconfig docker0 down"
    # ifconfig doesn't always work. use native linux networking commands to
    # mark the bridge as inactive.
    check_call(['ip', 'link', 'set', 'docker0', 'down'])
    check_call(['brctl', 'delbr', 'docker0'])

    # Render the config and restart docker.
    recycle_daemon()
