import os
import shutil
import sys
import tempfile
import unittest

from shlex import split
from subprocess import check_call
from subprocess import check_output

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.zfs import ZfsPool

class TestZfs(unittest.TestCase):

    def setUp(self):
        '''Run the setup operations.'''
        self.directory = tempfile.mkdtemp()
        self.mount_point = tempfile.mkdtemp()
        self.devices = []
        # The command to create multiple images to mount zfs.
        image = 'dd if=/dev/zero of={0} bs=1M count=256'
        for a in range(3):
            output_file = '{0}/zfs{1}.img'.format(self.directory, str(a))
            print(image.format(output_file))
            # Create the files
            check_call(split(image.format(output_file)))
            self.devices.append(output_file)
        self.create_pool_name = 'test-zfs-pool'

        self.init_pool_name = 'additive-zfs-pool'
        cmd = 'sudo zpool create -m {0} {1} '.format(self.mount_point,
                                                     self.init_pool_name)
        cmd += ' '.join(self.devices)
        print(cmd)
        check_call(split(cmd))


    def testInit(self):
        '''Test the init method of the ZfsPool.'''
        pool = ZfsPool('additive-zfs-pool')
        for a in range(3):
            print(self.devices[a])
            pool.add(self.devices[a])
        cmd = 'sudo zpool list -H'
        output = check_output(split(cmd))
        assert(self.init_pool_name in output, 'Pool name not in listing')
        destroy = 'sudo zpool destroy -f {0}'.format(self.init_pool_name)
        check_call(split(destroy))

    def testCreate(self):
        '''Test the create model of the ZfsPool.'''
        pool = ZfsPool.create(self.mount_point, self.devices)
        cmd = 'sudo zpool list -H'
        output = check_output(split(cmd))
        assert(self.create_pool_name in output, 'Pool name not in listing')
        destroy = 'sudo zpool destroy -f {0}'.format(self.create_pool_name)
        check_call(split(destroy))

    def tearDown(self):
        '''Remove the files.'''
        # Delete the directory of temporary files.
        shutil.rmtree(self.directory)
        # Delete the mount point directory.
        shutil.rmtree(self.mount_point)
