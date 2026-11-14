"""Secure Windows installer/wizard. Passwords are never command-line options."""
import argparse
from datetime import datetime,timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
import webbrowser
from .accounts import change_account,validate_account
from .client import Device,DeviceError,compatible
from .recovery import SecretStore,backup_device,restore_native_account
from .server import AppServer

def parser():
    p=argparse.ArgumentParser(description='Tehran Network P19H local companion; Windows account installer')
    modes=p.add_mutually_exclusive_group()
    for mode in ['check','dry-run','install','backup','verify','rollback','serve']:
        modes.add_argument('--'+mode,action='store_true')
    p.add_argument('--router',default='192.168.0.254',help='Private modem IPv4 or auto (known IP/configured gateways only)')
    p.add_argument('--port',type=int,default=8765,help='Local loopback port;0 selects a free port')
    p.add_argument('--no-browser',action='store_true')
    p.add_argument('--apply-accounts',action='store_true',help='Open the secure native-account wizard after backup')
    p.add_argument('--reboot-check',action='store_true',help='One visible reboot/persistence check; interrupts LTE briefly')
    p.add_argument('--state',type=Path,help='Owner DPAPI journal path for targeted rollback')
    return p

def serve(args,device):
    server=AppServer(device.base,args.port)
    print('پنل محلی آماده است / Local panel:',server.origin,flush=True)
    print('این پنجره را باز نگه دارید؛ Ctrl+C برای توقف. فریمور مودم تغییر نکرده است.',flush=True)
    if not args.no_browser:webbrowser.open(server.origin)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0

def read_login(device,input_fn=input,password_fn=getpass.getpass):
    if input_fn is input and password_fn is getpass.getpass and not sys.stdin.isatty():
        raise DeviceError('Open an interactive Windows console for the protected password prompt; redirected password input is not supported')
    username=input_fn('نام کاربری فعلی مودم / Current username: ').strip()
    password=password_fn('رمز فعلی / Current password (hidden): ')
    role=device.login(username,password)
    return username,password,role

def rollback_journal(payload,store,path,device_factory=Device):
    target=device_factory(payload['router']);identity=target.identity()
    if not compatible(identity) or identity.get('hwversion')!=payload['identity']['hwversion']:
        raise DeviceError('Recovery target does not match the verified hardware/firmware')
    if not payload.get('device_binding') or target.binding()!=payload['device_binding']:
        raise DeviceError('Recovery journal belongs to a different physical modem')
    if payload.get('needs_inspection'):raise DeviceError('A native write outcome is uncertain; inspect the encrypted journal before rollback')
    for slot in ['PRIMARY','SUPER']:
        item=payload.get('accounts',{}).get(slot)
        if not item or item.get('restored'):continue
        if item['current']!=item['original']:
            restore_native_account(device_factory(payload['router']),item['current'],item['original'],item['role'])
        item['restored']=True;store.save(Path(path).stem,payload)
    payload['rolled_back']=True;store.save(Path(path).stem,payload)
    return True

