import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock,patch
from tehnet.client import DeviceError
from tehnet.native_install import Console,Installer,ROOT,validate_bundle,main
from tehnet.recovery import SecretStore

class NativeInstallerTests(unittest.TestCase):
    def test_unsupported_check_never_authenticates_or_mutates(self):
        device=Mock();device.identity.return_value={'name':'other'}
        with patch('tehnet.native_install.Device',return_value=device):self.assertEqual(main(['--check']),1)
        device.login.assert_not_called();device.request.assert_not_called()

    def test_password_is_not_a_command_line_option(self):
        with self.assertRaises(SystemExit):main(['--install','--password','test-only'])

    def test_console_requires_complete_unique_frame_and_zero_exit(self):
        device=Mock();device.sid='test-session'
        def respond(*args,**kwargs):
            body=json.loads(args[2]);token=re.search(r'echo (TN_[a-f0-9]+)_BEGIN',body['requestCmd'])[1]
            return 200,{},('preamble\n'+token+'_BEGIN\nhello\n'+token+'_EXIT_0\n'+token+'_END\n').encode()
        device.request.side_effect=respond
        self.assertEqual(Console(device).run('id'),b'hello')
        device.request.return_value=(200,{},b'NO_AUTH');device.request.side_effect=None
        with self.assertRaises(DeviceError):Console(device).run('id')

    def test_binary_upload_limits_each_hex_line_and_verifies_readback(self):
        data=bytes(range(256))*4;console=Console(Mock());console.download=Mock(return_value=data)
        operations=[];console.upload('/root/tehnet-backups/test/ui.tar.gz',data,lambda name,command:operations.append(command))
        appends=[command for command in operations if command.startswith('echo ')]
        pieces=[command.split()[1] for command in appends]
        self.assertTrue(all(len(piece)<=256 for piece in pieces))
        self.assertEqual(bytes.fromhex(''.join(pieces)),data)
        self.assertTrue(any('lua -e' in command and ' < ' in command for command in operations));console.download.assert_called_once()

    def test_uncertain_mutation_is_journaled_and_never_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=SecretStore(Path(tmp),seal=lambda b:b,unseal=lambda b:b);installer=Installer(Mock(),store)
            installer.state={'name':'test','operations':[]};installer.console.run=Mock(side_effect=DeviceError('uncertain'))
            with self.assertRaises(DeviceError):installer.mutation('activate','mv a b')
            self.assertEqual(store.load(installer.state_path)['operations'],[{'name':'activate','submitted':True}])
            with self.assertRaises(DeviceError):installer.mutation('activate','mv a b')
            self.assertEqual(installer.console.run.call_count,1)

    def test_bundle_tampering_stops_before_contact(self):
        spec=importlib.util.spec_from_file_location('builder',ROOT/'tools/build_device_webui.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as tmp:
            builder.build(Path(tmp));validate_bundle(Path(tmp))
            (Path(tmp)/'workspace.js').write_text('tampered',encoding='utf-8')
            with self.assertRaises(DeviceError):validate_bundle(Path(tmp))

    def test_rollback_rejects_another_device_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=SecretStore(Path(tmp),seal=lambda b:b,unseal=lambda b:b)
            state=store.save('test',{'kind':'native-webui','base':'/root/tehnet-backups/'+'a'*16,'binding':'one','complete':True})
            device=Mock();device.binding.return_value='two';installer=Installer(device,store);installer.console.run=Mock()
            with self.assertRaises(DeviceError):installer.rollback(state)
            installer.console.run.assert_not_called()

if __name__=='__main__':unittest.main()
