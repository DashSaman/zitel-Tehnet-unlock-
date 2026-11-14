"""Deterministic source/runtime candidate ZIP; no credentials or build dependencies."""
import hashlib
from pathlib import Path
import sys
import zipfile
from audit_public import audit,public_files,ROOT
if audit():raise SystemExit(1)
out=ROOT/'dist';out.mkdir(exist_ok=True)
name='TehranNetwork-ZLT-P19H-v0.1.0-candidate.zip';path=out/name
with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for source in public_files():
        info=zipfile.ZipInfo('TehranNetwork-ZLT-P19H/'+source.relative_to(ROOT).as_posix(),(2026,11,14,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
        archive.writestr(info,source.read_bytes())
with zipfile.ZipFile(path) as archive:
    if archive.testzip() is not None:raise SystemExit('ZIP integrity failed')
sha=hashlib.sha256(path.read_bytes()).hexdigest()
(out/'SHA256SUMS.txt').write_text(sha+'  '+name+'\n',encoding='ascii')
print('Package:',path.name,'bytes:',path.stat().st_size,'SHA256:',sha)
