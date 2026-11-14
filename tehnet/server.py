"""Loopback-only companion, protected local sessions and native panel bridge."""
from dataclasses import dataclass,field
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit,unquote
from .accounts import change_account,AccountChangeError
from .client import Device,DeviceError,compatible

WEB=Path(__file__).resolve().parent.parent/'webui'
@dataclass
class Session:
    csrf:str=field(default_factory=lambda:secrets.token_urlsafe(32),repr=False)
    device:object=field(default=None,repr=False)
    username:str=''
    role:int=0
    touched:float=field(default_factory=time.monotonic)
    failures:int=0
    blocked_until:float=0
    lock:object=field(default_factory=threading.RLock,repr=False)

class AppServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=False
    def __init__(self,address='192.168.0.254',port=0,device_factory=Device):
        self.address=address;self.device_factory=device_factory;self.sessions={};self.lock=threading.Lock();self.internal_errors=0;self.super_name=None
        super().__init__(('127.0.0.1',port),Handler)
        self.authority='127.0.0.1:'+str(self.server_port);self.origin='http://'+self.authority
        self.cookie_name='tehnet_'+str(self.server_port)
    def handle_error(self,request,client_address):
        # No request body, session, account value, or arbitrary exception is logged.
        self.internal_errors+=1

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def reply(self,status,body=b'',content_type='application/json; charset=utf-8',headers=None,native=False):
        if isinstance(body,(dict,list)):body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status)
        for key,value in {'Content-Type':content_type,'Content-Length':str(len(body)),
            'Cache-Control':'no-store','Referrer-Policy':'same-origin','X-Content-Type-Options':'nosniff',
            'X-Frame-Options':'SAMEORIGIN','X-Robots-Tag':'noindex, nofollow, noarchive','Connection':'close',**(headers or {})}.items():self.send_header(key,value)
        if not native:self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; form-action 'self'; base-uri 'self'; object-src 'none'")
        self.end_headers();self.wfile.write(body);self.close_connection=True
    def error(self,status,message):self.reply(status,{'error':message})
    def do_GET(self):self.handle_request()
    def do_POST(self):self.handle_request()
    def do_HEAD(self):self.error(405,'Method not supported')
    def session(self,create=False):
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:pass
        token=cookie[self.server.cookie_name].value if self.server.cookie_name in cookie else ''
        with self.server.lock:
            now=time.monotonic()
            self.server.sessions={k:v for k,v in self.server.sessions.items() if now-v.touched<1800}
            state=self.server.sessions.get(token)
            fresh=False
            if state is None and create:
                if len(self.server.sessions)>=100:return None,{}
                token=secrets.token_urlsafe(32);state=Session();self.server.sessions[token]=state;fresh=True
            if state:state.touched=now
        return state,({'Set-Cookie':f'{self.server.cookie_name}={token}; Path=/; HttpOnly; SameSite=Strict'} if fresh else {})
    def handle_request(self):
        if self.client_address[0]!='127.0.0.1' or self.headers.get_all('Host',[])!=[self.server.authority]:return self.error(403,'Invalid local host')
        if self.headers.get('Sec-Fetch-Site') in ['cross-site','same-site']:return self.error(403,'Cross-origin request denied')
        if self.headers.get('Origin') not in [None,self.server.origin]:return self.error(403,'Cross-origin request denied')
        if not self.path.startswith('/') or self.path.startswith('//') or urlsplit(self.path).netloc:return self.error(400,'Invalid path')
        path=unquote(urlsplit(self.path).path)
        if '..' in path.split('/') or '\\' in path:return self.error(404,'Not found')
        state,headers=self.session(create=path in ['/','/index.html'])
        if path in ['/','/index.html'] and self.command=='GET':
            if state is None:return self.error(429,'Too many local sessions')
            return self.static('index.html',headers)
        if path in ['/app.js','/styles.css'] or path.startswith('/assets/'):
            if self.command!='GET':return self.error(405,'Method not supported')
            return self.static(path.lstrip('/'))
        if path=='/api/bootstrap' and self.command=='GET':
            if state is None:return self.error(401,'Open the local panel first')
            return self.reply(200,{'csrf':state.csrf,'authenticated':state.device is not None,
                'username':state.username if state.device else None,'role':state.role,'router':self.server.address,
                'can_rename_primary':state.role==2 and self.server.super_name is not None})
        if self.command=='POST':
            lengths=self.headers.get_all('Content-Length',[])
            if self.headers.get('Transfer-Encoding') or len(lengths)!=1 or not lengths[0].isdigit():return self.error(400,'Invalid body length')
            length=int(lengths[0]);maximum=32*1024*1024 if not path.startswith('/api/') else 8192
            if length>maximum:return self.error(413,'Request too large')
            if state is None or self.headers.get('Origin')!=self.server.origin:return self.error(403,'Local same-origin session required')
            native=not path.startswith('/api/')
            if native:
                origin=self.headers.get('Origin')
                if origin!=self.server.origin:return self.error(403,'Invalid native form origin')
            elif not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),state.csrf):return self.error(403,'Invalid CSRF token')
            self.connection.settimeout(20);body=self.rfile.read(length)
            if len(body)!=length:return self.error(400,'Incomplete request')
        else:body=None
        if path=='/api/login' and self.command=='POST':
            with state.lock:
                if time.monotonic()<state.blocked_until:return self.error(429,'Wait before trying another login')
                try:
                    data=json.loads(body)
                    if not isinstance(data,dict):raise ValueError()
                    username=data.get('username','');password=data.get('password','')
                    if not isinstance(username,str) or not isinstance(password,str) or not 1<=len(username)<=64 or not 1<=len(password)<=128:raise ValueError()
                    device=self.server.device_factory(self.server.address)
                    role=device.login(username,password)
                    if not compatible(device.identity()):raise DeviceError('This hardware/firmware is not in the verified compatibility list')
                    state.device=device;state.username=username;state.role=role;state.failures=0
                    if role==1:self.server.super_name=username
                    return self.reply(200,{'role':role,'username':username,'mode':'companion',
                        'can_rename_primary':role==2 and self.server.super_name is not None})
                except (ValueError,TypeError):return self.error(400,'Enter valid account information')
                except DeviceError as error:
                    state.failures+=1
                    if state.failures>=3:state.blocked_until=time.monotonic()+60
                    return self.error(401,str(error))
        if state is None or state.device is None:return self.error(401,'Sign in to the modem first')
        try:
            with state.lock:
                if state.device is None:return self.error(401,'Sign in to the modem first')
                if path=='/api/status' and self.command=='GET':
                    if state.role==1 and state.device.call({'cmd':172,'method':'GET','subcmd':15}).get('success') is not True:
                        state.device=None;return self.error(401,'Modem session expired; sign in again')
                    return self.reply(200,state.device.status())
                if path=='/api/logout' and self.command=='POST':
                    state.device=None;state.username='';state.role=0
                    return self.reply(200,{'success':True})
                if path=='/api/account' and self.command=='POST':
                    data=json.loads(body)
                    if not isinstance(data,dict):raise ValueError()
                    new_name=data.get('username',state.username)
                    if state.role==1 and new_name!=state.username:return self.error(400,'Native SUPER username changes are not verified on this firmware; keep the current name')
                    if state.role==2 and new_name!=state.username:
                        if self.server.super_name is None:return self.error(400,'Primary rename needs a verified SUPER login in this application first, or use the administrator installer wizard')
                        if new_name==self.server.super_name:return self.error(400,'Primary and SUPER usernames must be different')
                    old_password=data.get('current_password','');new_password=data.get('password','')
                    if not isinstance(old_password,str) or not 1<=len(old_password)<=128:raise ValueError()
                    import hashlib
                    from .recovery import SecretStore,backup_device,restore_native_account
                    from .accounts import validate_account
                    validate_account(new_name,new_password)
                    original={'username':state.username,'digest':hashlib.md5(old_password.encode()).hexdigest()}
                    planned={'username':new_name,'digest':hashlib.md5(new_password.encode()).hexdigest()}
                    if state.device.login_digest(original['username'],original['digest'])!=state.role:raise DeviceError('Current account verification failed')
                    store=SecretStore();name='self-account-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
                    if state.role==1:backup_device(state.device,store,name+'-backup')
                    journal={'schema':1,'router':state.device.base,'device_binding':state.device.binding(),
                        'identity':{k:v for k,v in state.device.identity().items() if k in ['name','version','hwversion']},
                        'accounts':{'SUPER' if state.role==1 else 'PRIMARY':{'role':state.role,'original':original,
                            'current':dict(original),'planned':planned,'restored':False}},'complete':False}
                    item=next(iter(journal['accounts'].values()));store.save(name,journal)
                    def on_step(stage,progress):
                        if progress.get('password_changed'):item['current']['digest']=planned['digest']
                        if progress.get('username_changed'):item['current']['username']=new_name
                        if progress.get('rename_reverted'):item['current']['username']=original['username']
                        item['stage']=stage;store.save(name,journal)
                    try:result=change_account(state.device,state.username,original['digest'],new_name,new_password,state.role,on_step)
                    except AccountChangeError as error:
                        if error.uncertain:
                            journal['needs_inspection']=True;store.save(name,journal);raise
                        restore_native_account(state.device,item['current'],original,state.role)
                        item['restored']=True;journal['rolled_back']=True;store.save(name,journal)
                        return self.reply(409,{'error':'The change failed. The previous account was restored and its login verified.','rolled_back':True})
                    journal['complete']=True;store.save(name,journal)
                    state.username=new_name
                    return self.reply(200,{'success':True,**result})
                if path.startswith('/native/') or path.startswith(('/cgi-bin/','/html/','/js/','/css/','/images/','/img/')) or path=='/firewall_and_config_backup_file.pac':
                    return self.native(state,path,body)
                if path=='/login.html':return self.reply(303,b'','text/plain',{'Location':'/'})
        except AccountChangeError as error:
            return self.reply(409,{'error':str(error),'password_changed':error.password_changed,'username_changed':error.username_changed,'uncertain':error.uncertain})
        except (ValueError,TypeError):return self.error(400,'Invalid account settings')
        except DeviceError as error:return self.error(502,str(error))
        return self.error(404,'Not found')
    def static(self,name,headers=None):
        path=(WEB/name).resolve()
        if not path.is_relative_to(WEB.resolve()) or not path.is_file():return self.error(404,'Not found')
        types={'.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.html':'text/html; charset=utf-8'}
        return self.reply(200,path.read_bytes(),types.get(path.suffix,mimetypes.guess_type(path.name)[0] or 'application/octet-stream'),headers)
    def native(self,state,path,body):
        upstream=path[len('/native'):] if path.startswith('/native/') else path
        if upstream=='/login.html':return self.reply(303,b'','text/plain',{'Location':'/'})
        query=urlsplit(self.path).query
        if query:
            from urllib.parse import parse_qsl,urlencode
            pairs=[(k,state.device.sid if k=='sessionId' else v) for k,v in parse_qsl(query,keep_blank_values=True)]
            upstream+='?'+urlencode(pairs)
        content_type=self.headers.get('Content-Type','')
        if body and 'json' in content_type:
            try:
                payload=json.loads(body)
                if not isinstance(payload,dict):return self.error(400,'Invalid native request')
                if 'sessionId' in payload:payload['sessionId']=state.device.sid
                body=json.dumps(payload,separators=(',',':')).encode()
            except ValueError:return self.error(400,'Invalid native request')
        status,headers,data=state.device.request(self.command,upstream,body,{'Content-Type':content_type} if body else {})
        if 'json' in headers.get('Content-Type','') or (data.startswith(b'{') and len(data)<100000):
            try:
                result=json.loads(data)
                renewed=result.get('sessionId') or result.get('message','')
                if result.get('cmd')==998 and result.get('success') and isinstance(renewed,str) and re.fullmatch(r'[a-fA-F0-9]{32,128}',renewed):state.device.sid=renewed
            except (ValueError,AttributeError):pass
        suffix=Path(urlsplit(upstream).path).suffix
        content_type={'.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.html':'text/html; charset=utf-8'}.get(suffix,headers.get('Content-Type','application/octet-stream'))
        if urlsplit(upstream).path=='/index.html' and status==200:
            script=('<base href="/native/"><script>sessionStorage.setItem("sessionId",'+json.dumps(state.device.sid)+');</script>').encode()
            data=data.replace(b'<head>',b'<head>'+script,1)
        return self.reply(status,data,content_type,native=True)
