"""Build the native-router variant from the shared UI, without device access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]


def build(destination,public_path='/tehnet'):
    destination=Path(destination).resolve()
    if not re.fullmatch(r'/tehnet(?:-[a-zA-Z0-9]+)?',public_path):
        raise ValueError('Use a local Tehran Network path')
    if destination==ROOT or ROOT.is_relative_to(destination):
        raise ValueError('Choose a dedicated output directory')
    destination.mkdir(parents=True,exist_ok=True)
    html=(ROOT/'webui/index.html').read_text(encoding='utf-8')
    app=(ROOT/'webui/app.js').read_text(encoding='utf-8')
    before='async function api(path,body){'
    assert app.count(before)==1
    app=app.replace(before,before+'if(window.TehnetNative)return window.TehnetNative.request(path,body);',1)
    app=app.replace("'/native/index.html'","'/tehnet-vendor.html'")
    assert app.count("companionNote:'")==1
    app=app.replace("companionNote:'An independent panel on your computer. Modem firmware is unchanged.'",
                    "companionNote:'Installed on your modem. No computer application is needed.'")
    app=app.replace("systemNote:'This interface runs on your computer. No new firmware is installed. FDD support and memory capacity cannot be inferred from this panel.'",
                    "systemNote:'This interface is served by your P19H modem. Radio firmware and calibration are unchanged.'")
    html=html.replace('<script src="/app.js" defer></script>',
        '<script src="/js/sha256.js" defer></script><script src="/tehnet/native.js?v=1" defer></script><script src="/tehnet/app.js?v=1" defer></script>')
    html=html.replace('href="/assets/','href="/tehnet/assets/').replace('src="/assets/','src="/tehnet/assets/')
    html=html.replace('href="/styles.css"','href="/tehnet/styles.css?v=1"')
    html=html.replace('/native/index.html','/tehnet-vendor.html')
    html=html.replace('TEHRAN NETWORK / DEVICE COMPANION','TEHRAN NETWORK / P19H WEB UI')
    html=html.replace('TehNet Companion','TehNet Web UI').replace('P19H COMPANION','P19H WEB UI')
    html=html.replace('Companion v0.1.0','Native UI v0.2.0').replace('v0.1.0','v0.2.0')
    html=html.replace('پنل مستقل روی کامپیوتر شما؛ فریمور مودم تغییر نکرده است.',
                      'نصب‌شده روی خود مودم؛ برای استفاده به برنامهٔ کامپیوتر نیاز ندارید.')
    html=html.replace('این رابط روی کامپیوتر اجرا می‌شود. فریمور جدیدی نصب نشده؛ فلش، FDD و ظرفیت حافظه از ظاهر پنل نتیجه‌گیری نمی‌شوند.',
                      'این رابط از حافظهٔ خود مودم بارگذاری می‌شود. فریمور رادیو و کالیبراسیون تغییر نکرده‌اند.')
    # Keep account mutations in the existing native implementation; the desktop
    # DPAPI transaction machinery does not exist on this firmware.
    start=html.index('<form id="account-form">')
    html=html[:start]+html[start:].replace('<form id="account-form">','<form id="account-form" hidden>',1)
    marker='<form id="account-form" hidden>'
    html=html.replace(marker,
        '<p>برای تغییر اطلاعات حساب، تنظیمات اصلی مودم را باز کنید. / Account settings are available in the original modem panel.</p>'
        '<button class="secondary" data-goto="native">تنظیمات اصلی حساب / Account settings</button>'+marker)
    start=app.index('function renderAccount(){')
    end=app.index('function signedIn(',start)
    app=app[:start]+"""function renderAccount(){
      text('account-name',username);text('account-role',tr(role===1?'adminRole':'userRole'));
      text('role-badge',tr(role===1?'adminRole':'userRole'));
      text('account-capability',language==='fa'?'حساب فعلی از API مودم تأیید شده است.':'The current account is verified by the modem API.');
      $('new-username').value=username;$('new-username').readOnly=true;
    }
    """+app[end:]
    css=(ROOT/'webui/styles.css').read_text(encoding='utf-8')
    # Replace the old framed view with controls in this document.
    start=html.index('   <section id="native-view"')
    end=html.index('   <footer class="app-footer"',start)
    html=html[:start]+(ROOT/'device-webui/workspace.html').read_text(encoding='utf-8')+(ROOT/'device-webui/alignment.html').read_text(encoding='utf-8')+html[end:]
    html=html.replace('<div class="nav-divider"></div>',
        '<button class="nav-item" data-view="alignment"><span class="nav-icon">◎</span><span data-i18n="alignment">راهنما و تنظیم جهت</span></button><div class="nav-divider"></div>')
    html=html.replace('پنل اصلی مودم','تنظیمات دستگاه').replace('همهٔ تنظیمات اصلی مودم','همهٔ تنظیمات دستگاه')
    html=html.replace('تنظیمات اصلی حساب / Account settings','تنظیمات حساب / Account settings')
    html=html.replace('data-goto="native">تنظیمات حساب','data-goto="native" data-setting-target="SYS_SET">تنظیمات حساب')
    html=html.replace('برای تغییر اطلاعات حساب، تنظیمات اصلی مودم را باز کنید. / Account settings are available in the original modem panel.',
                      'حساب‌ها و تنظیمات کامل در محیط مدیریت دستگاه در دسترس‌اند. / Open device settings for account controls.')
    html=html.replace('<span class="chip" id="band-chip">B—</span></div>',
        '<span class="chip" id="band-chip">B—</span></div><div class="sim-state"><span id="sim-state"></span><span class="signal-bars" id="signal-bars" role="img"><i></i><i></i><i></i><i></i><i></i></span></div>')
    for key in ['rsrp','sinr','rsrq']:
        html=html.replace('<strong id="'+key+'">—</strong>', '<strong id="'+key+'">—</strong><span class="direction-hint" id="'+key+'-direction" title="ابتدا جهت‌ها را در راهنما مقایسه کنید">↔</span>')
    html=html.replace('</head>', '<link rel="stylesheet" href="/tehnet/workspace.css?v=3"><link rel="stylesheet" href="/tehnet/telemetry.css?v=3"></head>')
    html=html.replace('<script src="/tehnet/app.js?v=1" defer></script>',
        '<script src="/tehnet/workspace.js?v=3" defer></script><script src="/tehnet/alignment.js?v=3" defer></script><script src="/tehnet/telemetry.js?v=3" defer></script><script src="/tehnet/app.js?v=3" defer></script>')
    html=html.replace('v=1','v=3').replace('0.2.0','0.3.0')
    app=app.replace("$('native-frame').removeAttribute('src');","window.TehnetWorkspace?.reset();")
    old="if(view==='native'&&!$('native-frame').getAttribute('src'))$('native-frame').src='/tehnet-vendor.html';"
    assert app.count(old)==1
    app=app.replace(old,"if(view==='native')window.TehnetWorkspace.open();else window.TehnetWorkspace.leave();if(view==='alignment')window.TehnetAlignment.render();if(view==='system')window.TehnetTelemetry.refresh();")
    app=app.replace("const titles={","const titles={alignment:['alignmentTitle','alignmentCopy'],")
    app=app.replace("['accounts','system','native']","['accounts','system','native','alignment']")
    before='const originals={};'
    app=app.replace(before,"""Object.assign(english,{native:'Device settings',nativeMenus:'All device settings',nativeCopy:'Network, firewall, system and diagnostics',nativeTitle:'Device settings',nativeSubtitle:'All controls in one workspace',alignment:'Guide & alignment',alignmentTitle:'Find a better direction',alignmentCopy:'Compare real signal samples, step by step.',systemTitle:'Device information and reports'});
