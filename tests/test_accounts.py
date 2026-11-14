import unittest
from tehnet.accounts import change_account,AccountChangeError
from tehnet.client import DeviceError

class FakeDevice:
    def __init__(self):self.username='old';self.digest='a'*32;self.role=1;self.sid='s';self.commands=[];self.reject=False
    def login_digest(self,name,digest):
        if name!=self.username or digest!=self.digest:raise AccountChangeError('Login failed')
        return self.role
    def call(self,p):
        self.commands.append(p['cmd'])
        if p['cmd']==98:
            if self.reject:return {'success':False}
            self.username=p['newUsername']
        if p['cmd']==102:self.digest=p['newPasswd']
        return {'success':True}

class AccountTests(unittest.TestCase):
    def test_change_verifies_each_step(self):
        d=FakeDevice();result=change_account(d,'old','a'*32,'new','secret',1)
        self.assertTrue(result['verified']);self.assertEqual(d.username,'new')
        self.assertEqual(d.commands,[102,98])

    def test_collision_preserves_working_name_and_reports_precisely(self):
        d=FakeDevice();d.reject=True
        with self.assertRaises(AccountChangeError) as raised:change_account(d,'old','a'*32,'new','secret',1)
        self.assertTrue(raised.exception.password_changed)
        self.assertFalse(raised.exception.username_changed)
        self.assertEqual(d.username,'old')

    def test_invalid_name_never_mutates(self):
        d=FakeDevice()
        with self.assertRaises(ValueError):change_account(d,'old','a'*32,'bad\nname','secret',1)
        self.assertEqual(d.commands,[])
    def test_transport_loss_does_not_claim_password_was_unchanged(self):
        class Uncertain(FakeDevice):
            def call(self,p):
                super().call(p)
                if p['cmd']==102:raise DeviceError('connection lost')
        with self.assertRaises(AccountChangeError) as raised:change_account(Uncertain(),'old','a'*32,'old','secret',1)
        self.assertTrue(raised.exception.uncertain)

if __name__=='__main__':unittest.main()
