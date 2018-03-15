#!/usr/bin/python3

# This is a very basic test for this layer to make sure docker is installed.

import amulet
import unittest

seconds = 1100


class TestDeployment(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Perform a one time setup for this class deploying the charms."""
        cls.deployment = amulet.Deployment(series='xenial')

        cls.deployment.add('docker')

        try:
            cls.deployment.setup(timeout=seconds)
            cls.deployment.sentry.wait()
        except amulet.helpers.TimeoutError:
            message = "The deploy did not setup in {0} seconds".format(seconds)
            amulet.raise_status(amulet.SKIP, msg=message)

        cls.unit = cls.deployment.sentry['docker'][0]

    def test_docker_binary(self):
        """Verify that the docker binary is installed, on the path and is
        functioning properly for this architecture."""
        # dockerbeat -version
        output, code = self.unit.run('docker --version')
        print(output)
        if code != 0:
            message = 'Docker unable to return version.'
            amulet.raise_status(amulet.FAIL, msg=message)
        # dockerbeat -devices
        output, code = self.unit.run('docker info')
        print(output)
        if code != 0:
            message = 'Docker unable to return system information.'
            amulet.raise_status(amulet.FAIL, msg=message)


if __name__ == '__main__':
    unittest.main()
