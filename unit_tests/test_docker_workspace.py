from lib.charms.docker.workspace import Workspace
import pytest
from mock import patch

class TestDockerOpts:

    def test_init_docker_sets_context_to_compose(self):
        w = Workspace("/tmp/docker-test")
        assert w.path is "/tmp/docker-test"
        assert w.context is "compose"

    def test_init_docker_sets_context_to_docker(self):
        w = Workspace("/tmp/docker-test", context="docker")
        assert w.path is "/tmp/docker-test"
        assert w.context is "docker"

    def test_invalid_workspace(self):
        w = Workspace("/tmp/docker-test")
        with pytest.raises(OSError):
            w.validate()

    def test_invalid_docker_workspace(self):
        w = Workspace("/tmp/docker-test", context="docker")
        with pytest.raises(OSError):
            w.validate()

    def test_to_string(self):
        w = Workspace("/tmp/docker-test")
        assert "{}".format(w) == "/tmp/docker-test"

    def test_valid_workspace(self):
        with patch('os.path.isfile') as m:
            m.return_value = True
            w = Workspace("/tmp/docker-test")
            assert w.validate() is True
