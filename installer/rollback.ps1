param([string]$Router='192.168.0.254',[Parameter(Mandatory=$true)][string]$State)
& "$PSScriptRoot\install.ps1" -Mode rollback -Router $Router -State $State
exit $LASTEXITCODE
