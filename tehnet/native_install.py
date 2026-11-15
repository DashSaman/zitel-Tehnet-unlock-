"""Reversible static WebUI installation through an owner's verified native console.

No SSH password recovery, account setter, reboot, RF setter or firmware writer.
The command-console transport must already be available to the supplied SUPER.
"""
import argparse
import base64
import getpass
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import tarfile
import tempfile
from .client import Device,DeviceError,compatible
from .pac import Pac
from .recovery import SecretStore

ROOT=Path(__file__).resolve().parents[1]
ENTRIES=['index.html','login.html','info.html','html/home.html','tehnet-vendor.html','tehnet-vendor-login.html']
HEX_DECODER="lua -e 'for s in io.lines() do io.write((s:gsub(string.char(46,46),function(h)return string.char(tonumber(h,16))end)))end'"
HEX_ENCODER="lua -e 's=io.read(1024);if s then for i=1,#s do io.write(string.format(string.char(37,48,50,120),s:byte(i)))end end'"
REDIRECT=b'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><meta http-equiv="Cache-Control" content="no-store"><meta http-equiv="refresh" content="0;url=/tehnet/index.html"><title>Tehran Network</title><script>location.replace('/tehnet/index.html');</script></head><body><a href="/tehnet/index.html">Tehran Network</a></body></html>'''

def digest(data):return hashlib.sha256(data).hexdigest()

def settings_equal(left,right):
    a=Pac.parse(left);b=Pac.parse(right)
    if [(e.name,e.platform,e.filename) for e in a.entries]!=[(e.name,e.platform,e.filename) for e in b.entries]:return False
    for x,y in zip(a.entries,b.entries):
        if x.name!=b'firewall':
            if x.content!=y.content:return False
        else:
            def members(content):
                with tarfile.open(fileobj=io.BytesIO(content),mode='r:*') as tar:
                    items={}
                    for m in tar.getmembers():
                        if m.name in items:raise DeviceError('Duplicate backup member')
                        items[m.name]=(m.type,m.mode,m.uid,m.gid,m.linkname,tar.extractfile(m).read() if m.isfile() else None)
                    return items
            if members(x.content)!=members(y.content):return False
    return True

def validate_bundle(bundle):
    bundle=Path(bundle);manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('variant')!='native-p19h' or manifest.get('public_path')!='/tehnet':raise DeviceError('Wrong native bundle')
    if set(manifest['files'])!={'index.html','app.js','styles.css','native.js','workspace.js','workspace.css','alignment.js','telemetry.js','telemetry.css','menu-map.json','assets/tehnet-logo.jpg'}:raise DeviceError('Unexpected bundle paths')
    files={}
    for name,record in manifest['files'].items():
        path=bundle/name
        if path.is_symlink() or not path.is_file():raise DeviceError('Bundle contains a link or missing file')
        data=path.read_bytes()
        if digest(data)!=record['sha256'] or len(data)!=record['bytes']:raise DeviceError('Bundle integrity failure')
        files[name]=data
    if sum(map(len,files.values()))>512*1024:raise DeviceError('Bundle exceeds verified profile size')
    return manifest,files

def archive_files(files):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as tar:
        for name,data in sorted(files.items()):
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0
            tar.addfile(info,io.BytesIO(data))
    return stream.getvalue()

