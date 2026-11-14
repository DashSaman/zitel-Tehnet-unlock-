"""Native account changes, always followed by fresh authentication.

Does not import configurations, reboot, or modify RF/network policies.
"""
import hashlib
import re
from .client import DeviceError

class AccountChangeError(DeviceError):
    def __init__(self,message,password_changed=False,username_changed=False,rename_reverted=False,uncertain=False):
        super().__init__(message)
        self.password_changed=password_changed;self.username_changed=username_changed
        self.rename_reverted=rename_reverted
        self.uncertain=uncertain

def validate_account(username,password):
    if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{2,20}',username):
        raise ValueError('Username must contain2–20 ASCII letters, digits, _, ., @ or -')
    if not isinstance(password,str) or not 1<=len(password)<=20 or any(ord(c)<32 for c in password):
        raise ValueError('Password must contain1–20 printable characters supported by this firmware')

def change_account(device,old_username,old_digest,new_username,new_password,expected_role,on_step=None):
    validate_account(new_username,new_password if new_password is not None else 'unchanged')
    new_digest=hashlib.md5(new_password.encode('utf-8')).hexdigest() if new_password is not None else old_digest
    state={'password_changed':False,'username_changed':False,'verified':False,'rename_reverted':False}
    def step(name):
        if on_step:on_step(name,dict(state))
    if device.login_digest(old_username,old_digest)!=expected_role:raise AccountChangeError('Initial account role mismatch')
    if new_digest!=old_digest:
        step('before_password_write')
        try:result=device.call({'cmd':102,'method':'POST','subcmd':-1,'passwd':old_digest,'newPasswd':new_digest})
        except DeviceError:raise AccountChangeError('Password write outcome is uncertain; preserve the recovery journal and do not repeat the write',uncertain=True) from None
        if result.get('success') is not True:raise AccountChangeError('Native password change was rejected')
        state['password_changed']=True;step('password_written')
        try:
            if device.login_digest(old_username,new_digest)!=expected_role:raise DeviceError('Role mismatch')
        except DeviceError:raise AccountChangeError('Password write needs recovery inspection',True) from None
        step('password_verified')
    if new_username!=old_username:
        saved_sid=device.sid
        step('before_username_write')
        try:result=device.call({'cmd':98,'method':'POST','username':old_username,'newUsername':new_username})
        except DeviceError:raise AccountChangeError('Username write outcome is uncertain; preserve the recovery journal and do not repeat the write',state['password_changed'],uncertain=True) from None
        if result.get('success') is not True:
            raise AccountChangeError('Native username change was rejected; the old username remains active',state['password_changed'])
        state['username_changed']=True;step('username_written')
        try:
            if device.login_digest(new_username,new_digest)!=expected_role:raise DeviceError('Role mismatch')
        except DeviceError:
            # A duplicate name may shadow a slot. Retain the pre-rename session
            # instead of attempting repeated logins or guessing account order.
            device.sid=saved_sid;device.role=expected_role
            reverted=device.call({'cmd':98,'method':'POST','username':new_username,'newUsername':old_username})
            if reverted.get('success') is True:
                if device.login_digest(old_username,new_digest)==expected_role:
                    state.update(username_changed=False,rename_reverted=True);step('rename_reverted')
                    raise AccountChangeError('Shared username prevents verified access; the conflicting rename was reverted',state['password_changed'],False,True) from None
            raise AccountChangeError('Account rename could not be verified; retain private recovery data',state['password_changed'],True) from None
    state['verified']=True;step('complete')
    return state
