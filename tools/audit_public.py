"""Fail closed on accidentally packaged private artifacts/common secret formats."""
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parent.parent
ALLOWED_BINARY={'.jpg','.png','.ico'}
PATTERNS=[rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
          rb'github_pat_[A-Za-z0-9_]{30,}',rb'gh[pousr]_[A-Za-z0-9]{30,}',
          rb'AKIA[0-9A-Z]{16}',
          rb'(?i)(?:TZ_(?:SUPER|SUPPORT|TEST)_PASSWD|TZ_PASSWD)\s*=\s*"[a-f0-9]{32}"',
          rb'(?i)"sessionId"\s*:\s*"[a-f0-9]{32,128}"']

def public_files():
    files=(path for path in ROOT.rglob('*') if path.is_file() and not any(
        part in ['.git','__pycache__','.venv','dist','test-results','playwright-report'] for part in path.relative_to(ROOT).parts))
    # WindowsPath ordering folds case; archive paths need the same order on Linux.
    return sorted(files,key=lambda path:path.relative_to(ROOT).as_posix())

def audit():
    errors=[];files=public_files()
    for path in files:
        rel=path.relative_to(ROOT).as_posix()
        if path.suffix.lower() in ['.pac','.dpapi','.conf','.log','.pyc'] or path.name=='.env' or any(part.lower() in ['private','backups'] for part in path.relative_to(ROOT).parts):
            errors.append(rel+': private artifact type');continue
        data=path.read_bytes()
        if path.suffix.lower() not in ALLOWED_BINARY:
            try:data.decode('utf-8')
            except UnicodeError:errors.append(rel+': unexpected binary file');continue
            if any(re.search(pattern,data) for pattern in PATTERNS):errors.append(rel+': secret-like material')
        if path.suffix.lower() in ['.html','.js','.css'] and re.search(rb'(?:src|href)=["\x27]https?://',data):
            # The sole public brand hyperlink is a user-triggered link, not a
            # runtime asset request. All scripts/styles/fonts/images are local.
            for tag in re.findall(rb'<(?:script|link|img)[^>]+>',data):
                if re.search(rb'(?:src|href)=["\x27]https?://',tag):errors.append(rel+': external runtime asset')
    if not (ROOT/'LICENSE').is_file() or not (ROOT/'docs'/'ASSET-NOTICES.md').is_file():errors.append('Missing license/asset notice')
    manifest=json.loads((ROOT/'DEPENDENCIES.json').read_text(encoding='utf-8'))
    if manifest.get('runtime')!=[]:errors.append('New runtime dependencies require a license review')
    for dependency in manifest.get('optional_development',[]):
        if (dependency.get('name'),dependency.get('version'),dependency.get('license'))!=('playwright','1.65.2','Apache-2.0'):
            errors.append('Unreviewed optional dependency/license')
    if errors:
        print('\n'.join(errors),file=sys.stderr);return 1
    print(json.dumps({'public_files_scanned':len(files),'forbidden_private_artifacts':0,
                      'secret_patterns':0,'runtime_dependencies':0,'license_notices':'present'},indent=2));return 0

if __name__=='__main__':raise SystemExit(audit())
