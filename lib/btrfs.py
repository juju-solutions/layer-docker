from storagepool import StoragePool
from storagepool import ToolsNotFound
from subprocess import check_call
from subprocess import CalledProcessError


class BtrfsPool(StoragePool):
    '''The class for a btrfs storage pool.'''

    def __init__(self, reference=None):
        '''Return an existing BtrfsPool object by string reference name.'''
        # Ensure we have BTRFS tools installed before we do *anything*
        self.__tool_check()
        self.reference = reference

    @property
    def size(self):
        '''Return a tuple used and total size.'''
        return self.used, self.total

    @classmethod
    def create(cls, mountPoint, devices=[], force=False):
        '''Return a new StoragePool object of devices at the mount point.'''
        print('BtrfsPool.create()')
        cls.__tool_check()
        cls.devices = devices
        cls.mountpoint = mountPoint

        if len(cls.devices) == 2:
            # Raid1 settings
            pass
        elif len(cls.devices) >= 3:
            # Raid5 settings
            pass
        else:
            # Raid0 settings
            pass

    def __tool_check(self):
        cmd = ['which', 'btrfs']
        try:
            check_call(cmd)
        except CalledProcessError:
            # Handle the user not having BTRFS-Tools installed
            raise ToolsNotFound('Missing package btrfs-tools')

    def add(self, device):
        '''Add a device to the btrfs storage pool.'''
        print('btrfs add')

    def mount(self, device, mountPoint):
        '''Mount a filesystem.'''
        print('btrfs mount')

    def umount(self, device='', mountPoint='', force=False):
        '''Detatch the file system from the file hierarchy.'''
        print('btrfs umount')
