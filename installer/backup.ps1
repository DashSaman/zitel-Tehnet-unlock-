param([string]$Router='192.168.0.254')
& "$PSScriptRoot\install.ps1" -Mode backup -Router $Router
exit $LASTEXITCODE
