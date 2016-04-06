from storagepool import StoragePool
from subprocess import check_call


class BtrfsPool(StoragePool):
    '''The class for a btrfs storage pool.'''

    def __init__(self, reference=None):
        '''Return an existing BtrfsPool object by string reference name.'''
        self.reference = reference

    @property
    def size(self):
        '''Return a tuple used and total size.'''
        return self.used, self.total

    @classmethod
    def create(cls, mountPoint, devices=[], force=False):
        '''Return a new StoragePool object of devices at the mount point.'''
        print('BtrfsPool.create()')
        o = cls()
        cls.devices = devices
        cls.mountpoint = mountPoint

        if len(cls.devices) == 2:
            # Raid1 settings
            raid_type = 'raid1'
        elif len(cls.devices) >= 3:
            # Raid5 settings
            raid_type = 'raid5'
        else:
            # Raid0 settings
            raid_type = 'raid0'

        cmd = ['mkfs.btrfs', '-f', '-d', raid_type]
        for dev in cls.devices:
            cmd.append(dev)
        # abandon all hope, data of the devices initializing this pool
        check_call(cmd)

        o.mount(devices, mountPoint)
        return o

    def add(self, device, mountpoint):
        '''Add a device to the btrfs storage pool.'''
        print('btrfs add')
        cmd = ['btrfs', 'device', 'add', '-f', device, mountpoint]
        check_call(cmd)
        print('btrfs balance')
        cmd = ['btrfs', 'balance', mountpoint]
        check_call(cmd)

    def mount(self, device, mountPoint):
        '''Mount a filesystem.'''
        print('btrfs mount')
        # BTRFS doesn't care which disk we choose, so use any identifier from
        # the btrfs pool to mount the fs
        mount_cmd = ['mount', '-t', 'btrfs', device[0], mountPoint]
        check_call(mount_cmd)

    def umount(self, device='', mountPoint='', force=False):
        '''Detatch the file system from the file hierarchy.'''
        print('btrfs umount')
