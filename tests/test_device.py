import hashlib
import unittest
from unittest.mock import patch
from tehnet.client import Device,DeviceError,validate_router,compatible,normalize_status

class DeviceTests(unittest.TestCase):
    def test_router_rejects_external_credentials_paths_and_loopback(self):
        for address in ['https://example.com','http://user:pw@192.168.0.254','http://127.0.0.1','http://192.168.0.254/a','http://8.8.8.8','http://192.168.0.254:99']:
            with self.subTest(address=address),self.assertRaises(ValueError):validate_router(address)
        self.assertEqual(validate_router('192.168.0.254'),'http://192.168.0.254')

    def test_exact_compatibility_fails_closed(self):
        self.assertTrue(compatible({'name':'ZLT P19H','version':'3.2.27','hwversion':'TZ7.821.183'}))
        self.assertFalse(compatible({'name':'ZLT P11','version':'3.2.27','hwversion':'TZ7.821.183'}))
        self.assertFalse(compatible({'name':'ZLT P19H','version':'3.2.28','hwversion':'TZ7.821.183'}))

    def test_login_uses_challenge_and_protected_role(self):
        device=Device()
        with patch.object(device,'call',side_effect=[{'success':True,'message':'salt'},
             {'success':True,'sessionId':'a'*64},{'success':True,'userType':'1'},
             {'success':True}]) as call:
            self.assertEqual(device.login('owner','private'),1)
            sent=call.call_args_list[1].args[0]
            self.assertEqual(sent['passwd'],hashlib.sha256(('salt'+hashlib.md5(b'private').hexdigest()).encode()).hexdigest())
        with patch.object(device,'call',side_effect=[{'success':True,'message':'salt'},
             {'success':True,'sessionId':'b'*64},{'success':True,'userType':'1'},
             {'success':False,'message':'NO_AUTH'}]):
            with self.assertRaises(DeviceError):device.login('owner','private')

    def test_status_handles_missing_malformed_and_never_exports_identifiers(self):
        data=normalize_status({'name':'ZLT P19H','version':'3.2.27','wanIp':'10.1.2.3',
            'imei':'private','rxBytes':'unknown'}, {'message':'RSRP@-95$RSRQ@-10$SINR@5$Frequency Band@42$EARFCN/ARFCN@41690$Cell ID@1234'})
        self.assertEqual(data['rsrp'],-95)
        self.assertEqual(data['band'],'42')
        self.assertIsNone(data['rx_bytes'])
        self.assertNotIn('imei',data)
        self.assertEqual(normalize_status({}, {})['connection'],'unknown')

if __name__=='__main__':unittest.main()
