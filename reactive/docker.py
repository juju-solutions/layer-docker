import os
from subprocess import check_call

from charmhelpers.core import hookenv

from charms import reactive
from charms.reactive import hook


@hook('install')
def install():
    hookenv.status_set('maintenance', 'Installing Docker and AUFS')
    # Using getenv will return '' if CHARM_DIR is not an environment variable.
    charm_path = os.getenv('CHARM_DIR', '')
    install_script_path = os.path.join(charm_path, 'scripts/install_docker.sh')
    check_call([install_script_path])
    # Install pip.
    check_call(['apt-get', 'install', '-y', 'python-pip'])
    # Pip install docker-compose.
    check_call(['pip', 'install', '-U', 'docker-compose'])
    # Leave a status message that Docker is installed.
    hookenv.status_set('active', 'Docker Installed')
    reactive.set_state('docker.available')
