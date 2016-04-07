import unittest

from btrfs import BtrfsPool
from mock import patch


class TestBtrfsPool(unittest.TestCase):

    def testCreate(self):
        with patch('btrfs.check_call') as bcc:
            # test raid5
            BtrfsPool.create(devices=['/dev/none0',
                                      '/dev/none1',
                                      '/dev/none2'],
                             mountPoint='/tmp')
            bcc.assert_called_with(['mkfs.btrfs', '-f', '-d', 'raid5',
                                    '/dev/none0', '/dev/none1', '/dev/none2'])

    def testAdd(self):
        bpool = BtrfsPool('/tmp/none', False)
        with patch('btrfs.check_call') as bcc:
            bpool.add('/dev/none0')
            bcc.assert_called_with(['btrfs', 'device', 'add', '-f',
                                    '/dev/none0', '/tmp/none'])

    def testRebalance(self):
        bpool = BtrfsPool('/tmp/none', False)
        with patch('btrfs.check_call') as bcc:
            bpool.rebalance()
            bcc.assert_called_with(['btrfs', 'balance', '/tmp/none'])

    def test_mounted_devices(self):
        stat = 'Label: none  uuid: 4b093691-9e6d-44ce-84cf-7c6d832dde86\n' \
               'Total devices 2 FS bytes used 256.00KiB\n' \
               'devid    1 size 1.00GiB used 240.00MiB path /dev/sdc\n' \
               'devid    2 size 1.00GiB used 448.00MiB path /dev/sdd\n'

        with patch('btrfs.check_output') as bco:
            bco.return_value = stat
            bpool = BtrfsPool('/tmp/none', False)
            self.assertTrue('/dev/sdc' in bpool.mounted_devices)
            self.assertTrue('/dev/sdd' in bpool.mounted_devices)

    def test_mount(self):
        with patch('btrfs.check_call') as bcc:
            bpool = BtrfsPool.create(devices=['/dev/none0',
                                              '/dev/none1',
                                              '/dev/none2'],
                                     mountPoint='/tmp')
            bpool.mount()
            bcc.assert_called_with(['mount', '-t', 'btrfs', '/dev/none0',
                                    '/tmp'])
