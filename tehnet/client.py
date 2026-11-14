"""Narrow native P19H client. Never logs credentials or device responses."""
import hashlib
import ipaddress
import json
import math
import re
import secrets
import time
from urllib.parse import urlsplit
import urllib.request

class DeviceError(Exception):pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def validate_router(address):
    address=address.strip().rstrip('/')
    if '://' not in address:address='http://'+address
    p=urlsplit(address)
    try:ip=ipaddress.IPv4Address(p.hostname or '')
    except ValueError:raise ValueError('A private IPv4 router address is required') from None
    if p.scheme!='http' or p.username or p.password or p.path or p.query or p.fragment or p.port not in [None,80] or not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        raise ValueError('Only a private IPv4 router on native HTTP port80 is supported')
    return 'http://'+str(ip)

def compatible(identity):
    return identity.get('name')=='ZLT P19H' and identity.get('version')=='3.2.27' and identity.get('hwversion') in ['TZ7.821.183','TZ7.821.183B']

class Device:
    def __init__(self,address='192.168.0.254'):
        self.base=validate_router(address);self.sid='';self.role=0
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def request(self,method,path,body=None,headers=None,timeout=12):
        if not path.startswith('/') or path.startswith('//') or urlsplit(path).netloc:
            raise DeviceError('Invalid modem path')
        h={'Referer':self.base+'/index.html','User-Agent':'TehranNetwork-P19H/0.1',
           'Accept-Encoding':'identity',**(headers or {})}
        if method=='POST':h['Origin']=self.base
        req=urllib.request.Request(self.base+path,body,h,method=method)
        try:
            with self.opener.open(req,timeout=timeout) as response:
                data=response.read(32*1024*1024+1)
                if len(data)>32*1024*1024:raise DeviceError('Modem response exceeds size limit')
                return response.status,dict(response.headers),data
        except DeviceError:raise
        except Exception:raise DeviceError('The modem did not return a usable response') from None
    def call(self,payload):
        status,headers,raw=self.request('POST','/cgi-bin/http.cgi',
            json.dumps({'language':'EN','sessionId':self.sid,**payload},separators=(',',':')).encode(),
            {'Content-Type':'application/json; charset=UTF-8'})
        try:result=json.loads(raw)
        except (ValueError,UnicodeError):raise DeviceError('Unexpected modem response format') from None
        if not isinstance(result,dict):raise DeviceError('Unexpected modem response type')
        return result
    def login(self,username,password):
        return self.login_digest(username,hashlib.md5(password.encode('utf-8')).hexdigest())
    def login_digest(self,username,digest):
        if not isinstance(username,str) or not 1<=len(username)<=64 or not re.fullmatch(r'[a-fA-F0-9]{32}',digest):
            raise DeviceError('Invalid credential format')
        salt=self.call({'cmd':997,'method':'GET','sessionId':''})
        if not salt.get('success') or not isinstance(salt.get('message'),str):raise DeviceError('Login challenge unavailable')
        result=self.call({'cmd':100,'method':'POST','sessionId':secrets.token_hex(32),
            'username':username,'passwd':hashlib.sha256((salt['message']+digest).encode()).hexdigest()})
        session=result.get('sessionId','')
        if result.get('success') is not True or not isinstance(session,str) or not re.fullmatch(r'[a-fA-F0-9]{32,128}',session):
            raise DeviceError('Login failed; verify the supplied account and avoid repeated attempts')
        self.sid=session
        info=self.call({'cmd':80,'method':'GET'})
        try:role=int(info.get('userType',0))
        except (TypeError,ValueError):role=0
        if role not in [1,2]:raise DeviceError('The modem did not identify an established account role')
        if role==1 and self.call({'cmd':172,'subcmd':15,'method':'GET'}).get('success') is not True:
            raise DeviceError('The protected administrator check failed')
        self.role=role
        return role
    def identity(self):
        self.last_identity=self.call({'cmd':43,'method':'GET'})
        return self.last_identity
    def binding(self):
        identity=self.identity()
        values={key:str(identity.get(key,'')).strip() for key in ['mac','imei']
                if identity.get(key) not in [None,'','NULL'] and len(str(identity.get(key)))>=8}
        if not values:raise DeviceError('No stable hardware identity is available for safe recovery binding')
        return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
    def status(self):
        router=self.call({'cmd':133,'method':'GET'})
        radio=self.call({'cmd':82,'method':'POST'})
        if router.get('message')=='NO_AUTH' or radio.get('message')=='NO_AUTH':raise DeviceError('Session expired; sign in again')
        operator=getattr(self,'_operator',None);source=getattr(self,'_operator_source',None)
        if self.role==1 and time.monotonic()-getattr(self,'_operator_at',-999)>60:
            self._operator_at=time.monotonic()
            try:
                result=self.call({'cmd':45,'method':'POST','atcmd':'AT+COPS?'})
                found=re.search(r'''\+COPS:\s*\d+,\s*\d+,\s*["']([^"']+)["']''',result.get('message',''))
                if found:operator=found[1][:80];source='serving_network';self._operator=operator;self._operator_source=source
            except DeviceError:pass
        if not operator:
            # Iran uses these established two-digit MNCs. Do not infer MNC
            # length for arbitrary countries or expose the subscriber suffix.
            imsi=str(getattr(self,'last_identity',{}).get('imsi',''))
            if imsi[:5] in ['43211','43235','43244','43245','43220']:
                operator=imsi[:5];source='sim_home_network'
        normalized=normalize_status({**router,'operator':operator},radio)
        normalized['operator_source']=source
        return normalized
    def export(self):
        if self.role!=1 or not compatible(self.identity()):raise DeviceError('Backup requires the verified compatible administrator role')
        if self.call({'cmd':180,'method':'GET'}).get('success') is not True:raise DeviceError('Native backup was rejected')
        return self.request('GET','/firewall_and_config_backup_file.pac')[2]

def number(value):
    try:n=float(str(value).strip())
    except (ValueError,TypeError):return None
    return n if math.isfinite(n) else None

def normalize_status(router,radio):
    raw=radio.get('message','')
    parts=dict(item.split('@',1) for item in raw.split('$') if '@' in item) if isinstance(raw,str) else {}
    def text(value):return str(value)[:200] if value not in [None,'','NULL'] else None
    wan=text(router.get('wanIp'))
    return {'timestamp':time.time(),'model':text(router.get('name')),'firmware':text(router.get('version')),
        'uptime':text(router.get('uptime')),'wan_ip':wan,'connection':'connected' if wan and wan!='0.0.0.0' else 'unknown',
        'band':text(parts.get('Frequency Band')),'earfcn':text(parts.get('EARFCN/ARFCN')),
        'bandwidth_mhz':number(parts.get('Downlink Bandwidth')),'rsrp':number(parts.get('RSRP')),
        'rsrq':number(parts.get('RSRQ')),'sinr':number(parts.get('SINR')),
        'cell_id':text(parts.get('Serving CellID') or parts.get('Cell ID') or parts.get('CellId')),
        'operator':text(parts.get('Operator') or parts.get('PLMN') or re.sub(r'\D','',parts.get('MCC MNC','')) or router.get('operator')),
        'rrc':text(parts.get('RRCState')),
        'rx_bytes':number(router.get('rxBytes')),'tx_bytes':number(router.get('txBytes'))}
