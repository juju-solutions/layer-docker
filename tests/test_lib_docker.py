import json

from unittest.mock import mock_open
from unittest.mock import patch

from charms.layer.docker import write_daemon_json
from charms.layer.docker import set_daemon_json
from charms.layer.docker import delete_daemon_json


@patch("charmhelpers.core.unitdata.kv")
@patch("charmhelpers.core.hookenv.config")
def test_write_daemon_json(config, kv):
    daemon_opts = {
        "log-driver": "json-file",
        "log-opts": {"max-size": "10m", "max-file": "100"},
    }

    daemon_opts_additions = {
        "log-driver": "this-will-be-overwritten",
        "my-extra-config": "this-will-be-preserved",
    }

    charm_config = {"daemon-opts": json.dumps(daemon_opts)}

    def mock_config(key):
        return charm_config[key]

    config.side_effect = mock_config
    kv.return_value.get.return_value = daemon_opts_additions

    with patch("builtins.open", mock_open(), create=True):
        daemon_opts_additions.update(daemon_opts)
        result = write_daemon_json()
        assert result == daemon_opts_additions


@patch("charmhelpers.core.hookenv.config")
def test_set_daemon_json(config):
    daemon_opts = {
        "log-driver": "json-file",
        "log-opts": {"max-size": "10m", "max-file": "100"},
    }

    charm_config = {"daemon-opts": json.dumps(daemon_opts)}

    def mock_config(key):
        return charm_config[key]

    config.side_effect = mock_config

    # Test that charm can't override a config value
    assert set_daemon_json("log-driver", "new value") is False

    with patch("builtins.open", mock_open(), create=True):
        result = set_daemon_json("log-driver", "json-file")
        assert result["log-driver"] == "json-file"
        result = set_daemon_json("my-extra-config", "value")
        assert result["my-extra-config"] == "value"


@patch("charmhelpers.core.unitdata.kv")
def test_delete_daemon_json(kv):
    daemon_opts_additions = {"foo": "bar"}

    with patch("charms.layer.docker.write_daemon_json"):
        kv.return_value.get.return_value = {}
        assert delete_daemon_json("foo") is False

        kv.reset_mock()
        kv.return_value.get.return_value = daemon_opts_additions
        assert delete_daemon_json("foo") is True
        kv().set.assert_called_once_with("daemon-opts-additions", {})
