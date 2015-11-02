import os

from contextlib import contextmanager
from shlex import split
from subprocess import check_output
from workspace import Workspace

# Wrapper and convenience methods for charming w/ docker compose in python
class Compose:
    def __init__(self, workspace, strict=True):
        '''
        Object to manage working with Docker-Compose on the CLI. exposes
        a natural language for performing common tasks with docker in
        juju charms.

        @param workspace - Define the CWD for docker-compose execution

        @param strict - Enable/disable workspace validation
        '''
        self.workspace = Workspace(workspace)
        if strict:
            self.workspace.validate()

    def up(self, service=None):
        '''
        Convenience method that wraps `docker-compose up`

        usage: c.up('nginx')  to start the 'nginx' service from the
        defined `docker-compose.yml` as a daemon
        '''
        if service:
            cmd = "docker-compose up -d {}".format(service)
        else:
            cmd = "docker-compose up -d"
        self.run(cmd)

    def kill(self, service=None):
        '''
        Convenience method that wraps `docker-compose kill`

        usage: c.kill('nginx')  to kill the 'nginx' service from the
        defined `docker-compose.yml`
        '''
        if service:
            cmd = "docker-compose kill {}".format(service)
        else:
            cmd = "docker-compose kill"
        self.run(cmd)

    def run(self, cmd):
        '''
        chdir sets working context on the workspace

        @param: cmd - String of the command to run. eg: echo "hello world"
        the string is passed through shlex.parse() for convenience.

        returns STDOUT of command execution

        usage: c.run('docker-compose ps')
        '''
        with chdir("{}".format(self.workspace)):
            out = check_output(split(cmd))
            return out


# This is helpful for setting working directory context
@contextmanager
def chdir(path):
    '''Change the current working directory to a different directory to run
    commands and return to the previous directory after the command is done.'''
    old_dir = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(old_dir)
