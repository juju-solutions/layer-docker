import os

from contextlib import contextmanager
from shlex import split
from subprocess import check_call

# Wrapper and convenience methods for charming w/ docker compose in python
class Compose:
    def __init__(self, workspace):
        self.workspace = workspace
        self.validate_workspace()

    def start_service(self, service=None):
        if service:
            cmd = "docker-compose up -d {}".format(service)
        else:
            cmd = "docker-compose up -d"
        self.run(cmd)

    def kill_service(self, service=None):
        if service:
            cmd = "docker-compose kill -d {}".format(service)
        else:
            cmd = "docker-compose kill"
        self.run(cmd)

    def run(self, cmd):
        with chdir(self.workspace):
            check_call(split(cmd))


    def validate_workspace(self):
        dcyml = os.path.isfile("{}/docker-compose.yml".format(self.workspace))
        dcyaml = os.path.isfile("{}/docker-compose.yaml".format(self.workspace))
        if not dcyml and not dcyaml:
            raise OSError("docker-compose.yml not found in workspace")

# This is helpful for setting working directory context
@contextmanager
def chdir(path):
    '''Change the current working directory to a different directory to run
    commands and return to the previous directory after the command is done.'''
    old_dir = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(old_dir)
