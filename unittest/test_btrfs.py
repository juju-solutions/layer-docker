import unittest

from btrfs import BtrfsPool
from mock import patch


class TestBtrfsPool(unittest.TestCase):

    def testCreate(self):
        with patch('btrfs.check_call') as bcc:
            # test raid0
            BtrfsPool.create(devices=['/dev/none'], mountPoint='/tmp')
            bcc.assert_called_with(['mkfs.btrfs', '-f', '-d', 'raid0',
                                    '/dev/none'])
            # test raid1
            BtrfsPool.create(devices=['/dev/none0',
                                      '/dev/none1'], mountPoint='/tmp')
            bcc.assert_called_with(['mkfs.btrfs', '-f', '-d', 'raid1',
                                    '/dev/none0', '/dev/none1'])
            # test raid5
            BtrfsPool.create(devices=['/dev/none0',
                                      '/dev/none1',
                                      '/dev/none2'],
                             mountPoint='/tmp')
            bcc.assert_called_with(['mkfs.btrfs', '-f', '-d', 'raid5',
                                    '/dev/none0', '/dev/none1', '/dev/none2'])

    def testAdd(self):
        bpool = BtrfsPool()
        with patch('btrfs.check_call') as bcc:
            bpool.add('/dev/none0', '/tmp/none')
            bcc.assert_called_with(['btrfs', 'device', 'add', '-f',
                                    '/dev/none0', '/tmp/none'])

    def testRebalance(self):
        bpool = BtrfsPool()
        with patch('btrfs.check_call') as bcc:
            bpool.rebalance('/tmp/none')
            bcc.assert_called_with(['btrfs', 'balance', '/tmp/none'])
