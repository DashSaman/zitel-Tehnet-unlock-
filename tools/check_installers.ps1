$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$errorsFound=@()
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'installer') -Filter '*.ps1' | ForEach-Object {
    $parseTokens=$null
    $parseErrors=$null
    [System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$parseTokens,[ref]$parseErrors) | Out-Null
    $errorsFound+=$parseErrors
}
if($errorsFound.Count){$errorsFound | Write-Output;exit 1}
Write-Output 'All PowerShell installer scripts parsed successfully.'