def account_wizard(admin,admin_name,values,store,backup_path,input_fn=input,password_fn=getpass.getpass,device_factory=Device):
    if admin.role!=1:raise DeviceError('Account installation needs a verified SUPER administrator')
    print('دو نقش تأییدشده: حساب عادی اصلی و مدیر SUPER. حساب سومِ مدیر ساخته نمی‌شود.')
    print('نام SUPER در این نسخه از مسیر بومی قابل تغییر نیست؛ نام فعلی حفظ می‌شود.')
    user_name=input_fn('نام جدید حساب عادی (Enter = حفظ نام فعلی): ').strip() or values['TZ_USERNAME']
    user_password=password_fn('رمز جدید حساب عادی (Enter = حفظ رمز فعلی): ') or None
    if user_password is not None:
        if password_fn('تکرار رمز جدید حساب عادی: ')!=user_password:raise ValueError('Password confirmation mismatch')
    super_password=password_fn('رمز جدید SUPER (Enter = حفظ رمز فعلی): ') or None
    if super_password is not None:
        if password_fn('تکرار رمز جدید SUPER: ')!=super_password:raise ValueError('Password confirmation mismatch')
    validate_account(user_name,user_password if user_password is not None else 'unchanged')
    if super_password is not None:validate_account(admin_name,super_password)
    if user_name==admin_name:raise ValueError('Installer requires distinct primary and SUPER usernames to avoid unverified collision behavior')
    name='accounts-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
    payload={'schema':1,'router':admin.base,'device_binding':admin.binding(),'identity':{k:v for k,v in admin.identity().items() if k in ['name','version','hwversion']},
             'backup_path':str(backup_path),'accounts':{},'complete':False}
    path=store.save(name,payload)
    for slot,username,digest,target_name,target_password,role in [
        ('PRIMARY',values['TZ_USERNAME'],values['TZ_PASSWD'],user_name,user_password,2),
        ('SUPER',admin_name,values['TZ_SUPER_PASSWD'],admin_name,super_password,1)]:
        original={'username':username,'digest':digest}
        item={'role':role,'original':original,'current':dict(original),'restored':False,'verified':False}
        payload['accounts'][slot]=item;store.save(name,payload)
        desired_digest=hashlib.md5(target_password.encode()).hexdigest() if target_password is not None else digest
        item['planned']={'username':target_name,'digest':desired_digest};store.save(name,payload)
        def on_step(stage,progress):
            if progress.get('password_changed'):item['current']['digest']=desired_digest
            if progress.get('username_changed'):item['current']['username']=target_name
            if progress.get('rename_reverted'):item['current']['username']=username
            item['stage']=stage;item['verified']=progress.get('verified',False)
            store.save(name,payload)
        try:
            change_account(device_factory(admin.base),username,digest,target_name,target_password,role,on_step)
        except Exception as error:
            if getattr(error,'uncertain',False):
                payload['needs_inspection']=True;store.save(name,payload)
                raise DeviceError('A write outcome is uncertain. Do not repeat it. Keep the encrypted journal: '+str(path)) from None
            print('تغییر کامل نشد؛ بازیابی محدود حساب‌های تغییرکرده در حال اجراست.')
            rollback_journal(payload,store,path,device_factory)
            raise
    payload['complete']=True;store.save(name,payload)
    # Authenticate with the final SUPER credential in the encrypted journal;
    # retain no plaintext password in installed source or configuration.
    final=payload['accounts']['SUPER']['current']
    admin.login_digest(final['username'],final['digest'])
    after=admin.export()
    from .pac import Pac,config_values
    exported=config_values(Pac.parse(after).text())
    allowed={'TZ_USERNAME','TZ_PASSWD','TZ_SUPER_PASSWD'}
    if any(exported.get(k)!=v for k,v in values.items() if k not in allowed):
        raise DeviceError('Unrelated configuration differed; keep encrypted backups and stop')
    print('ورود هر دو حساب و ثابت‌ماندن تنظیمات دیگر تأیید شد. Journal:',path)
    return path

