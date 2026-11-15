'use strict';
window.TehnetAlignment=(()=>{
  const $=id=>document.getElementById('tn-'+id);
  const fa=()=>document.documentElement.lang==='fa';
  const say=(f,e)=>fa()?f:e;
  let current=null,recording=null,rows=[],direction='baseline';
  const symbols={left:'←',right:'→',up:'↑',down:'↓'},opposite={left:'right',right:'left',up:'down',down:'up'};
  function compare(before,after,key){
    if(!before||!after||!after.direction||after.direction==='baseline'||!before.stable||!after.stable||before.band!==after.band||before.cell!==after.cell||before.samples<3||after.samples<3||!Number.isFinite(before[key])||!Number.isFinite(after[key]))return {arrow:'↔',change:null};
    const change=after[key]-before[key],limit=key==='rsrp'?2:1;
    return {arrow:Math.abs(change)<limit?'↔':symbols[change>0?after.direction:opposite[after.direction]],change};
  }
  function arrows(before,after){for(const key of ['rsrp','sinr','rsrq']){const node=$(key+'-direction');if(!node)continue;const result=compare(before,after,key);node.textContent=result.arrow;node.classList.toggle('better',result.change!==null&&result.change>0);node.classList.toggle('worse',result.change!==null&&result.change<0);node.title=result.change===null?say('ابتدا مبنا و یک حرکت آزمایشی با سلول ثابت ثبت کنید.','Record a baseline and a trial movement on the same cell first.'):say('تغییر ثبت‌شده: ','Measured change: ')+result.change.toFixed(1)+' dB';node.setAttribute('aria-label',node.title);}}
  const median=values=>{const a=values.filter(Number.isFinite).sort((x,y)=>x-y);return a.length?(a.length%2?a[(a.length-1)/2]:(a[a.length/2-1]+a[a.length/2])/2):null;};
  const show=n=>Number.isFinite(n)?n.toFixed(1):'—';
  function render(){
    const target=$('alignment-results');if(!target)return;target.replaceChildren();
    for(const row of rows){const tr=document.createElement('tr');for(const value of [row.label,show(row.sinr),show(row.rsrq),show(row.rsrp),row.band+' / '+row.cell,row.samples]){const td=document.createElement('td');td.textContent=String(value);tr.append(td);}target.append(tr);}
    const qualified=rows.filter(row=>row.samples>=3&&Number.isFinite(row.sinr)&&Number.isFinite(row.rsrp)&&row.stable);
    qualified.sort((a,b)=>b.sinr-a.sinr||(b.rsrq??-99)-(a.rsrq??-99)||b.rsrp-a.rsrp);
    $('alignment-recommendation').textContent=qualified.length?say('بهترین کیفیت ثبت‌شده: '+qualified[0].label+'؛ سرعت واقعی و پایداری را هم مقایسه کنید.','Best recorded quality: '+qualified[0].label+'. Also compare real throughput and stability.'):say('برای مقایسه، حداقل سه نمونهٔ معتبر در هر موقعیت و باند/سلول ثابت لازم است.','Comparison needs at least three valid samples per position with a stable band/cell.');
  }
  function finish(){
    const points=recording.points;const signatures=new Set(points.map(p=>(p.band||'—')+'/'+(p.cell_id||'—')));
    const before=rows.at(-1);
    rows.push({label:recording.label,direction:recording.direction,sinr:median(points.map(p=>p.sinr)),rsrq:median(points.map(p=>p.rsrq)),rsrp:median(points.map(p=>p.rsrp)),
      band:points.at(-1)?.band||'—',cell:points.at(-1)?.cell_id||'—',stable:signatures.size===1&&Boolean(points.at(-1)?.band&&points.at(-1)?.cell_id),samples:points.filter(p=>Number.isFinite(p.rsrp)&&Number.isFinite(p.sinr)).length});
    arrows(before,rows.at(-1));
    const changed=signatures.size>1;recording=null;$('alignment-start').disabled=false;
    $('alignment-progress').textContent=changed?say('باند یا سلول هنگام ثبت عوض شد؛ برای مقایسهٔ منصفانه دوباره نمونه بگیرید.','The band or cell changed during recording; repeat for a fair comparison.'):say('نمونه‌برداری تمام شد. موقعیت بعدی را امتحان کنید.','Capture complete. Try the next position.');render();
  }
  function observe(data){
    current=data;if(!$('alignment-health'))return;
    const prior=rows.at(-1);if(data.sim_state!=='ready'||(prior&&(data.band!==prior.band||data.cell_id!==prior.cell)))arrows(null,null);
    $('alignment-health').textContent=data.sim_state==='absent'?say('سیم‌کارت شناسایی نشده؛ ابتدا شیار سیم و روشن‌کردن مجدد پس از تعویض را بررسی کنید.','SIM not detected. Check seating and restart after replacing it.'):data.sim_state==='locked'?say('سیم نیاز به بررسی PIN/PUK دارد؛ رمز را حدس نزنید.','The SIM needs PIN/PUK attention; do not guess codes.'):data.connection!=='connected'?say('هنوز آدرس WAN ندارید. ابتدا ثبت شبکه و APN را در تنظیمات بررسی کنید.','No WAN address yet. Check registration and APN in settings.'):say('اتصال آماده است. RSRP: '+show(data.rsrp)+' | SINR: '+show(data.sinr)+' | RSRQ: '+show(data.rsrq),'Connected. RSRP: '+show(data.rsrp)+' | SINR: '+show(data.sinr)+' | RSRQ: '+show(data.rsrq));
    if(recording){recording.points.push(data);const elapsed=(Date.now()-recording.started)/1000;$('alignment-progress').textContent=say('مودم ثابت بماند؛ ','Keep the modem still; ')+Math.max(0,Math.ceil(30-elapsed))+say(' ثانیه باقی مانده',' seconds remaining');if(elapsed>=30)finish();}
  }
  function bind(){
    document.querySelectorAll('[data-probe]').forEach(button=>button.addEventListener('click',()=>{direction=button.dataset.probe;document.querySelectorAll('[data-probe]').forEach(node=>node.classList.toggle('selected',node===button));}));
    $('alignment-start').addEventListener('click',()=>{
      if(!current||current.sim_state!=='ready'||!Number.isFinite(current.rsrp)||!Number.isFinite(current.sinr)){$('alignment-progress').textContent=say('هنوز اندازه‌گیری معتبر در دسترس نیست؛ اتصال و سیگنال را بررسی کنید.','Valid measurements are not available yet. Check connection and signal.');return;}
      recording={label:$('position-name').value.trim()||say('موقعیت ','Position ')+(rows.length+1),direction,started:Date.now(),points:[]};$('alignment-start').disabled=true;observe(current);
    });
    $('alignment-clear').addEventListener('click',()=>{rows=[];arrows(null,null);render();});
    $('alignment-export').addEventListener('click',()=>{
      const quote=value=>'"'+(typeof value==='string'&&/^[=+\-@\t\r]/.test(value)?"'":'')+String(value??'').replaceAll('"','""')+'"';
      const csv=[['position','direction','sinr_db','rsrq_db','rsrp_dbm','band','cell','valid_samples','stable'],...rows.map(row=>[row.label,row.direction,row.sinr,row.rsrq,row.rsrp,row.band,row.cell,row.samples,row.stable])].map(row=>row.map(quote).join(',')).join('\r\n');
      const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='signal-positions.csv';a.click();URL.revokeObjectURL(url);
    });render();
  }
  return {bind,observe,render,median,compare};
})();
