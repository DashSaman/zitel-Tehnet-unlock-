'use strict';
window.TehnetTelemetry=(()=>{
  const $=id=>document.getElementById('tn-'+id);const fa=()=>document.documentElement.lang==='fa';let busy=false,last=null,traffic=[];
  function rates(before,after){
    const seconds=after.timestamp-before.timestamp;if(!Number.isFinite(seconds)||seconds<=0||seconds>60)return {rx:null,tx:null};
    const rate=key=>Number.isFinite(before[key])&&Number.isFinite(after[key])&&after[key]>=before[key]?(after[key]-before[key])*8/seconds/1000000:null;
    return {rx:rate('rx_bytes'),tx:rate('tx_bytes')};
  }
  function observe(data){
    if(last){traffic.push(rates(last,data));if(traffic.length>120)traffic.shift();}last=data;
    for(const [key,limit] of [['rsrp',-90],['rsrq',-10],['sinr',13]]){const card=$(key)?.closest('.metric');if(card)card.dataset.quality=Number.isFinite(data[key])?(data[key]>=limit?'good':'poor'):'';}
    const svg=$('traffic-chart');if(!svg)return;svg.replaceChildren();const latest=traffic.at(-1);
    $('traffic-rates').textContent=latest?'RX '+(latest.rx===null?'—':latest.rx.toFixed(2))+' / TX '+(latest.tx===null?'—':latest.tx.toFixed(2))+' Mbps':'—';
    const maximum=Math.max(.01,...traffic.flatMap(item=>[item.rx,item.tx]).filter(Number.isFinite));
    for(const [key,color] of [['rx','#6ae5b3'],['tx','#bf9bff']]){
      const points=traffic.map((item,i)=>({value:item[key],x:12+i/Math.max(1,traffic.length-1)*676})).filter(item=>Number.isFinite(item.value));
      if(points.length<2)continue;const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d',points.map((point,i)=>(i?'L':'M')+point.x.toFixed(1)+' '+(145-point.value/maximum*125).toFixed(1)).join(' '));path.setAttribute('fill','none');path.setAttribute('stroke',color);path.setAttribute('stroke-width','2');svg.append(path);
    }
  }
  const secret=key=>/pass|pwd|session|token|secret|private|wpa|secFile/i.test(key);
  const sensitive=key=>/imei|imsi|iccid|mac|serial|\bsn\b|cell|wan|lan.*ip|gateway|dns|server|address|ssid/i.test(key);
  const labels={imsi:'IMSI',imei:'IMEI',iccid:'ICCID',sn:'Serial',plmn:'PLMN',mac:'MAC',wanRxBytes:'RX bytes',wanTxBytes:'TX bytes',wanRxPackets:'RX packets',wanTxPackets:'TX packets',rssi:'RSSI',uptime:'Uptime',tozedind:'SIM / registration states',connectStatus:'Connection status',wanIP:'WAN IP',wanIp:'WAN IP',hwversion:'Hardware revision',modversion:'Radio version',configVer:'Configuration version'};
  function display(value){return (typeof value==='object'?JSON.stringify(value):String(value??'—')).replace(/(https?:\/\/)[^\s/]*@/gi,'$1<credentials>@').replace(/([?&](?:password|token|secret)=)[^&\s]*/gi,'$1<redacted>').slice(0,8000);}
  function table(name,fields){
    const group=document.createElement('details');group.open=true;group.className='telemetry-group';const title=document.createElement('summary');title.textContent=name;group.append(title);
    const table=document.createElement('table');table.className='telemetry-table';
    for(const [key,value] of Object.entries(fields)){if(secret(key)||['success','cmd'].includes(key))continue;
      const row=document.createElement('tr'),label=document.createElement('th'),data=document.createElement('td');label.textContent=labels[key]||key;data.textContent=display(value);data.dir='auto';
      if(sensitive(key)){data.className='private-value';data.dataset.private='true';}row.append(label,data);table.append(row);
    }group.append(table);return group;
  }
  async function refresh(){
    if(busy||!$('details-values'))return;busy=true;$('details-status').textContent=fa()?'در حال دریافت مشخصات زنده…':'Loading live device data…';
    try{const details=await TehnetNative.request('/api/details'),target=$('details-values');target.replaceChildren();
      const names=fa()?{device:'شناسه‌ها، نسخه‌ها و آدرس‌ها',network:'شبکه، ارسال و دریافت',sim:'وضعیت سیم‌کارت',capabilities:'قابلیت‌ها و پرچم‌های دستگاه',bands:'باندهای اعلام‌شده',radio:'اندازه‌گیری‌های رادیویی'}:{device:'Identifiers, versions and addresses',network:'Network, transmit and receive',sim:'SIM state',capabilities:'Device capability flags',bands:'Reported bands',radio:'Radio measurements'};
      for(const [key,value] of Object.entries(details)){
        if(key==='radio'&&typeof value.message==='string'){const parts={};for(const item of value.message.split('$')){const i=item.indexOf('@');if(i>=0)parts[item.slice(0,i)]=item.slice(i+1);}target.append(table(names.radio,parts));}
        else target.append(table(names[key]||key,value));
      }$('details-status').textContent=fa()?'داده‌ها از خود مودم خوانده شدند؛ مقدار خالی یعنی گزارش نشده، نه صفر.':'Read from the modem. An empty value means unavailable, not zero.';
    }catch(error){$('details-status').textContent=error.message;}finally{busy=false;}
  }
  async function hardware(){try{const value=await TehnetNative.request('/api/hardware');$('hardware-report').textContent=value.report;$('hardware-report').hidden=false;}catch(error){$('details-status').textContent=error.message;}}
  function bind(){
    const trafficCard=document.createElement('article');trafficCard.className='card traffic-card';
    trafficCard.innerHTML='<div class="card-top"><h2><span class="lang-fa">روند واقعی ارسال و دریافت</span><span class="lang-en">Actual traffic over time</span></h2><strong class="mono" id="tn-traffic-rates">—</strong></div><svg id="tn-traffic-chart" viewBox="0 0 700 160" role="img" aria-label="نمودار ارسال و دریافت"></svg><p class="muted small"><span class="lang-fa">دریافت سبز، ارسال بنفش؛ نرخ مشاهده‌شدهٔ همین اتصال است، نه آزمون سقف سرعت.</span><span class="lang-en">Receive is green, transmit is purple. This is observed traffic, not a maximum-speed test.</span></p>';
    const dashboard=$('dashboard-view');dashboard.insertBefore(trafficCard,dashboard.querySelector('.detail-grid'));
    const box=document.createElement('div');box.className='telemetry-box';const toolbar=document.createElement('div');toolbar.className='alignment-controls';
    const filter=document.createElement('input');filter.id='tn-details-search';filter.type='search';filter.placeholder='جست‌وجوی مشخصات / Search fields';
    const reload=document.createElement('button');reload.className='secondary';reload.textContent='بازخوانی مشخصات / Refresh';reload.onclick=refresh;
    const report=document.createElement('button');report.className='secondary';report.textContent='گزارش سیستم و حافظه / Hardware report';report.onclick=hardware;
    const values=document.createElement('div');values.id='tn-details-values';const status=document.createElement('p');status.id='tn-details-status';status.className='muted';
    const pre=document.createElement('pre');pre.id='tn-hardware-report';pre.className='hardware-report';pre.hidden=true;toolbar.append(filter,reload,report);box.append(toolbar,status,values,pre);$('system-view').append(box);
    filter.oninput=()=>{const q=filter.value.trim().toLowerCase();for(const row of values.querySelectorAll('tr'))row.hidden=!row.textContent.toLowerCase().includes(q);};
  }
  return {bind,observe,refresh,rates};
})();