def reboot_verify(device,username,password=None,timeout=180,digest=None):
    if device.role!=1 or not compatible(device.identity()):raise DeviceError('Reboot check needs the verified compatible administrator')
    print('آزمون یک‌بار راه‌اندازی مجدد: اتصال LTE برای مدتی قطع می‌شود.')
    before=device.call({'cmd':133,'method':'GET'}).get('uptime','')
    def uptime_minutes(value):
        import re
        match=re.search(r'up\s+(?:(\d+)\s+days?,\s*)?(?:(\d+):(\d+)|(\d+)\s+min)',value)
        if not match:return None
        days,hours,minutes,plain=match.groups()
        return int(days or 0)*1440+int(hours or 0)*60+int(minutes or plain or 0)
    before_minutes=uptime_minutes(before)
    result=device.call({'cmd':6,'method':'POST'})
    if result.get('success') is not True:raise DeviceError('Reboot command was not accepted; not repeated')
    deadline=time.monotonic()+timeout;went_offline=False
    while time.monotonic()<deadline:
        time.sleep(2)
        try:
            identity=device.identity()
            if went_offline and compatible(identity):break
            uptime=device.call({'cmd':133,'method':'GET'}).get('uptime','')
            after_minutes=uptime_minutes(uptime)
            if compatible(identity) and before_minutes is not None and after_minutes is not None and after_minutes<before_minutes:break
        except DeviceError:went_offline=True
    else:raise DeviceError('Restart verification timed out; no second reboot was sent')
    if digest:device.login_digest(username,digest)
    else:device.login(username,password)
    until=time.monotonic()+90
    while time.monotonic()<until:
        status=device.status()
        if status['connection']=='connected':return {'reboot_count':1,'fresh_login':True,'wan_assigned':True}
        time.sleep(3)
    raise DeviceError('Login returned but WAN was not assigned within the verification window')

def main(argv=None):
    if sys.version_info<(3,10):raise SystemExit('Python3.10+ is required')
    args=parser().parse_args(argv)
    try:
        if args.router=='auto':
            from .discovery import discover
            device=discover()
        else:device=Device(args.router)
        identity=device.identity()
        if not compatible(identity):raise DeviceError('Unsupported device: no account, radio or firmware changes were sent')
        if args.check:
            print(json.dumps({'compatible':True,'model':identity.get('name'),'firmware':identity.get('version'),
                'hardware':identity.get('hwversion'),'mode':'companion','native_ui_replacement':False,
                'super_username_change':False,'second_device_tested':False},ensure_ascii=False,indent=2));return 0
        if args.serve:return serve(args,device)
        if args.rollback:
            if not args.state:raise ValueError('--rollback requires the owner DPAPI journal via --state')
            store=SecretStore();payload=store.load(args.state)
            if payload.get('router')!=device.base:raise DeviceError('Journal address differs from the selected router')
            rollback_journal(payload,store,args.state);print('بازیابی حساب‌ها تأیید شد؛ تنظیمات شبکه بازنویسی نشد.');return 0
        username,password,role=read_login(device)
        if args.dry_run:
            print(json.dumps({'compatible':True,'role':role,'mode':'companion','native_account_writes':False,
                'reboot':False,'firmware_flash':False,'status':{'connection':device.status()['connection']}},ensure_ascii=False,indent=2));return 0
        if args.verify:
            if args.reboot_check:
                print(json.dumps(reboot_verify(device,username,password),ensure_ascii=False));return 0
            status=device.status();print(json.dumps({'login_verified':True,'role':role,'wan_assigned':status['connection']=='connected','band':status['band']},ensure_ascii=False,indent=2));return 0
        if role==1:
            name='backup-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
            store=SecretStore();backup_path,values=backup_device(device,store,name)
            print('بکاپ رمزگذاری‌شده و بازخوانی آن تأیید شد:',backup_path)
        elif args.backup or args.apply_accounts or args.reboot_check:
            raise DeviceError('This action needs the verified SUPER account')
        if args.backup:return 0
        if args.apply_accounts:
            journal=account_wizard(device,username,values,store,backup_path)
            final=store.load(journal)['accounts']['SUPER']['current']
            # The reboot flow uses the digest internally; do not recover or save plaintext.
            if args.reboot_check:
                print(json.dumps(reboot_verify(device,final['username'],digest=final['digest']),ensure_ascii=False))
        elif args.reboot_check:
            print(json.dumps(reboot_verify(device,username,password),ensure_ascii=False))
        password=None
        return serve(args,device)
    except (DeviceError,ValueError,OSError) as error:
        print('خطا / Error:',str(error),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
