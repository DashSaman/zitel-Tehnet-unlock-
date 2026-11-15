"""Native bundle generation and challenge authentication, without modem access."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_builder',ROOT/'tools/build_device_webui.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class NativeWebUiTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node is optional')
    def test_alignment_and_traffic_require_valid_comparable_samples(self):
        script=r'''
const vm=require('node:vm'),fs=require('node:fs'),a=require('node:assert/strict');
const c={window:{},document:{}};vm.createContext(c);
for(const file of process.argv.slice(1))vm.runInContext(fs.readFileSync(file,'utf8'),c);
const compare=c.window.TehnetAlignment.compare,rates=c.window.TehnetTelemetry.rates;
const before={stable:true,band:'42',cell:'sample',samples:4,sinr:3,rsrp:-95};
const after={...before,direction:'left',sinr:6,rsrp:-99};
a.equal(compare(before,after,'sinr').arrow,'←');a.equal(compare(before,after,'rsrp').arrow,'→');
a.equal(compare(before,{...after,cell:'changed'},'sinr').arrow,'↔');
a.equal(compare(before,{...after,samples:1},'sinr').arrow,'↔');
a.equal(compare(null,after,'sinr').arrow,'↔');
a.equal(rates({timestamp:0,rx_bytes:100,tx_bytes:0},{timestamp:5,rx_bytes:625100,tx_bytes:0}).rx,1);
a.equal(rates({timestamp:0,rx_bytes:100},{timestamp:5,rx_bytes:0}).rx,null);
a.equal(rates({timestamp:0,rx_bytes:0},{timestamp:61,rx_bytes:10}).rx,null);
'''
        result=subprocess.run(['node','-e',script,str(ROOT/'device-webui/alignment.js'),str(ROOT/'device-webui/telemetry.js')],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)

    def test_bundle_preserves_companion_and_removes_proxy_dependency(self):
        original=(ROOT/'webui/app.js').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            manifest=builder.build(Path(tmp)/'bundle')
            html=(Path(tmp)/'bundle/index.html').read_text(encoding='utf-8')
            app=(Path(tmp)/'bundle/app.js').read_text(encoding='utf-8')
            self.assertIn('window.TehnetNative.request',app)
            self.assertNotIn('/native/index.html',html+app)
            self.assertTrue('id="tn-account-form" hidden' in html,'Desktop account transaction form stays hidden in native mode')
            self.assertNotIn('پنل مستقل روی کامپیوتر',html)
            self.assertIn('نصب‌شده روی خود مودم',html)
            for name,record in manifest['files'].items():
                self.assertEqual(hashlib.sha256((Path(tmp)/'bundle'/name).read_bytes()).hexdigest(),record['sha256'])
        self.assertEqual(original,(ROOT/'webui/app.js').read_bytes())

    def test_full_workspace_has_no_old_panel_frame_and_has_alignment_guide(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder.build(Path(tmp)/'bundle')
            html=(Path(tmp)/'bundle/index.html').read_text(encoding='utf-8')
            self.assertFalse('<iframe' in html,'The full workspace must not embed the previous panel')
            self.assertNotIn('/tehnet-vendor',html)
            self.assertIn('تنظیم جهت',html)
            self.assertTrue((Path(tmp)/'bundle/workspace.js').is_file())
            self.assertTrue((Path(tmp)/'bundle/alignment.js').is_file())

    @unittest.skipUnless(shutil.which('node'),'Node is optional for JS protocol tests')
    def test_hashes_authentication_acl_and_missing_measurements(self):
        script=r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');const fs=require('node:fs');const crypto=require('node:crypto');
const storage=new Map();const sent=[];let deny=false,loginCount=0,queueStatus=false,releaseStatus;
const context={window:{},sessionStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
  location:{hostname:'192.168.0.254',protocol:'http:',port:''},TextEncoder,DataView,Uint8Array,crypto:crypto.webcrypto,
  AbortController,setTimeout,clearTimeout,sha256_digest:s=>crypto.createHash('sha256').update(s).digest('hex'),
  fetch:async(path,options)=>{const body=JSON.parse(options.body);sent.push(body);
    assert.equal(path,'/cgi-bin/http.cgi');assert.equal(options.redirect,'error');
    let data={success:true};
    if(body.cmd===133&&queueStatus)data=await new Promise(resolve=>{releaseStatus=()=>resolve({success:false,message:'NO_AUTH'});});
    if(body.cmd===43)data={name:'ZLT P19H',version:'3.2.27',hwversion:'TZ7.821.183B',imsi:'432119999999999'};
    if(body.cmd===997)data={success:true,message:'challenge'};
    if(body.cmd===100){assert.equal(body.passwd,crypto.createHash('sha256').update('challenge'+crypto.createHash('md5').update('test-only').digest('hex')).digest('hex'));data={success:true,sessionId:(++loginCount===1?'a':'b').repeat(64)};}
    if(body.cmd===80)data={userType:1};
    if(body.cmd===172)data={success:!deny};
    return {ok:true,json:async()=>data};}
};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const api=context.window.TehnetNative;
(async()=>{
  for(const value of ['', 'abc', 'x'.repeat(129), 'سلام'])assert.equal(api.md5(value),crypto.createHash('md5').update(value).digest('hex'));
  const normalized=api.normalize({wanIp:'0.0.0.0'}, {message:'RSRP@$SINR@NULL$RSRQ@'});
  assert.equal(normalized.rsrp,null);assert.equal(normalized.sinr,null);assert.notEqual(normalized.connection,'connected');
  await api.request('/api/login',{username:'test-account',password:'test-only'});
  const swapped=api.normalize({wanIp:'0.0.0.0',imsi:'432449999999999'}, {message:''}, {message:'1 0 0 0 0 0'});
  assert.equal(swapped.operator,'43244');
  const absent=api.normalize({wanIp:'0.0.0.0',imsi:'432119999999999'}, {message:''}, {message:'0 0 0 0 0 0'});
  assert.equal(absent.operator,null);
  const stale=api.normalize({wanIp:'10.0.0.1',imsi:'432119999999999'}, {message:'RSRP@-80$SINR@20'}, {message:'0 0 0 0 0 0'});
  assert.equal(stale.connection,'no_sim');assert.equal(stale.wan_ip,null);assert.equal(stale.rsrp,null);
  assert.equal(sent.filter(x=>x.cmd===172).length,1);
  assert.equal(storage.get('sessionId'),'a'.repeat(64));assert.equal([...storage.keys()].some(x=>/pass|hash/i.test(x)),false);
  await assert.rejects(api.request('/api/account',{}),error=>error.status===405);
  queueStatus=true;const oldStatus=api.request('/api/status');
  await api.request('/api/logout',{});queueStatus=false;
  await api.request('/api/login',{username:'test-account',password:'test-only'});
  releaseStatus();await assert.rejects(oldStatus,error=>error.status===409);
  assert.equal(storage.get('sessionId'),'b'.repeat(64));assert.equal(api.context().role,1);
  await api.request('/api/logout',{});assert.equal(storage.has('sessionId'),false);
  deny=true;await assert.rejects(api.request('/api/login',{username:'test-account',password:'test-only'}),error=>error.status===401);
  assert.equal(storage.has('sessionId'),false);
  context.location.hostname='example.com';await assert.rejects(api.request('/api/bootstrap'),error=>error.status===403);
  context.location.hostname='127.0.0.1';await assert.rejects(api.request('/api/bootstrap'),error=>error.status===403);
  context.location.hostname='192.168.1.1';assert.equal((await api.request('/api/bootstrap')).authenticated,false);
  console.log(JSON.stringify({hash_vectors:4,protected_role_checked:true,account_writes_blocked:true,foreign_origin_blocked:true}));
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result=subprocess.run(['node','-e',script,str(ROOT/'device-webui/native.js')],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['hash_vectors'],4)


if __name__=='__main__':unittest.main()
