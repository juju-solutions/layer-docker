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
