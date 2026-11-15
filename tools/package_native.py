"""Deterministic native installer runtime, containing only this project's sources."""
import base64,hashlib,json
from pathlib import Path
import zipfile
from audit_public import audit,ROOT

def build():
    if audit():raise SystemExit(1)
    files=[ROOT/'LICENSE',ROOT/'tools/build_device_webui.py']
    files += [ROOT/'tehnet'/name for name in ['__init__.py','client.py','pac.py','recovery.py','native_install.py']]
    for directory in ['webui','device-webui']:
        files += [p for p in (ROOT/directory).rglob('*') if p.is_file()]
    out=ROOT/'dist';out.mkdir(exist_ok=True);target=out/'tehnet-native-v0.3.0.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in sorted(files,key=lambda p:p.relative_to(ROOT).as_posix()):
            info=zipfile.ZipInfo(p.relative_to(ROOT).as_posix(),(2026,11,15,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,p.read_bytes())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():raise SystemExit('Package integrity failed')
    data=target.read_bytes();packages=ROOT/'packages';packages.mkdir(exist_ok=True)
    (packages/'tehnet-native-v0.3.0.zip.b64').write_text(base64.b64encode(data).decode('ascii'),encoding='ascii')
    metadata={'version':'0.3.0','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'runtime_files':len(files)}
    (packages/'native-v0.3.0.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(metadata));return metadata

if __name__=='__main__':build()
