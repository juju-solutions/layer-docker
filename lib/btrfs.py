
class BtrfsPool(StoragePool):
    '''The class for a btrfs storage pool.'''

    def __init__(self, reference):
        '''Return an existing BtrfsPool object by string reference name.'''
        self.reference = reference

    @property
    def size(self):
        '''Return a tuple used and total size.'''
        return self.used, self.total

    dev add(self, device):
            '''Add a device to the btrfs storage pool.'''
            print('btrfs add')

    @classmethod
    def create(cls, mountPoint, devices=[], force=False):
        '''Return a new StoragePool object of devices at the mount point.'''
        print('BtrfsPool.create()')

    dev mount(self, device, mountPoint):
        '''Mount a filesystem.'''
        print('btrfs mount')

    dev umount(self, device='', mountPoint='', force=False):
        '''Detatch the file system from the file hierarchy.'''
        print('btrfs umount')
