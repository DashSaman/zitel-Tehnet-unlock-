"""Generate a bootstrap with the exact audited runtime SHA256 embedded."""
import json
from pathlib import Path
from package_native import build,ROOT

if __name__=='__main__':
    metadata=build()
    template=r'''param([ValidateSet('check','install')][string]$Mode='install',[string]$Router='192.168.0.254')
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$expectedHash='@SHA256@'
$runtimeUrl='https://raw.githubusercontent.com/DashSaman/zitel-Tehnet-unlock-/main/packages/tehnet-native-v0.3.0.zip.b64'
$pythonExe=Get-Command python -ErrorAction SilentlyContinue
if(-not $pythonExe){throw 'Install Python 3.10+ from python.org, then run this command again.'}
& $pythonExe.Source -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)'
if($LASTEXITCODE -ne 0){throw 'Python 3.10+ is required.'}
$packageRoot=Join-Path $env:LOCALAPPDATA ('TehranNetwork\Packages\native-0.3.0-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
$zipPath=Join-Path $packageRoot 'runtime.zip'
$encoded=[string](Invoke-RestMethod -Uri $runtimeUrl)
[IO.File]::WriteAllBytes($zipPath,[Convert]::FromBase64String($encoded.Trim()))
if((Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash){throw 'Runtime checksum mismatch. Nothing was executed on the modem.'}
$runtimePath=Join-Path $packageRoot 'runtime'
Expand-Archive -LiteralPath $zipPath -DestinationPath $runtimePath
Push-Location -LiteralPath $runtimePath
try {
    Write-Host 'Verified Tehran Network native UI 0.3.0. Existing passwords will be preserved.'
    & $pythonExe.Source -X utf8 -m tehnet.native_install ('--'+$Mode) --router $Router
    if($LASTEXITCODE -ne 0){throw 'Operation stopped. Inspect the encrypted journal before retrying.'}
} finally {Pop-Location}
'''
    (ROOT/'installer/bootstrap-native.ps1').write_text(template.replace('@SHA256@',metadata['sha256']),encoding='utf-8')
    print('Generated checksum-pinned bootstrap; package requires Python 3.10+ and an existing authorized SUPER console.')
