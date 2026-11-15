param([ValidateSet('check','install','rollback')][string]$Mode='check',[string]$Router='192.168.0.254',[string]$State='')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$pythonExe=Get-Command python -ErrorAction SilentlyContinue
if(-not $pythonExe){throw 'Python 3.10+ is required. Install it from python.org, then run this command again.'}
Push-Location -LiteralPath $projectRoot
try {
    & $pythonExe.Source -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)'
    if($LASTEXITCODE -ne 0){throw 'Python 3.10+ is required.'}
    $nativeArgs=@('-X','utf8','-m','tehnet.native_install',('--'+$Mode),'--router',$Router)
    if($Mode -eq 'rollback'){
        if(-not $State){throw 'Rollback requires -State with the encrypted journal path.'}
        $nativeArgs=@('-X','utf8','-m','tehnet.native_install','--rollback',$State,'--router',$Router)
    }
    & $pythonExe.Source @nativeArgs
    if($LASTEXITCODE -ne 0){throw 'Native operation stopped. Inspect its journal before trying again.'}
} finally {Pop-Location}
