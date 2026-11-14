import base64
import tempfile
from pathlib import Path
import unittest
import os
from tehnet.recovery import SecretStore,restore_native_account

class RecoveryTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows DPAPI is platform-specific')
    def test_real_windows_dpapi_roundtrip(self):
        with tempfile.TemporaryDirectory() as root:
            store=SecretStore(Path(root));payload={'example':'local-owner-test-value'}
            path=store.save('windows-roundtrip',payload)
            self.assertNotIn(payload['example'].encode(),path.read_bytes())
            self.assertEqual(store.load(path),payload)
    def test_encrypted_store_never_writes_plaintext(self):
        with tempfile.TemporaryDirectory() as root:
            store=SecretStore(Path(root),seal=lambda b:b'ENC:'+base64.b64encode(b),unseal=lambda b:base64.b64decode(b[4:]))
            path=store.save('journal',{'private':'unique-owner-secret'})
            self.assertNotIn(b'unique-owner-secret',path.read_bytes())
            self.assertEqual(store.load(path),{'private':'unique-owner-secret'})
    def test_path_traversal_in_state_name_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            store=SecretStore(Path(root),seal=lambda b:b,unseal=lambda b:b)
            with self.assertRaises(ValueError):store.save('../elsewhere',{})
    def test_restore_changes_only_account_and_verifies(self):
        from test_accounts import FakeDevice
        d=FakeDevice();d.username='new';d.digest='b'*32
        result=restore_native_account(d,{'username':'new','digest':'b'*32},
            {'username':'old','digest':'a'*32},1)
        self.assertTrue(result);self.assertEqual(d.username,'old');self.assertEqual(d.digest,'a'*32)
        self.assertEqual(d.commands,[98,102])

if __name__=='__main__':unittest.main()
