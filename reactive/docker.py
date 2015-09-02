import os
from subprocess import check_call

try:
    from path import path
except:
    check_call(['apt-get', 'install', '-y', 'python-pip'])
    check_call(['pip', 'install', 'path.py'])
    from path import path

from charmhelpers.core import hookenv

from charms import reactive
from charms.reactive import hook


@hook('install')
def install():
    hookenv.status_set('maintenance', 'Installing Docker and AUFS')
    charm_path = path(os.environ['CHARM_DIR'])
    install_script_path = charm_path/'scripts/install_docker.sh'
    check_call([install_script_path])
    hookenv.status_set('active', 'Docker Installed')
    reactive.set_state('docker.available')
