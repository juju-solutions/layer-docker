import json
import tempfile

from charms.layer.docker import write_daemon_json
from charms.reactive import is_state


def test_write_daemon_json():
    # Test the case where nvidia runtime is not being used.
    # The daemon-opts in the config should match what gets
    # written to the json file.

    is_state.return_value = False
    daemon_opts = {
        "log-driver": "json-file",
        "log-opts": {
          "max-size": "10m",
          "max-file": "100"
        }
    }

    with_nvidia = daemon_opts.copy()
    with_nvidia['default-runtime'] = 'nvidia'

    config = {
        "daemon-opts": json.dumps(daemon_opts)
    }

    def mock_config(key):
        return config[key]

    with tempfile.NamedTemporaryFile() as f:
        write_daemon_json(mock_config, f.name)
        f.seek(0)
        assert json.loads(f.read().decode('utf8')) == daemon_opts

    # Test the case where nvidia runtime is being used.
    # The config written to the json file should contain
    # default-runtime=nvidia, even if that wasn't explicitly
    # in the daemon-opts config.

    is_state.return_value = True
    with tempfile.NamedTemporaryFile() as f:
        write_daemon_json(mock_config, f.name)
        f.seek(0)
        assert json.loads(f.read().decode('utf8')) == with_nvidia
