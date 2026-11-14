import contextlib
import io
import unittest
from unittest.mock import patch
from tehnet.cli import main,parser,reboot_verify
from tehnet.client import DeviceError

class InstallerTests(unittest.TestCase):
    def test_password_is_never_a_command_line_option(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):parser().parse_args(['--password','private'])
    def test_unsupported_device_never_prompts_or_writes(self):
        with patch('tehnet.cli.Device') as factory,patch('tehnet.cli.read_login') as login:
            factory.return_value.identity.return_value={'name':'different'}
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main(['--install']),1)
            login.assert_not_called();factory.return_value.call.assert_not_called()
    def test_check_never_authenticates_or_changes_device(self):
        with patch('tehnet.cli.Device') as factory,patch('tehnet.cli.read_login') as login:
            factory.return_value.identity.return_value={'name':'ZLT P19H','version':'3.2.27','hwversion':'TZ7.821.183'}
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(['--check']),0)
            login.assert_not_called();factory.return_value.call.assert_not_called()
    def test_reboot_is_sent_once_and_login_waits_for_return(self):
        class Modem:
            role=1
            def __init__(self):self.reboots=0;self.probes=0;self.logins=0
            def identity(self):
                self.probes+=1
                if self.probes==2:raise DeviceError('offline')
                return {'name':'ZLT P19H','version':'3.2.27','hwversion':'TZ7.821.183'}
            def call(self,p):
                if p['cmd']==6:self.reboots+=1;return {'success':True}
                return {'uptime':'20:00 up 2:10, load average:0'}
            def login(self,u,p):self.logins+=1;return 1
            def status(self):return {'connection':'connected'}
        d=Modem()
        with patch('tehnet.cli.time.sleep'),contextlib.redirect_stdout(io.StringIO()):
            result=reboot_verify(d,'owner','private')
        self.assertTrue(result['fresh_login']);self.assertEqual(d.reboots,1);self.assertEqual(d.logins,1)

if __name__=='__main__':unittest.main()
