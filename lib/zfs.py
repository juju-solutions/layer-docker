import os

from shlex import split
from subprocess import check_call
from subprocess import check_output

from storagepool import StoragePool

class ZfsPool(StoragePool):
    '''The class for a zfs storage pool.'''

    def __init__(self, reference):
        '''Return an existing ZfsPool object by string reference name.'''
        self.reference = reference

        cmd = 'sudo zfs get -H mountpoint {0}'.format(self.reference)
        output = check_output(split(cmd))
        if output:
            # NAME PROPERTY VALUE SOURCE
            self.mountPoint = output.split()[2]


    @classmethod
    def create(cls, mountPoint, devices=[], force=False):
        '''Return a new StoragePool object of devices at the mount point.'''
        self.reference = 'zfs-pool'
        # The mount point must be an absolute path.
        self.mountPoint = os.path.abspath(mountPoint)
        self.devices = devices
        if len(self.devices) > 2:
            # There are enough devices, so create a raidz pool.
            cmd = 'sudo zpool create -m {0} {1} raidz '.format(self.mountPoint,
                                                               self.reference)
            cmd += ' '.join(self.devices)
            # Create the zfs pool with raidz.
            check_call(split(cmd))
        else:
            # Create a normal zfs pool.
            cmd = 'sudo zpool create -m {0} {1}'.format(self.mountPoint,
                                                        self.reference)
            cmd += ' '.join(self.devices)
            # Create a normal zfs pool.
            check_call(split(cmd))


    @property
    def size(self):
        '''Return a string tuple of used and total size of the storage pool.'''
        # Create a command to get the details of the storage pool (no header).
        cmd = 'sudo zfs list -H ' + self.reference
        output = check_output(split(cmd))
        if output:
            # NAME USED AVAIL REFER MOUNTPOINT
            self.used = str(line.split()[1])
            self.total = str(line.split()[2])
        # Return a tuple of used and available for this pool.
        return self.used, self.total


    def add(self, device):
        '''Add a device to the zfs storage pool.'''
        if self.reference:
            cmd = 'sudo zpool add {0} {1}'.format(self.reference, device)
            check_call(split(cmd))
        else:
            print('No pool name set.')


    def mount(self, mountPoint):
        '''Mount the zfs pool as a file system at the mount point.'''
        # Create the command to mount the zfs pool at a specific mount point.
        if self.reference:
            # Create the command to mount the zfs pool at a specific mount point.
            cmd = 'zfs set mountpoint={0} {1}'.format(mountPoint, self.reference)
            check_call(split(cmd))


    def umount(self, mountPoint, force=False):
        '''Detatch the file system from the file hierarchy.'''
        cmd = 'zfs unmount {0} {1}'.format('-f' if force else '', mountPoint)
        check_call(split(cmd))
