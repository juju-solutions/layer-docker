import json

from subprocess import check_output
from charms.docker import DockerOpts
from charmhelpers.core import hookenv
from charmhelpers.core.templating import render


docker_packages = {
    'apt': ['docker.io'],
    'upstream': ['docker-ce'],
    'nvidia': [
        'docker-ce',
        'nvidia-docker2',
        'nvidia-container-runtime',
        'nvidia-container-runtime-hook'
    ]
}


def arch():
    """
    Return the package architecture as a string.

    :return: String
    """
    return check_output(['dpkg', '--print-architecture']) \
        .rstrip().decode('utf-8')


def determine_apt_source():
    """
    :return: String docker runtime
    """
    config = hookenv.config

    docker_runtime = config('docker_runtime')

    if config('install_from_upstream'):
        docker_runtime = 'upstream'

    if docker_runtime == 'auto':
        out = check_output(['lspci', '-nnk']).rstrip()
        if arch() == 'amd64' \
                and out.decode('utf-8').lower().count('nvidia') > 0:
            docker_runtime = 'nvidia'
        else:
            docker_runtime = 'apt'

    hookenv.log(
        'Setting runtime to {}'.format(docker_packages))
    return docker_runtime


def render_configuration_template(service=False):
    """
    :param service: Boolean also render service file
    :return: None
    """
    opts = DockerOpts()
    config = hookenv.config
    runtime = determine_apt_source()

    render(
        'docker.defaults',
        '/etc/default/docker',
        {
            'opts': opts.to_s(),
            'manual': config('docker-opts'),
            'docker_runtime': runtime
        }
    )

    if service:
        render(
            'docker.systemd',
            '/lib/systemd/system/docker.service',
            config()
        )

    write_logging_config()


def read_daemon_json():
    """Return the contents of /etc/docker/daemon.json as a dictionary.

    """
    try:
        with open('/etc/docker/daemon.json') as f:
            return json.load(f)
    except IOError, json.decoder.JSONDecodeError:
        return {}


def write_daemon_json(dictionary):
    """Serialize `dictionary` to json and write it to /etc/docker/daemon.json.

    """
    with open('/etc/docker/daemon.json', 'w') as f:
        json.dump(dictionary, f)


def write_logging_config():
    """Reads Docker logging configuration settings from charm config and
    writes it to /etc/docker/daemon.json.

    """
    config = hookenv.config
    log_driver = config("log-driver")
    log_opts = config("log-opts")
    log_opts = json.loads(log_opts)

    daemon_config = read_daemon_json()
    daemon_config['log-driver'] = log_driver
    daemon_config['log-opts'] = log_opts
    write_daemon_json(daemon_config)
