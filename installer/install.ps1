[CmdletBinding()]
param(
    [ValidateSet('check','dry-run','install','backup','verify','rollback','serve')][string]$Mode='install',
    [string]$Router='192.168.0.254',
    [int]$Port=8765,
    [switch]$NoBrowser,
    [switch]$ApplyAccounts,
    [switch]$RebootCheck,
    [string]$State
)
$ErrorActionPreference='Stop'
$projectPath=Split-Path -Parent $PSScriptRoot
$pythonCommand=Get-Command py.exe -ErrorAction SilentlyContinue
$pythonOptions=@()
if($pythonCommand){$pythonOptions=@('-3')}
else{$pythonCommand=Get-Command python.exe -ErrorAction SilentlyContinue}
if(-not $pythonCommand){throw 'Install Python3.10+ from python.org, then run this installer again.'}
$pythonOptions+=@('-X','utf8','-m','tehnet.cli',"--$Mode",'--router',$Router,'--port',"$Port")
if($NoBrowser){$pythonOptions+='--no-browser'}
if($ApplyAccounts){$pythonOptions+='--apply-accounts'}
if($RebootCheck){$pythonOptions+='--reboot-check'}
if($State){$pythonOptions+=@('--state',$State)}
Push-Location -LiteralPath $projectPath
try{
    & $pythonCommand.Source @pythonOptions
    $resultCode=$LASTEXITCODE
}finally{Pop-Location}
exit $resultCode