Object.assign(persian,{native:'تنظیمات دستگاه',nativeMenus:'تمام تنظیمات دستگاه',nativeCopy:'شبکه، فایروال، سیستم و گزارش‌ها',nativeTitle:'تنظیمات دستگاه',nativeSubtitle:'همهٔ کنترل‌ها در یک محیط یکپارچه',alignment:'راهنما و تنظیم جهت',alignmentTitle:'بهترین جهت را با اندازه‌گیری پیدا کنید',alignmentCopy:'مقایسهٔ نمونه‌های واقعی؛ قدم‌به‌قدم.',systemTitle:'مشخصات دستگاه و گزارش‌ها'});
"""+before)
    app=app.replace('function render(data){latest=data;',"function render(data){latest=data;window.TehnetAlignment.observe(data);window.TehnetTelemetry.observe(data);")
    app=app.replace("history.push(data);","if(latest&&latest.sim_signature!==data.sim_signature)history=[];history.push(data);")
    app=app.replace("text('connection-badge',tr(live?'connected':'unknown'));",
        "text('connection-badge',live?tr('connected'):data.sim_state==='absent'?(language==='fa'?'سیم شناسایی نشده':'No SIM'):data.sim_state==='locked'?(language==='fa'?'بررسی سیم':'SIM attention'):(language==='fa'?'در حال اتصال':'Connecting'));"+
        "text('sim-state',data.sim_state==='ready'?(language==='fa'?'سیم آماده':'SIM ready'):(language==='fa'?'وضعیت سیم: ':'SIM: ')+(data.sim_state||'—'));"+
        "const bars=Number.isFinite(data.rsrp)&&data.sim_state==='ready'?[ -120,-110,-100,-90,-80 ].filter(n=>data.rsrp>=n).length:0;"+
        "$('signal-bars').setAttribute('aria-label',(language==='fa'?'قدرت تقریبی سیگنال: ':'Estimated signal: ')+bars+'/5');$('signal-bars').querySelectorAll('i').forEach((el,i)=>el.classList.toggle('on',i<bars));")
    app=app.replace("const $=id=>document.getElementById(id);","const $=id=>document.getElementById('tn-'+id);")
    app=app.replace("'chart-title'","'tn-chart-title'")
    app=app.replace("stroke:'var(--accent)','stroke-width':2", "stroke:({sinr:'#56dce8',rsrp:'#6ae5b3',rsrq:'#bf9bff'})[metric],'stroke-width':2")
    setup="window.TehnetWorkspace.bind({navigate:setView});window.TehnetAlignment.bind();window.TehnetTelemetry.bind();\n"
    app=app.replace("setTheme(localStorage.getItem('tehnet-theme')",setup+"setTheme(localStorage.getItem('tehnet-theme')",1)
    # The firmware controllers use unprefixed IDs and global jQuery. Keep the
    # dashboard lexical bindings and element IDs in their own namespace.
    ids=set(re.findall(r'\bid="([^"]+)"',html))
    html=re.sub(r'\bid="([^"]+)"',lambda match:'id="tn-'+match[1]+'"',html)
    def reference(match):
        return match[1]+'="'+' '.join('tn-'+value if value in ids else value for value in match[2].split())+'"'
    html=re.sub(r'\b(for|aria-controls|aria-labelledby)="([^"]+)"',reference,html)
    html=re.sub(r'href="#([^"]+)"',lambda match:'href="#tn-'+match[1]+'"' if match[1] in ids else match[0],html)
    id_pattern=re.compile(r'#('+ '|'.join(sorted(map(re.escape,ids),key=len,reverse=True))+r')(?![\w-])')
    css=id_pattern.sub(lambda match:'#tn-'+match[1],css)
    html=html.replace('/tehnet/',public_path+'/')
    html=html.replace('<title>','<script>window.TEHNET_BASE='+json.dumps(public_path)+';</script><title>',1)
    (destination/'index.html').write_text(html,encoding='utf-8')
    (destination/'app.js').write_text('(()=>{\n'+app+'\n})();',encoding='utf-8')
    (destination/'styles.css').write_text(css,encoding='utf-8')
    shutil.copyfile(ROOT/'device-webui/native.js',destination/'native.js')
    for name in ['workspace.js','workspace.css','alignment.js','telemetry.js','telemetry.css','menu-map.json']:
        shutil.copyfile(ROOT/'device-webui'/name,destination/name)
    (destination/'assets').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'webui/assets/tehnet-logo.jpg',destination/'assets/tehnet-logo.jpg')
    # Fingerprint links so existing browser tabs cannot keep stale UI assets.
    for name in ['app.js','styles.css','native.js','workspace.js','workspace.css','alignment.js','telemetry.js','telemetry.css']:
        digest=hashlib.sha256((destination/name).read_bytes()).hexdigest()[:12]
        html=html.replace(name+'?v=3',name+'?v='+digest)
    (destination/'index.html').write_text(html,encoding='utf-8')
    manifest={'variant':'native-p19h','version':'0.3.0','public_path':public_path,'files':{}}
    for name in ['index.html','app.js','styles.css','native.js','workspace.js','workspace.css','alignment.js','telemetry.js','telemetry.css','menu-map.json','assets/tehnet-logo.jpg']:
        data=(destination/name).read_bytes()
        manifest['files'][name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--public-path',default='/tehnet')
    args=parser.parse_args()
    print(json.dumps(build(args.output,args.public_path),indent=2))
