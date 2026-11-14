"""Windows-user-bound encrypted backups; narrow native account rollback."""
import base64
import ctypes
import json
import os
from pathlib import Path
import re
import secrets
from .client import DeviceError,compatible
from .pac import Pac,config_values

def dpapi(data,decrypt=False):
    if os.name!='nt':raise DeviceError('Encrypted backup/account installation requires Windows DPAPI')
    from ctypes import wintypes
    class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    if decrypt:
        function=crypt.CryptUnprotectData
        function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        success=function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:
        function=crypt.CryptProtectData
        function.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        success=function(ctypes.byref(source),'Tehran Network P19H',None,None,None,1,ctypes.byref(target))
    if not success:raise DeviceError('Windows could not protect/open this private backup')
    try:return ctypes.string_at(target.data,target.size)
    finally:
        kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
        kernel.LocalFree(ctypes.cast(target.data,ctypes.c_void_p))

class SecretStore:
    def __init__(self,root=None,seal=None,unseal=None):
        self.root=Path(root) if root else Path(os.environ.get('LOCALAPPDATA',''))/'TehranNetwork'/'P19H'
        self.seal=seal or (lambda b:dpapi(b));self.unseal=unseal or (lambda b:dpapi(b,True))
    def save(self,name,payload):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name):raise ValueError('Invalid private state name')
        raw=self.seal(json.dumps(payload,ensure_ascii=False).encode('utf-8'))
        self.root.mkdir(parents=True,exist_ok=True)
        target=self.root/(name+'.dpapi');temporary=self.root/(name+'.'+secrets.token_hex(6)+'.tmp')
        temporary.write_bytes(raw);os.replace(temporary,target)
        return target
    def load(self,path):
        path=Path(path)
        if path.stat().st_size>40*1024*1024:raise DeviceError('Private state exceeds size limit')
        try:payload=json.loads(self.unseal(path.read_bytes()))
        except DeviceError:raise
        except Exception:raise DeviceError('Invalid encrypted private state') from None
        if not isinstance(payload,dict):raise DeviceError('Invalid private state format')
        return payload

def backup_device(device,store,name):
    identity=device.identity()
    if not compatible(identity) or device.role!=1:raise DeviceError('Backup needs the verified compatible administrator')
    raw=device.export();pac=Pac.parse(raw)
    if pac.pack()!=raw:raise DeviceError('Backup failed its byte-identical roundtrip')
    import hashlib
    payload={'schema':1,'router':device.base,'device_binding':device.binding(),'identity':{key:identity.get(key) for key in ['name','version','hwversion']},
        'pac_base64':base64.b64encode(raw).decode('ascii'),'pac_sha256':hashlib.sha256(raw).hexdigest()}
    path=store.save(name,payload)
    restored=store.load(path)
    if base64.b64decode(restored['pac_base64'])!=raw:raise DeviceError('Encrypted backup verification failed')
    return path,config_values(pac.text())

def restore_native_account(device,current,original,role):
    name=current['username'];digest=current['digest']
    if device.login_digest(name,digest)!=role:raise DeviceError('Recovery role mismatch')
    if name!=original['username']:
        result=device.call({'cmd':98,'method':'POST','username':name,'newUsername':original['username']})
        if result.get('success') is not True:raise DeviceError('Recovery username change was rejected')
        name=original['username']
        if device.login_digest(name,digest)!=role:raise DeviceError('Recovery username verification failed')
    if digest!=original['digest']:
        result=device.call({'cmd':102,'method':'POST','subcmd':-1,'passwd':digest,'newPasswd':original['digest']})
        if result.get('success') is not True:raise DeviceError('Recovery password change was rejected')
        digest=original['digest']
    if device.login_digest(name,digest)!=role:raise DeviceError('Restored account login verification failed')
    return True