class Console:
    def __init__(self,device):self.device=device;self.progress=lambda message:None
    def run(self,command):
        # This firmware's command-console parser corrupts escaped double quotes.
        if any(c in command for c in '\r\n\\"') or len(command)>900:raise DeviceError('Invalid bounded command')
        token='TN_'+secrets.token_hex(12)
        framed='ps;echo '+token+'_BEGIN;('+command+');_tn_rc=$?;echo;echo '+token+'_EXIT_$_tn_rc;echo '+token+'_END'
        _,_,raw=self.device.request('POST','/cgi-bin/http.cgi',json.dumps({'language':'EN','sessionId':self.device.sid,'cmd':46,'method':'GET','requestCmd':framed}).encode(),{'Content-Type':'application/json; charset=UTF-8'},timeout=35)
        begin=('\n'+token+'_BEGIN\n').encode();end=('\n'+token+'_END').encode()
        raw=raw.replace(b'\r',b'')
        if len(raw)>256*1024 or raw.count(begin)!=1 or raw.count(end)!=1:raise DeviceError('Console result uncertain; stop and inspect the encrypted journal')
        result=raw.split(begin)[1].split(end)[0]
        marker=('\n'+token+'_EXIT_').encode()
        if result.count(marker)!=1:raise DeviceError('Console exit status unavailable')
        output,status=result.rsplit(marker,1)
        if status.strip()!=b'0':raise DeviceError('Console operation failed; stop and inspect the encrypted journal')
        return output
    def download(self,path,maximum=8*1024*1024):
        size=int(self.run('wc -c < '+shlex.quote(path)).strip())
        if not 0<=size<=maximum:raise DeviceError('Backup size outside supported limits')
        result=bytearray()
        for i in range((size+1023)//1024):
            chunk=self.run('dd if='+shlex.quote(path)+' bs=1024 skip='+str(i)+' count=1 2>/dev/null | '+HEX_ENCODER)
            result.extend(bytes.fromhex(chunk.decode('ascii')))
            if i and i%64==0:self.progress('Verified backup transfer: '+str(len(result))+' / '+str(size)+' bytes')
        if len(result)!=size:raise DeviceError('Backup transfer length mismatch')
        return bytes(result)
    def upload(self,path,data,mutation):
        encoded=data.hex();temporary=path+'.hex'
        mutation('upload-create','umask 077;test ! -e '+shlex.quote(temporary)+' && : > '+shlex.quote(temporary))
        for i in range(0,len(encoded),256):
            mutation('upload-'+str(i),'echo '+encoded[i:i+256]+' >> '+shlex.quote(temporary))
            if i and i%32768==0:self.progress('Staging UI: '+str(i//2)+' / '+str(len(data))+' bytes')
        mutation('upload-decode',HEX_DECODER+' < '+shlex.quote(temporary)+' > '+shlex.quote(path))
        if self.download(path,maximum=1024*1024)!=data:raise DeviceError('Uploaded bytes differ; activation cancelled')
        mutation('upload-remove-hex','rm -f '+shlex.quote(temporary))

class Installer:
    def __init__(self,device,store):
        self.device=device;self.store=store;self.console=Console(device);self.state=None;self.state_path=None
    def check(self):
        if not compatible(self.device.identity()) or self.device.role!=1:raise DeviceError('Only the verified P19H SUPER profile is supported')
        if self.device.call({'cmd':172,'subcmd':15,'method':'GET'}).get('success') is not True:raise DeviceError('Protected role check failed')
        probe=self.console.run('echo 74657374 | '+HEX_DECODER)
        if probe!=b'test':raise DeviceError('Verified binary transfer decoder unavailable')
        probe=self.console.run('dd if=/dev/zero bs=1024 count=1 2>/dev/null | '+HEX_ENCODER)
        if probe!=b'00'*1024:raise DeviceError('Verified binary transfer encoder unavailable')
        out=self.console.run('id;cat /etc/openwrt_release;test -d /tzwww && command -v tar && command -v dd && df -k /tzwww')
        if b'uid=0' not in out or not re.search(rb"DISTRIB_TARGET=['\"]?sqn/32x0",out):raise DeviceError('Verified root command console / sqn/32x0 target unavailable')
        # The final filesystem row belongs to /tzwww, regardless of mount label.
        try:free=int(out.splitlines()[-1].split()[3])*1024
        except (ValueError,IndexError):raise DeviceError('Cannot establish overlay free space') from None
        return free
    def save(self):self.state_path=self.store.save(self.state['name'],self.state)
    def mutation(self,name,command):
        if any(item['name']==name for item in self.state['operations']):raise DeviceError('Never replay a submitted operation')
        item={'name':name,'submitted':True};self.state['operations'].append(item);self.save()
        result=self.console.run(command);item['verified_exit']=0;self.save();return result
    def install(self,bundle):
        manifest,files=validate_bundle(bundle);free=self.check()
        if free<sum(map(len,files.values()))+384*1024:raise DeviceError('Insufficient overlay headroom')
        binding=self.device.binding();nonce=secrets.token_hex(8);base='/root/tehnet-backups/'+nonce
        pac=self.device.export()
        if Pac.parse(pac).pack()!=pac:raise DeviceError('Native backup checksum failure')
        passwords=self.console.run('cat /etc/passwd;cat /etc/shadow 2>/dev/null || true')
        self.state={'schema':1,'kind':'native-webui','name':'native-'+nonce,'router':self.device.base,'binding':binding,'base':base,'manifest':manifest,'operations':[],
            'pac_base64':base64.b64encode(pac).decode(),'password_files_sha256':digest(passwords),'complete':False}
        self.save()
        # The private directory is outside the served webroot; no backup endpoint.
        self.mutation('backup-directory','umask 077;test ! -L /root/tehnet-backups && mkdir -p /root/tehnet-backups && chmod 700 /root/tehnet-backups && mkdir '+base)
        self.mutation('backup-web','tar -czf '+base+'/web-before.tar.gz -C / tzwww')
        backup=self.console.download(base+'/web-before.tar.gz')
        return self.finish_install(manifest,files,pac,binding,base,backup)
    def finish_install(self,manifest,files,pac,binding,base,backup):
        with tarfile.open(fileobj=io.BytesIO(backup),mode='r:gz') as tar:
            if not any(m.name.endswith('/js/main.js') for m in tar.getmembers()):raise DeviceError('Web backup missing native controllers')
        self.state['web_backup_base64']=base64.b64encode(backup).decode();self.save()
        if self.store.load(self.state_path)['web_backup_base64']!=self.state['web_backup_base64']:raise DeviceError('Encrypted backup readback failed')
        self.mutation('prepare-stage','mkdir -m 755 '+base+'/stage')
        self.console.upload(base+'/ui.tar.gz',archive_files(files),self.mutation)
        return self.activate_staged_archive(manifest,files,pac,binding,base)
    def activate_staged_archive(self,manifest,files,pac,binding,base):
        self.mutation('extract-stage','tar -xzf '+base+'/ui.tar.gz -C '+base+'/stage && chmod 755 '+base+'/stage/assets')
        self.mutation('remove-staged-archive','rm -f '+base+'/ui.tar.gz')
        entries={}
        for i,name in enumerate(ENTRIES):
            path='/tzwww/'+name
            kind=self.console.run('if test -L '+path+';then echo link;elif test -f '+path+';then echo file;else echo absent;fi').strip().decode()
            entries[name]=kind
            if kind!='absent':self.mutation('save-entry-'+str(i),'mv '+path+' '+base+'/entry-'+str(i))
        self.state['entries']=entries
        self.state['had_tehnet']=self.console.run('if test -d /tzwww/tehnet;then echo yes;else echo no;fi').strip()==b'yes';self.save()
        if self.state['had_tehnet']:self.mutation('save-previous-ui','mv /tzwww/tehnet '+base+'/previous-ui')
        self.mutation('activate-ui','mv '+base+'/stage /tzwww/tehnet')
        self.console.upload(base+'/redirect.html',REDIRECT,self.mutation_unique('redirect-'))
        for i,name in enumerate(ENTRIES):self.mutation('redirect-entry-'+str(i),'cp '+base+'/redirect.html /tzwww/'+name+' && chmod 644 /tzwww/'+name)
        self.mutation('sync','sync')
        self.verify(files)
        if self.device.binding()!=binding or not settings_equal(self.device.export(),pac):raise DeviceError('Settings changed; inspect before restoring anything')
        if digest(self.console.run('cat /etc/passwd;cat /etc/shadow 2>/dev/null || true'))!=self.state['password_files_sha256']:raise DeviceError('Password files changed outside the UI transaction')
        self.state['complete']=True;self.save();return self.state_path
    def mutation_unique(self,prefix):return lambda name,command:self.mutation(prefix+name,command)
    def verify(self,files):
        for name,data in files.items():
            status,_,actual=self.device.request('GET','/tehnet/'+name+'?tnverify='+secrets.token_hex(4))
            if status!=200 or data!=actual:raise DeviceError('Served asset verification failed')
        for name in ENTRIES:
            if self.device.request('GET','/'+name)[2]!=REDIRECT:raise DeviceError('Legacy entrypoint still active')
    def rollback(self,state_path):
        state=self.store.load(state_path)
        if state.get('kind')!='native-webui' or not re.fullmatch(r'/root/tehnet-backups/[a-f0-9]{16}',state.get('base','')):raise DeviceError('Invalid native rollback journal')
        if self.device.binding()!=state['binding'] or not state.get('complete'):raise DeviceError('Wrong device or incomplete operation: manual journal inspection required')
        self.check();self.state=state;self.state_path=Path(state_path)
        # Preserve later UI deployments and all later router/account settings.
        for name,record in state['manifest']['files'].items():
            if digest(self.device.request('GET','/tehnet/'+name)[2])!=record['sha256']:raise DeviceError('UI changed after installation; rollback refused')
        for name in ENTRIES:
            if self.device.request('GET','/'+name)[2]!=REDIRECT:raise DeviceError('Entry changed after installation; rollback refused')
        base=state['base'];self.mutation('rollback-park-ui','mv /tzwww/tehnet '+base+'/removed-ui')
        if state['had_tehnet']:self.mutation('rollback-old-ui','mv '+base+'/previous-ui /tzwww/tehnet')
        for i,name in enumerate(ENTRIES):
            command='mv /tzwww/'+name+' '+base+'/removed-entry-'+str(i)
            if state['entries'][name]!='absent':command+=' && mv '+base+'/entry-'+str(i)+' /tzwww/'+name
            self.mutation('rollback-entry-'+str(i),command)
        self.mutation('rollback-sync','sync');self.state['rolled_back']=True;self.save()

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--check',action='store_true');mode.add_argument('--install',action='store_true');mode.add_argument('--rollback',type=Path)
    parser.add_argument('--router',default='192.168.0.254');args=parser.parse_args(argv)
    try:
        device=Device(args.router)
        if not compatible(device.identity()):raise DeviceError('Unsupported device; no authentication or write attempted')
        if args.check:print('Compatible identity. Installation additionally requires the existing SUPER command console. No changes made.');return 0
        if os.name!='nt':raise DeviceError('Windows DPAPI is required')
        username=input('Current SUPER username: ').strip();password=getpass.getpass('Current SUPER password (preserved): ')
        device.login(username,password);password=''
        installer=Installer(device,SecretStore())
        installer.console.progress=lambda message:print(message,flush=True)
        if args.rollback:installer.rollback(args.rollback);print('Previous UI restored; router settings and passwords preserved.');return 0
        spec=importlib.util.spec_from_file_location('native_builder',ROOT/'tools/build_device_webui.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory(prefix='tehnet-build-') as tmp:
            builder.build(Path(tmp)/'ui');path=installer.install(Path(tmp)/'ui')
        print('Installed:',device.base+'/tehnet/index.html');print('Encrypted rollback journal:',path);return 0
    except (DeviceError,ValueError,OSError) as error:
        # No raw device output, credential, journal contents or command in errors.
        print('Stopped:',str(error));return 1

if __name__=='__main__':raise SystemExit(main())
