/* Native P19H adapter. No proxy, saved credentials, radio setters or account writes. */
'use strict';
window.TehnetNative = (() => {
  let sid = sessionStorage.getItem('sessionId') || '';
  let role = 0;
  let username = sessionStorage.getItem('tehnet-username') || '';
  let identity = null;
  const fail = (message, status=502) => Object.assign(new Error(message), {status});
  function clear() {
    sid=''; role=0; username=''; identity=null;
    sessionStorage.removeItem('sessionId');
    sessionStorage.removeItem('tehnet-username');
  }
  function md5(value) {
    const bytes = new TextEncoder().encode(value);
    const data = new Uint8Array(Math.ceil((bytes.length+9)/64)*64);
    data.set(bytes); data[bytes.length]=128;
    const view = new DataView(data.buffer);
    view.setUint32(data.length-8, bytes.length*8, true);
    view.setUint32(data.length-4, Math.floor(bytes.length/0x20000000), true);
    const shifts=[7,12,17,22,5,9,14,20,4,11,16,23,6,10,15,21];
    let state=[0x67452301,0xefcdab89,0x98badcfe,0x10325476];
    for(let offset=0;offset<data.length;offset+=64) {
      let [a,b,c,d]=state;
      for(let i=0;i<64;i++) {
        let f,g;
        if(i<16){f=(b&c)|(~b&d);g=i;}
        else if(i<32){f=(d&b)|(~d&c);g=(5*i+1)%16;}
        else if(i<48){f=b^c^d;g=(3*i+5)%16;}
        else {f=c^(b|~d);g=(7*i)%16;}
        const sum=(a+f+Math.floor(Math.abs(Math.sin(i+1))*0x100000000)+view.getUint32(offset+g*4,true))|0;
        const shift=shifts[Math.floor(i/16)*4+i%4];
        [a,b,c,d]=[d,(b+((sum<<shift)|(sum>>>(32-shift))))|0,b,c];
      }
      state=state.map((n,i)=>(n+[a,b,c,d][i])|0);
    }
    return state.map(n=>[0,8,16,24].map(shift=>((n>>>shift)&255).toString(16).padStart(2,'0')).join('')).join('');
  }
  function checkOrigin() {
    const parts=location.hostname.split('.');const ip=parts.map(Number);
    const privateIp=parts.length===4&&parts.every(x=>/^\d{1,3}$/.test(x))&&ip.every(n=>n>=0&&n<=255)&&(ip[0]===10||(ip[0]===172&&ip[1]>=16&&ip[1]<=31)||(ip[0]===192&&ip[1]===168));
    if(!privateIp||location.protocol!=='http:'||!['','80'].includes(location.port))
      throw fail('این نسخه فقط روی آدرس محلی همین مودم اجرا می‌شود.',403);
  }
  async function command(payload, session=sid) {
    checkOrigin();
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),15000);
    try {
      const response=await fetch('/cgi-bin/http.cgi', {
        method:'POST',cache:'no-store',credentials:'omit',redirect:'error',
        headers:{'Content-Type':'application/json; charset=UTF-8','Accept':'application/json'},
        body:JSON.stringify({language:'EN',sessionId:session,...payload}),signal:controller.signal
      });
      if(!response.ok)throw fail('ارتباط با پنل مودم برقرار نشد.');
      const data=await response.json();
      if(!data||typeof data!=='object'||Array.isArray(data))throw fail('پاسخ مودم قابل خواندن نیست.');
      if(data.message==='NO_AUTH'){
        const current=session===sid;if(current)clear();
        throw fail('نشست پایان یافته؛ دوباره وارد شوید.',current?401:409);
      }
      return data;
    } finally {clearTimeout(timeout);}
  }
  async function checkIdentity() {
    const data=await command({cmd:43,method:'GET'});
    if(data.name!=='ZLT P19H'||data.version!=='3.2.27'||!['TZ7.821.183','TZ7.821.183B'].includes(data.hwversion))
      throw fail('نسخهٔ سخت‌افزار یا فریمور با این رابط سازگار نیست.',403);
    identity=data;
  }
  async function verifyRole() {
    const info=await command({cmd:80,method:'GET'});
    const actual=Number(info.userType);
    if(![1,2].includes(actual))throw fail('نشست معتبر نیست؛ دوباره وارد شوید.',401);
    if(actual===1) {
      const protectedRead=await command({cmd:172,subcmd:15,method:'GET'});
      if(protectedRead.success!==true)throw fail('نشست مدیر معتبر نیست؛ دوباره وارد شوید.',401);
    }
    role=actual;
    return {authenticated:true,role,username,can_rename_primary:false};
  }
  const text=value=>value===null||value===undefined||value===''||value==='NULL'?null:String(value).slice(0,200);
  function number(value) {
    if(value===null||value===undefined||String(value).trim()==='')return null;
    const n=Number(value);return Number.isFinite(n)?n:null;
  }
  function normalize(router, radio, sim={}, running={}) {
    const parts={};
    for(const item of String(radio.message||'').split('$')) {
      const split=item.indexOf('@');if(split>=0)parts[item.slice(0,split)]=item.slice(split+1);
    }
    const wan=text(router.wanIp||running.wanIP);
    const simFields=String(sim.message||'').trim().split(/\s+/);
    const simState=simFields[0]==='0'?'absent':simFields[0]==='1'?(simFields[1]==='0'?'ready':'locked'):'unknown';
    const connected=simState==='ready'&&Boolean(wan&&wan!=='0.0.0.0');
    const hasRadio=simState==='ready';
    const metric=(value,min,max)=>{const n=number(value);return hasRadio&&n!==null&&n>=min&&n<=max?n:null;};
    // Login identity is only a compatibility check. It may outlive a SIM swap.
    const home=simState==='ready'?String(router.imsi||'').slice(0,5):'';
    const reported=text(parts.Operator||parts.PLMN||String(parts['MCC MNC']||'').replace(/\D/g,'')||running.plmn);
    const operator=connected&&reported?reported:(['43211','43235','43244','43245','43220'].includes(home)?home:null);
    return {timestamp:Date.now()/1000,model:text(router.name),firmware:text(router.version),uptime:text(router.uptime),
      wan_ip:hasRadio?wan:null,connection:connected?'connected':simState==='absent'?'no_sim':simState==='locked'?'sim_locked':'searching',
      sim_state:simState,sim_home_plmn:home||null,sim_signature:home?md5(String(router.imsi)):null,
      band:hasRadio?text(parts['Frequency Band']):null,earfcn:hasRadio?text(parts['EARFCN/ARFCN']):null,
      bandwidth_mhz:hasRadio?number(parts['Downlink Bandwidth']):null,rsrp:metric(parts.RSRP,-160,-20),rsrq:metric(parts.RSRQ,-40,0),sinr:metric(parts.SINR,-50,60),
      cell_id:hasRadio?text(parts['Serving CellID']||parts['Cell ID']||parts.CellId):null,operator,
      operator_source:connected&&reported?'serving_network':'sim_home_network',rrc:text(parts.RRCState),
      rx_bytes:number(router.rxBytes??running.wanRxBytes),tx_bytes:number(router.txBytes??running.wanTxBytes)};
  }
  async function request(path, body) {
    if(path==='/api/bootstrap') {
      await checkIdentity();
      if(!/^[a-f0-9]{32,128}$/i.test(sid)||!username)return {authenticated:false,csrf:''};
      try{return {csrf:'',...await verifyRole()};}
      catch(error){if(error.status!==401)throw error;clear();return {authenticated:false,csrf:''};}
    }
    if(path==='/api/login') {
      if(!body||typeof body.username!=='string'||!body.username.length||body.username.length>64||typeof body.password!=='string'||!body.password.length||body.password.length>128)
        throw fail('نام کاربری و رمز را وارد کنید.',400);
      if(typeof sha256_digest!=='function')throw fail('ابزار ورود مودم بارگذاری نشد.');
      await checkIdentity();
      const salt=await command({cmd:997,method:'GET'},'');
      if(salt.success!==true||typeof salt.message!=='string')throw fail('چالش ورود دریافت نشد.');
      const random=new Uint8Array(32);crypto.getRandomValues(random);
      const candidate=Array.from(random,n=>n.toString(16).padStart(2,'0')).join('');
      const result=await command({cmd:100,method:'POST',username:body.username,
        passwd:sha256_digest(salt.message+md5(body.password))},candidate);
      if(result.success!==true||typeof result.sessionId!=='string'||!/^[a-f0-9]{32,128}$/i.test(result.sessionId)) {
        clear();throw fail('ورود تأیید نشد؛ نام کاربری و رمز فعلی مودم را بررسی کنید.',401);
      }
      sid=result.sessionId;username=body.username;
      try {
        const result=await verifyRole();
        sessionStorage.setItem('sessionId',sid);sessionStorage.setItem('tehnet-username',username);
        return result;
      } catch(error){clear();throw error;}
    }
    if(path==='/api/logout'){clear();return {success:true};}
    if(path==='/api/account')throw fail('تنظیمات حساب از پنل اصلی مودم در دسترس است.',405);
    if(path==='/api/details') {
      sid=sessionStorage.getItem('sessionId')||'';
      if(!sid||!role)throw fail('دوباره وارد شوید.',401);
      const details={};
      for(const [name,cmd] of [['device',133],['network',0],['sim',134],['capabilities',80],['bands',157]])details[name]=await command({cmd,method:'GET'});
      details.radio=await command({cmd:82,method:'POST'});return details;
    }
    if(path==='/api/hardware') {
      if(role!==1||!sid)throw fail('این گزارش به حساب مدیر نیاز دارد.',403);
      if((await command({cmd:172,subcmd:15,method:'GET'})).success!==true)throw fail('نشست مدیر معتبر نیست.',401);
      const response=await fetch('/cgi-bin/http.cgi',{method:'POST',cache:'no-store',credentials:'omit',redirect:'error',
        headers:{'Content-Type':'application/json; charset=UTF-8'},body:JSON.stringify({language:'EN',sessionId:sessionStorage.getItem('sessionId'),cmd:46,method:'GET',
          requestCmd:'ps;echo TN_HW_BEGIN;uname -a;cat /proc/meminfo;cat /proc/uptime;cat /proc/loadavg;cat /proc/mtd;cat /etc/openwrt_release;cat /sys/kernel/debug/psiConfig/rf/bands;echo TN_HW_END'})});
      const raw=(await response.text()).replaceAll('\r','');const begin='\nTN_HW_BEGIN\n',end='\nTN_HW_END';
      if(!response.ok||raw.length>65536||raw.split(begin).length!==2||!raw.includes(end))throw fail('گزارش سیستمی در دسترس نیست.');
      return {report:raw.split(begin)[1].split(end)[0]};
    }
    if(path==='/api/status') {
      sid=sessionStorage.getItem('sessionId')||'';
      if(!sid||!role)throw fail('دوباره وارد شوید.',401);
      const started=sid;
      const stillCurrent=()=>{if(sid!==started)throw fail('نمونهٔ نشست قبلی کنار گذاشته شد.',409);};
      const router=await command({cmd:133,method:'GET'});
      stillCurrent();
      const radio=await command({cmd:82,method:'POST'});
      stillCurrent();
      const sim=await command({cmd:134,method:'GET'});
      stillCurrent();
      const running=await command({cmd:0,method:'GET'});
      stillCurrent();
      if(router.success===false||radio.success===false)throw fail('وضعیت مودم در دسترس نیست.');
      return normalize(router,radio,sim,running);
    }
    throw fail('مسیر پشتیبانی نمی‌شود.',404);
  }
  return {request,md5,normalize,read:async payload=>{
    if(!role||!sid)throw fail('دوباره وارد شوید.',401);
    if(payload.method && payload.method!=='GET')throw fail('خواندن فقط با GET مجاز است.',405);
    return command({...payload,method:'GET'});
  },context:()=>({role,username})};
})();
