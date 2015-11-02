from lib.charms.docker.compose import Compose
from lib.charms.docker import compose
from mock import patch
import pytest

class TestCompose:

    # This has limited usefulness, it fails when used with the @patch
    # decorator. simply pass in compose to any object to gain the
    # test fixture
    @pytest.fixture
    def compose(self):
        return Compose('files/test', strict=False)

    def test_init_strict(self):
        with patch('lib.charms.docker.compose.Workspace.validate') as f:
            c = Compose('test', strict=True)
            # Is this the beast? is mock() doing the right thing here?
            f.assert_called_with()

    def test_init_workspace(self, compose):
        assert "{}".format(compose.workspace) == "files/test"

    def test_start_service(self, compose):
        with patch('lib.charms.docker.compose.Compose.run') as s:
            compose.start_service('nginx')
            expect = 'docker-compose up -d nginx'
            s.assert_called_with(expect)

    def test_start_default_formation(self, compose):
        with patch('lib.charms.docker.compose.Compose.run') as s:
            compose.start_service()
            expect = 'docker-compose up -d'

    def test_kill_service(self, compose):
        with patch('lib.charms.docker.compose.Compose.run') as s:
            compose.kill_service('nginx')
            expect = 'docker-compose kill nginx'

    def test_kill_service(self, compose):
        with patch('lib.charms.docker.compose.Compose.run') as s:
            compose.kill_service()
            expect = 'docker-compose kill'

    @patch('lib.charms.docker.compose.chdir')
    @patch('lib.charms.docker.compose.check_call')
    def test_run(self, ccmock, chmock):
        compose = Compose('files/workspace', strict=False)
        compose.start_service('nginx')
        chmock.assert_called_with('files/workspace')
        ccmock.assert_called_with(['docker-compose', 'up', '-d', 'nginx'])

    # This test is a little ugly but is a byproduct of testing the callstack.
    @patch('os.getcwd')
    def test_context_manager(self, cwdmock):
        cwdmock.return_value = '/tmp'
        with patch('os.chdir') as chmock:
            compose = Compose('files/workspace', strict=False)
            with patch('lib.charms.docker.compose.check_call'):
                compose.start_service('nginx')
                # We can only test the return called with in this manner.
                # So check that we at least reset context
                chmock.assert_called_with('/tmp')
                # TODO: test that we've actually tried to change dir context
