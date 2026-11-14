import unittest
from tehnet.discovery import discover
from tehnet.client import DeviceError

class DiscoveryTests(unittest.TestCase):
    def test_only_configured_private_candidates_are_checked(self):
        seen=[]
        class Probe:
            def __init__(self,address):seen.append(address);self.base=address
            def identity(self):return {'name':'ZLT P19H','version':'3.2.27','hwversion':'TZ7.821.183'} if self.base.endswith('.1') else {}
        found=discover(Probe,lambda:['8.8.8.8','127.0.0.1','192.168.10.1'])
        self.assertEqual(found.base,'http://192.168.10.1')
        self.assertEqual(seen,['http://192.168.0.254','http://192.168.10.1'])
    def test_no_network_range_scan_on_failure(self):
        seen=[]
        class Probe:
            def __init__(self,address):seen.append(address)
            def identity(self):return {}
        with self.assertRaises(DeviceError):discover(Probe,lambda:[])
        self.assertEqual(len(seen),1)
