import ipaddress
import json

from subprocess import check_output
from charms.docker import DockerOpts
from charmhelpers.core import hookenv
from charmhelpers.core import unitdata
from charmhelpers.core.templating import render

docker_packages = {
    "apt": ["docker.io"],
    "upstream": ["docker-ce"],
    "nvidia": [
        "docker-ce",
        "nvidia-docker2",
        "nvidia-container-runtime",
        "nvidia-container-runtime-hook",
    ],
}


def arch():
    """
    Return the package architecture as a string.

    :return: String
    """
    return check_output(["dpkg", "--print-architecture"]).rstrip().decode("utf-8")


def determine_apt_source():
    """
    :return: String docker runtime
    """
    config = hookenv.config

    docker_runtime = config("docker_runtime")

    if config("install_from_upstream"):
        docker_runtime = "upstream"

    if docker_runtime == "auto":
        out = check_output(["lspci", "-nnk"]).rstrip()
        if arch() == "amd64" and out.decode("utf-8").lower().count("nvidia") > 0:
            docker_runtime = "nvidia"
        else:
            docker_runtime = "apt"

    hookenv.log("Setting runtime to {}".format(docker_packages))
    return docker_runtime


def render_configuration_template(service=False):
    """
    :param service: Boolean also render service file
    :return: None
    """
    opts = DockerOpts()
    config = hookenv.config

    environment_config = hookenv.env_proxy_settings()
    modified_config = dict(config())
    parsed_hosts = ""
    if environment_config is not None:
        hosts = []
        for address in environment_config.get("NO_PROXY", "").split(","):
            address = address.strip()
            try:
                net = ipaddress.ip_network(address)
                ip_addresses = [str(ip) for ip in net.hosts()]
                if ip_addresses == []:
                    hosts.append(address)
                else:
                    hosts += ip_addresses
            except ValueError:
                hosts.append(address)
        parsed_hosts = ",".join(hosts)
        environment_config.update({"NO_PROXY": parsed_hosts, "no_proxy": parsed_hosts})
        for key in ["http_proxy", "https_proxy", "no_proxy"]:
            if not modified_config.get(key):
                modified_config[key] = environment_config.get(key)

    runtime = determine_apt_source()

    render(
        "docker.defaults",
        "/etc/default/docker",
        {
            "opts": opts.to_s(),
            "manual": config("docker-opts"),
            "docker_runtime": runtime,
        },
    )

    if service:
        render("docker.systemd", "/lib/systemd/system/docker.service", modified_config)

    write_daemon_json()


def write_daemon_json():
    """Reads Docker daemon options from `daemon-opts` charm config and
    writes them to /etc/docker/daemon.json.

    :return: The dict written to /etc/docker/daemon.json

    """
    daemon_opts = hookenv.config("daemon-opts")
    daemon_opts = json.loads(daemon_opts)

    kv = unitdata.kv()
    daemon_opts_additions = kv.get("daemon-opts-additions", default={})

    # Merge the key/vals from charm config into those set by the charm.
    # If there are any shared keys, we want the value from charm config to win.
    daemon_opts_additions.update(daemon_opts)

    with open("/etc/docker/daemon.json", "w") as f:
        json.dump(daemon_opts_additions, f)

    return daemon_opts_additions


def set_daemon_json(key, value):
    """Set a key/value pair in /etc/docker/daemon.json.

    The contents of /etc/docker/daemon.json are controlled by the `daemon-opts`
    charm config, which is set by the Juju operator. This function provides a
    way for the charm itself to augment the contents of that file.

    Only keys that don't exist in `daemon-opts` can be written. In other words,
    this function can not update the values of keys that already exist in the
    `daemon-opts` charm config value.

    The update will succeed if:
    - The key does not already exist in `daemon-opts`
    - The key does exist in `daemon-opts`, but its value matches `value`

    :param key str: The key to add to daemon.json
    :param value: The value for `key`; can be any json-serializable type
    :return: If the update succeeds, returns the dict written to
      /etc/docker/daemon.json; otherwise returns False

    """
    daemon_opts = hookenv.config("daemon-opts")
    daemon_opts = json.loads(daemon_opts)

    existing_value = daemon_opts.get(key)
    if existing_value and existing_value != value:
        return False

    kv = unitdata.kv()
    daemon_opts_additions = kv.get("daemon-opts-additions", default={})
    daemon_opts_additions[key] = value
    kv.set("daemon-opts-additions", daemon_opts_additions)
    kv.flush()

    return write_daemon_json()


def delete_daemon_json(key):
    """Delete a key (and its value) from /etc/docker/daemon.json.

    Only keys that have been set with ``update_daemon_json()`` can be deleted.

    :param key string: The key to delete
    :return: Returns False if the key doesn't exist, otherwise True

    """
    kv = unitdata.kv()
    daemon_opts_additions = kv.get("daemon-opts-additions", default={})

    if key not in daemon_opts_additions:
        return False

    daemon_opts_additions.pop(key)
    kv.set("daemon-opts-additions", daemon_opts_additions)
    kv.flush()
    write_daemon_json()

    return True
