from storagepool import StoragePool
from subprocess import check_call
from subprocess import check_output
import os


class BtrfsPool(StoragePool):
    '''The class for a btrfs storage pool.'''

    def __init__(self, reference, strict=True):
        '''Return an existing BtrfsPool object by string reference name.'''
        self.mountpoint = reference
        if not os.path.exists(self.mountpoint) and strict:
            raise OSError("Mountpoint {} does not exist".format(reference))

        print("Initialized with:")
        print("Mountpoint: {}".format(self.mountpoint))
        print("Known Devices: {}".format(self.mounted_devices))

    @property
    def mounted_devices(self):
        ''' Parse the btrfs filesystem output to determine what devices
        are already participating in the storage pool '''
        # Label: none  uuid: 4b093691-9e6d-44ce-84cf-7c6d832dde86
        # Total devices 2 FS bytes used 256.00KiB
        # devid    1 size 1.00GiB used 240.00MiB path /dev/sdc
        # devid    2 size 1.00GiB used 448.00MiB path /dev/sdd
        mounted_devices = []
        cmd = ['btrfs', 'filesystem', 'show', '-m']
        fsout = check_output(cmd)
        for line in fsout.split('\n'):
            # lots of headers and other info we dont care about...
            if '/dev/' not in line:
                continue
            # Parse out the last bit on the line, which is the device
            mounted_devices.append(line.split()[7])

        return mounted_devices

    @classmethod
    def create(cls, mountPoint, devices=[]):
        '''Return a new StoragePool object of devices at the mount point.'''
        print('BtrfsPool.create()')
        o = cls(mountPoint)
        o.devices = devices

        cmd = ['mkfs.btrfs', '-f', '-d', 'raid5']
        for dev in o.devices:
            cmd.append(dev)
        # abandon all hope, data of the devices initializing this pool
        check_call(cmd)
        return o

    def add(self, device):
        '''Add a device to the btrfs storage pool.'''
        print('btrfs add')
        if device in self.mounted_devices:
            return
        cmd = ['btrfs', 'device', 'add', '-f', device, self.mountpoint]
        check_call(cmd)

    def mount(self):
        '''Mount a filesystem.'''
        print('btrfs mount')
        # BTRFS doesn't care which disk we choose, so use any identifier from
        # the btrfs pool to mount the fs
        if not os.path.exists(self.mountpoint):
            os.makedirs(self.mountpoint)
        mount_cmd = ['mount', '-t', 'btrfs', self.devices[0], self.mountpoint]
        check_call(mount_cmd)

    def rebalance(self):
        ''' Rebalance the disks by distributing striped data among the
        devices participating in the pool. '''
        print('btrfs rebalance')
        cmd = ['btrfs', 'balance', self.mountpoint]
        check_call(cmd)

    def umount(self):
        print('btrfs unmount')
        print(self.mountpoint)
        cmd = ['umount', self.mountpoint]
        check_call(cmd)
