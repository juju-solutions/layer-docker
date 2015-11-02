from lib.charms.docker import Docker
from lib.charms import docker
from mock import patch
import pytest

class TestDocker:

    @pytest.fixture
    def docker(self):
        return Docker()


    # There's a pattern to run an isolated docker daemon to run supporting
    # infrastructure of the primary docker daemon. This bootstrap daemon
    # runs host only on a socket
    @pytest.fixture
    def bootstrap(self):
        return Docker(socket="unix:///var/run/docker-bootstrap.sock")

    def test_docker_init_defaults(self, docker):
        docker.socket = "unix:///var/run/docker.sock"

    def test_docker_init_socket(self):
        docker = Docker(socket="tcp://127.0.0.1:2357")
        assert docker.socket == "tcp://127.0.0.1:2357"

    def test_docker_init_workspace(self):
        devel = Docker(workspace="files/tmp")
        assert "{}".format(devel.workspace) == "files/tmp"

    def test_running(self, bootstrap):
        with patch('os.path.isfile') as isfilemock:
            isfilemock.return_value = True
            assert bootstrap.running() is True

    def test_run(self, docker):
        with patch('subprocess.check_output') as spmock:
            docker.run('nginx')
            spmock.assert_called_with(['docker', 'run', 'nginx'])
            docker.run('nginx', '-d --name=nginx')
            spmock.assert_called_with(['docker', 'run', '-d', '--name=nginx',
             'nginx'])
