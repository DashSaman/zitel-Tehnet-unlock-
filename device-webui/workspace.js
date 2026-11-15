/* Same-device form controllers, rendered inside the Tehran Network workspace. */
'use strict';
window.TehnetWorkspace=(()=>{
  const $=id=>document.getElementById('tn-'+id);
  const fa=()=>document.documentElement.lang==='fa';
  const say=(f,e)=>fa()?f:e;
  const names={SYS_INFO:'وضعیت دستگاه',DEVICE_INFO:'نسخه‌ها و سخت‌افزار',CLIENT_LIST:'دستگاه‌های متصل',FLOW_INFO:'آمار مصرف',LTE_INFO:'وضعیت شبکهٔ موبایل',BASIC_CONFIG:'شبکه، سیم و APN',NETWORK_CONFIG:'شبکهٔ محلی و DHCP',ROUTER_TABLE:'مسیریابی',DIAL_CONFIG:'VPN / L2TP',SIM_LOCKING:'تنظیمات اپراتور',ADVANCED_CONFIG:'تنظیمات پیشرفته',FW_RULE:'قوانین فایروال',FW_MAC_FILTER:'فیلتر MAC',FW_PORT_MAPPING:'انتقال پورت',FW_DMZ:'میزبان DMZ',FW_ALG:'سرویس‌های ALG',FW_URL_FILTER:'فیلتر نشانی وب',FW_IP_MAC_BINDING:'اتصال IP به MAC',FW_SPEED_LIMIT:'محدودیت سرعت',FW_BACKUP_FIREWALL:'پشتیبان فایروال',SYS_SET:'سیستم و حساب‌ها',SYS_LOG:'گزارش‌های دستگاه',SYS_UPDATE:'به‌روزرسانی سیستم',CONFIG_UPDATE:'پشتیبان و تنظیمات',NETWORK_TOOLS:'ابزارهای شبکه',SYS_REBOOT:'راه‌اندازی مجدد',SYS_HELPER:'راهنما و تنظیم جهت'};
  let hooks=null,map=null,ready=null,current='BASIC_CONFIG',generation=0,armedUntil=0,active=false,languageLoaded='';
  const menuLabel=key=>fa()?(names[key]||key):(map?.menus.find(item=>item.id===key)?.text||key);
  const status=message=>{if($('settings-status'))$('settings-status').textContent=message;};
  function script(path){return new Promise((resolve,reject)=>{const node=document.createElement('script');node.src=path;node.onload=resolve;node.onerror=()=>reject(new Error('Unable to load device controls'));document.head.append(node);});}
  function clean(html){return String(html).replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,'').replace(/<link\b[^>]*>/gi,'').replace(/<iframe\b[\s\S]*?<\/iframe>/gi,'');}
  function confirm(message){return new Promise(resolve=>{const dialog=$('settings-dialog');$('settings-dialog-message').textContent=String(message).replace(/<[^>]*>/g,'');dialog.returnValue='cancel';dialog.addEventListener('close',()=>resolve(dialog.returnValue==='ok'),{once:true});dialog.showModal();});}
  function isRead(json){
    const method=String(json.method||'GET').toUpperCase();
    if([6,11,13,14,15,20,39,48,49,53,97,98,99,101,102,105,106,112,159,170,178,188,194,196,198,199,200,290].includes(Number(json.cmd)))return false;
    if(Number(json.cmd)===46)return /^(?:ps|free|uptime|cat \/proc\/[a-z_]+)\s*$/.test(String(json.requestCmd||''));
    if(Number(json.cmd)===45)return /^(?:ATI|AT\+(?:CIMI|CSQ|CEER)|AT\+[A-Z0-9_]+\?)\s*$/i.test(String(json.atcmd||''));
    if(method==='GET')return true;
    if(Number(json.cmd)===82)return true;
    return false;
  }
  function wrapControllers(){
    const original=Page.postJSON;
    Url.DEFAULT_CGI='/cgi-bin/http.cgi';Page.defaultSetting.url=Url.DEFAULT_CGI;
    Page.createSession=()=>{}; // one native session; independent views must not rotate it
    Page.setTitle=()=>{document.title='Tehran Network · P19H';};
    Page.setHelperStyle=()=>{};
    Page.getUrl=url=>{if(/^(?:https?:)?\/\//i.test(url))throw new Error('External device URL rejected');return '/'+String(url).replace(/^\/+/, '')+'?'+Page.getRandomParam();};
    const nativeHtml=Page.getHtml;
    Page.getHtml=(url,subcmd,callback)=>{
      if(!/^html\/[a-z0-9_\/-]+\.html$/i.test(url))throw new Error('Unsupported device page');
      const requested=generation;
      return nativeHtml(url,subcmd,data=>{if(requested===generation)callback(clean(data));});
    };
    Page.postJSON=options=>{
      const json=options.json||{};const cmd=Number(json.cmd);
      const forbidden=[178,196,198,200];
      const firmwareWrite=(cmd===5||cmd===184)&&String(json.method||'GET').toUpperCase()!=='GET';
      if(forbidden.includes(cmd)||firmwareWrite||(!isRead(json)&&(!active||Date.now()>armedUntil))){
        status(say('این عملیات بدون درخواست مستقیم شما یا فایل سازگارِ تأییدشده اجرا نمی‌شود.','This operation needs your direct action or a verified compatible image.'));
        if(options.fail)options.fail({success:false,message:'USER_ACTION_REQUIRED'});
        if(options.complete)options.complete();return;
      }
      const success=options.success;
      return original({...options,success(data){
        if(options.returnHtml)data=clean(data);
        if(data?.message==='NO_AUTH'){status(say('نشست پایان یافته؛ دوباره وارد شوید.','Session expired; sign in again.'));return;}
        if(success)success(data);
      }});
    };
    Page.get=(url,title)=>{
      Page.destory();const run=++generation;Page.$iframe.empty();status(say('در حال دریافت تنظیمات…','Loading device settings…'));
      Page.getHtml(url,Page.menuItem?.cmd||0,data=>{if(run!==generation)return;Page.$iframe.html(data);status('');styleSurface();});
    };
    if(window.AlertUtil){
      // Native controllers require synchronous Boolean confirmation; returning
      // a Promise here would be truthy and could bypass a cancellation.
      AlertUtil.alertMsg=message=>{const text=String(message).replace(/<[^>]*>/g,'');status(text);window.alert(text);};
      AlertUtil.confirm=message=>{const answer=window.confirm(String(message).replace(/<[^>]*>/g,''));if(answer)armedUntil=Date.now()+10000;return answer;};
    }
    jQuery.ajaxPrefilter((options,originalOptions,xhr)=>{
      if(/^(?:js\/|html\/|cgi-bin\/|firewall|systemconfig|all_captured)/.test(options.url))options.url='/'+options.url;
      const url=new URL(options.url,location.href);if(url.origin!==location.origin)xhr.abort('foreign-origin');
    });
  }
  async function ensure(){
    if(ready)return ready;
    ready=(async()=>{
      map=await (await fetch((window.TEHNET_BASE||'/tehnet')+'/menu-map.json?v=3',{cache:'no-store'})).json();
      for(const path of ['/js/json2.js','/js/jquery-1.7.2.min.js','/js/jquery.form.js','/js/jquery.validate.js','/js/jquery.accordion.js','/js/underscore-min.js','/js/language_list.js','/js/language.js','/js/language/en.js','/js/helper.js','/js/main.js'])await script(path);
      languageLoaded='en';wrapControllers();
      const init=await TehnetNative.read({cmd:80});
      Page.setSupported(ConvertUtil.parseHex(init.supported||0));Page.setUnsupported(ConvertUtil.parseHex(init.unsupported||0));
      Page.setItemHide(ConvertUtil.parseHex(init.itemHide||0));Page.setItemDisable(ConvertUtil.parseHex(init.itemDisable||0));
      Page.isNormalUser=TehnetNative.context().role!==1;Page.isTestUser=false;Page.isRuKuVersion=init.isRuku==='1';
      // Reveal presentation-hidden controls for the verified SUPER only. Keep
      // hardware support/disable flags and backend authorization unchanged.
      const hidden=Page.isItemHide;Page.isItemHide=function(item){return Page.isNormalUser?hidden.call(Page,item):false;};
      Page.$iframe=jQuery($('settings-surface'));Page.lanIp=location.hostname;
      renderMenu();
    })();
    try{return await ready;}catch(error){ready=null;throw error;}
  }
  function renderMenu(){
    const nav=$('settings-menu');nav.replaceChildren();const search=$('settings-search').value.trim().toLowerCase();
    for(const item of map.menus){if(search&&!((names[item.id]||'')+' '+item.text).toLowerCase().includes(search))continue;
      const button=document.createElement('button');button.type='button';button.dataset.setting=item.id;button.className='settings-item'+(item.id===current?' selected':'');button.textContent=menuLabel(item.id);button.addEventListener('click',()=>open(item.id));nav.append(button);}
  }
  function styleSurface(){
    const surface=$('settings-surface');
    for(const node of surface.querySelectorAll('img')){if(/logo|banner|zitel|tozed|zotel/i.test(node.getAttribute('src')||''))node.remove();}
    for(const table of surface.querySelectorAll('table'))table.classList.add('tn-device-table');
    for(const field of surface.querySelectorAll('input:not([type]),input[type=text],input[type=password],select,textarea'))field.classList.add('tn-device-field');
    for(const field of surface.querySelectorAll('input'))if(['text','password'].includes(field.type)&&/password|passwd|pwd/i.test(field.name||field.id))field.type='password';
  }
  async function open(key){
    active=true;
    try{
      await ensure();Page.isNormalUser=TehnetNative.context().role!==1;current=key||current;renderMenu();$('settings-heading').textContent=menuLabel(current);
      const wanted=fa()?'fa':'en';if(languageLoaded!==wanted){await script('/js/language/'+wanted+'.js');languageLoaded=wanted;}Page.language=wanted.toUpperCase();
      if(current==='SYS_HELPER'){hooks.navigate('alignment');return;}
      if(current==='SYS_REBOOT'){
        Page.destory();$('settings-surface').replaceChildren();const p=document.createElement('p');p.textContent=say('راه‌اندازی مجدد، اتصال دستگاه را برای مدت کوتاهی قطع می‌کند.','Restarting briefly interrupts the device connection.');const button=document.createElement('button');button.className='primary';button.textContent=say('راه‌اندازی مجدد دستگاه','Restart device');button.onclick=async()=>{if(await confirm(say('دستگاه اکنون راه‌اندازی مجدد شود؟','Restart this device now?'))){armedUntil=Date.now()+10000;Page.postJSON({json:{cmd:6,method:'POST'},success:()=>status(say('در حال راه‌اندازی مجدد…','Restarting…'))});}};$('settings-surface').append(p,button);status('');return;
      }
      if(current==='SYS_UPDATE'){
        Page.destory();$('settings-surface').replaceChildren();const p=document.createElement('p');p.textContent=say('نسخهٔ فعلی: 3.2.27 — برای برد TZ7.821.183B فایل جدید سازگار و تأییدشده در دسترس نیست. نصب تصویر ناشناس غیرفعال است.','Current version: 3.2.27. No verified compatible replacement image is available for TZ7.821.183B. Unknown firmware installation is disabled.');$('settings-surface').append(p);status('');return;
      }
      const route=map.routes[current];if(!route?.url)throw new Error('Unsupported settings page');
      Page.menuItem={...route,isRoot:true,requireTitle:false,requireIndent:false};Page.get(route.url,menuLabel(current));
    }catch(error){status(error.message||say('دریافت تنظیمات انجام نشد.','Unable to load settings.'));}
  }
  function bind(options){
    hooks=options;$('settings-search').addEventListener('input',()=>{if(map)renderMenu();});$('settings-reload').addEventListener('click',()=>open(current));
    $('settings-surface').addEventListener('click',event=>{if(event.isTrusted&&event.target.matches('button,input[type=button],input[type=submit],input[type=checkbox],input[type=radio]'))armedUntil=Date.now()+10000;},true);
    $('settings-surface').addEventListener('change',event=>{if(event.isTrusted)armedUntil=Date.now()+10000;},true);
    $('settings-surface').addEventListener('submit',event=>{if(event.isTrusted)armedUntil=Date.now()+10000;},true);
    new MutationObserver(styleSurface).observe($('settings-surface'),{childList:true,subtree:true});
    document.addEventListener('click',event=>{const button=event.target.closest('[data-setting-target]');if(button){hooks.navigate('native');open(button.dataset.settingTarget);}});
  }
  function leave(){active=false;armedUntil=0;if(window.Page){Page.destory();generation++;}}
  function reset(){leave();if($('settings-surface'))$('settings-surface').replaceChildren();}
  return {bind,open,leave,reset,renderMenu};
})();
