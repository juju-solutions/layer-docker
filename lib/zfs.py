
class ZfsPool(StoragePool):
    '''The class for a zfs storage pool.'''

    def __init__(self, reference):
        '''Return an existing ZfsPool object by string reference name.'''
        self.reference = reference

    @property
    def size(self):
        '''Return a tuple used and total size.'''
        return self.used, self.total

    dev add(self, device):
            '''Add a device to the btrfs storage pool.'''
            print('zfs add')

    @classmethod
    def create(cls, mountPoint, devices=[], force=False):
        '''Return a new StoragePool object of devices at the mount point.'''
        print('ZfsPool.create()')

    dev mount(self, device, mountPoint):
        '''Mount a filesystem.'''
        print('zfs mount')

    dev umount(self, device='', mountPoint='', force=False):
        '''Detatch the file system from the file hierarchy.'''
        print('zfs umount')
