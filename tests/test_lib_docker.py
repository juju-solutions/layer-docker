import tempfile

from charms.layer.docker import read_daemon_json
from charms.layer.docker import write_daemon_json
from charms.layer.docker import write_logging_config


def test_read_daemon_json_no_file():
    assert read_daemon_json(path='file-does-not-exist') == {}


def test_read_daemon_json_invalid_contents():
    with tempfile.NamedTemporaryFile() as f:
        assert read_daemon_json(f.name) == {}


def test_read_daemon_json_valid_contents():
    with tempfile.NamedTemporaryFile() as f:
        f.write(b'{"log-driver": "json-file"}')
        f.seek(0)
        assert read_daemon_json(f.name) == {'log-driver': 'json-file'}


def test_write_daemon_json():
    d = {'log-driver': 'json-file'}
    with tempfile.NamedTemporaryFile() as f:
        write_daemon_json(d, f.name)
        assert d == read_daemon_json(f.name)


def test_write_logging_config():
    config = {
        "log-driver": "json-file",
        "log-opts": '{"max-size": "10m", "max-file": "100"}',
    }

    def mock_config(key):
        return config[key]

    expected = {
        "log-driver": "json-file",
        "log-opts": {"max-size": "10m", "max-file": "100"},
    }
    with tempfile.NamedTemporaryFile() as f:
        write_logging_config(mock_config, f.name)
        assert read_daemon_json(f.name) == expected
