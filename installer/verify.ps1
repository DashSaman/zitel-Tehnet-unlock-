param([string]$Router='192.168.0.254',[switch]$RebootCheck)
& "$PSScriptRoot\install.ps1" -Mode verify -Router $Router -RebootCheck:$RebootCheck
exit $LASTEXITCODE
