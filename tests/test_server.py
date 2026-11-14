from http.client import HTTPConnection
import json
import threading
import unittest
from tehnet.server import AppServer

class FakeDevice:
    def __init__(self,address):self.base='http://192.168.0.254';self.sid='a'*64;self.role=0
    def login(self,name,password):self.role=1 if password=='owner' else 2;return self.role
    def identity(self):return {'name':'ZLT P19H','version':'3.2.27','hwversion':'TZ7.821.183'}
    def call(self,p):return {'success':True,'sessionId':self.sid}
    def status(self):return {'connection':'connected','rsrp':-95,'sinr':4,'band':'42'}
    def request(self,method,path,body=None,headers=None):
        if body and json.loads(body).get('cmd')==998:return 200,{'Content-Type':'application/json'},json.dumps({'cmd':998,'success':True,'message':'b'*64}).encode()
        return 200,{'Content-Type':'text/html'},b'<html><head></head><body>native</body></html>'

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server=AppServer('192.168.0.254',0,device_factory=FakeDevice)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.cookie='';self.csrf=''
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,method='GET',data=None,headers=None):
        h={'Host':self.server.authority}
        if self.cookie:h['Cookie']=self.cookie
        if method=='POST':h.update({'Origin':self.server.origin,'X-CSRF-Token':self.csrf,'Content-Type':'application/json'})
        h.update(headers or {})
        c=HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        c.request(method,path,json.dumps(data).encode() if data is not None else None,h)
        r=c.getresponse();body=r.read();result=(r.status,dict(r.getheaders()),body);c.close();return result
    def bootstrap(self):
        status,h,b=self.request('/');self.assertEqual(status,200)
        self.cookie=h['Set-Cookie'].split(';')[0]
        status,h,b=self.request('/api/bootstrap');self.csrf=json.loads(b)['csrf']
    def login(self,password='owner'):
        self.bootstrap();return self.request('/api/login','POST',{'username':'local','password':password})
    def test_status_requires_authenticated_cookie(self):
        self.assertEqual(self.request('/api/status')[0],401)
        self.assertEqual(self.login()[0],200)
        status,h,b=self.request('/api/status');self.assertEqual(status,200)
        self.assertEqual(json.loads(b)['band'],'42')
        self.assertNotIn(b'a'*64,b)
    def test_host_origin_and_csrf_guard_login(self):
        self.bootstrap()
        self.assertEqual(self.request('/api/login','POST',{}, {'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('/api/login','POST',{}, {'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/api/login','POST',{}, {'X-CSRF-Token':'wrong'})[0],403)
    def test_non_object_json_rejected_without_internal_error(self):
        self.bootstrap()
        for data in [[],['username'],'text']:
            with self.subTest(data=data):self.assertEqual(self.request('/api/login','POST',data)[0],400)
        self.assertEqual(self.server.internal_errors,0)
    def test_primary_rename_needs_verified_super_name_before_any_write(self):
        self.login('ordinary')
        status,h,b=self.request('/api/account','POST',{'username':'possible-admin-name','current_password':'ordinary','password':'new-value'})
        self.assertEqual(status,400)
        self.assertEqual(self.server.internal_errors,0)
    def test_native_panel_requires_login_and_injects_session_without_url(self):
        self.assertEqual(self.request('/native/index.html')[0],401)
        self.login();status,h,b=self.request('/native/index.html')
        self.assertEqual(status,200);self.assertIn(b'sessionStorage',b)
        self.assertIn('no-store',h['Cache-Control'])
    def test_logout_and_expiry_remove_access(self):
        self.login();self.assertEqual(self.request('/api/logout','POST',{})[0],200)
        self.assertEqual(self.request('/api/status')[0],401)
    def test_native_session_renewal_message_updates_backend_session(self):
        self.login()
        self.assertEqual(self.request('/native/cgi-bin/http.cgi','POST',{'cmd':998,'sessionId':'a'*64})[0],200)
        current=next(iter(self.server.sessions.values()))
        self.assertEqual(current.device.sid,'b'*64)
    def test_oversize_and_traversal_rejected(self):
        self.bootstrap()
        self.assertEqual(self.request('/api/login','POST',{}, {'Content-Length':'100000000'})[0],413)
        self.assertEqual(self.request('/../tehnet/client.py')[0],404)
    def test_pending_native_request_during_logout_returns_401(self):
        self.login();state=next(iter(self.server.sessions.values()))
        entered=threading.Event();release=threading.Event();outcome=[]
        class Gate:
            def __enter__(self):entered.set();release.wait(2)
            def __exit__(self,*args):pass
        state.lock=Gate()
        def pending():
            try:outcome.append(self.request('/native/cgi-bin/http.cgi','POST',{'cmd':80,'sessionId':'a'*64})[0])
            except Exception:outcome.append('connection-closed')
        thread=threading.Thread(target=pending);thread.start()
        self.assertTrue(entered.wait(2));state.device=None;release.set();thread.join(3)
        self.assertEqual(outcome,[401])

if __name__=='__main__':unittest.main()
