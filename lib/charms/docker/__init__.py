import os
import subprocess

from contextlib import contextmanager
from shlex import split

from workspace import Workspace

# Wrapper and convenience methods for charming w/ docker in python
class Docker:
    '''
    Wrapper class to communicate with the Docker daemon on behalf of
    a charmer. Provides stateless operations of a running docker daemon
    '''

    def __init__(self, socket="unix:///var/run/docker.sock", workspace=None):
        '''
        @param socket - URI to the Docker daemon socket
            default: unix://var/run/docker.sock

        @param workspace - Path to directory containing a Dockerfile
            default: None
        '''
        self.socket = socket
        if workspace:
            self.workspace = Workspace(workspace)

    def running(self):
        '''
        Predicate method to determine if the daemon we are talking to is
        actually online and recieving events.

        ex: bootstrap = Docker(socket="unix://var/run/docker-boostrap.sock")
        bootstrap.running()
        > True
        '''
        # TODO: Add TCP:// support for running check
        return os.path.isfile(self.socket)

    def run(self, image, options="", volumes=[], ports=[]):
        volumes = " --volume=".join(volumes)
        ports = " -p".join(ports)
        cmd = "docker run {opts} {vols} {ports} {image}".format(
            opts=options, vols=volumes, ports=ports, image=image)

        try:
            subprocess.check_output(split(cmd))
        except subprocess.CalledProcessError as expec:
            print "Error: ", expect.returncode, expect.output
