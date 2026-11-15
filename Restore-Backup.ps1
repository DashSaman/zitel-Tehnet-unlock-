param([Parameter(Mandatory=$true)][string]$Archive,[string]$KeyFile='', [switch]$VerifyOnly,[string]$OutputZip='')
$ErrorActionPreference='Stop'
# Offline decrypt/verify only. This script never connects to or flashes a modem.
$raw=[IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Archive).Path)
if($raw.Length -lt 116 -or [Text.Encoding]::ASCII.GetString($raw,0,8) -ne 'TNRECOV1'){throw 'Unknown recovery envelope'}
$rounds=[BitConverter]::ToUInt32($raw,8)
$length=[BitConverter]::ToUInt64($raw,60)
if($rounds -ne 600000 -or $length -gt 67108864 -or $length -lt 16 -or ($length % 16) -ne 0 -or $length+100 -ne $raw.Length){throw 'Invalid recovery envelope bounds'}
if($KeyFile){$key=[IO.File]::ReadAllText((Resolve-Path -LiteralPath $KeyFile).Path).Trim()} else {
    $secure=Read-Host 'Separate owner recovery key (not the router password)' -AsSecureString
    $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {$key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)} finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}
}
if($key -notmatch '^[A-Za-z0-9_-]{43}$'){throw 'Invalid recovery key format'}
$salt=[byte[]]$raw[12..43];$iv=[byte[]]$raw[44..59]
$derive=[Security.Cryptography.Rfc2898DeriveBytes]::new($key,$salt,[int]$rounds,[Security.Cryptography.HashAlgorithmName]::SHA256)
try {$material=$derive.GetBytes(64)} finally {$derive.Dispose();$key=''}
$macKey=[byte[]]$material[32..63];$hmac=[Security.Cryptography.HMACSHA256]::new($macKey)
try {$actual=$hmac.ComputeHash($raw,0,[int](68+$length))} finally {$hmac.Dispose()}
$difference=0
for($i=0;$i -lt 32;$i++){$difference=$difference -bor ($actual[$i] -bxor $raw[68+$length+$i])}
if($difference -ne 0){throw 'Recovery key is wrong or encrypted backup is damaged. No plaintext written.'}
$aes=[Security.Cryptography.Aes]::Create();$aes.Key=[byte[]]$material[0..31];$aes.IV=$iv
$aes.Mode=[Security.Cryptography.CipherMode]::CBC;$aes.Padding=[Security.Cryptography.PaddingMode]::PKCS7
try {$decryptor=$aes.CreateDecryptor();try {$plain=$decryptor.TransformFinalBlock($raw,68,[int]$length)} finally {$decryptor.Dispose()}} finally {$aes.Dispose();[Array]::Clear($material,0,$material.Length)}
[Reflection.Assembly]::LoadWithPartialName('System.IO.Compression') | Out-Null
$memory=[IO.MemoryStream]::new($plain,$false)
$zip=[IO.Compression.ZipArchive]::new($memory,[IO.Compression.ZipArchiveMode]::Read,$false)
try {
    $total=[long]0
    foreach($entry in $zip.Entries){
        $name=$entry.FullName.Replace('\','/')
        if($name.StartsWith('/') -or $name.Contains(':') -or ($name.Split('/') -contains '..')){throw 'Unsafe archive path'}
        $total+=$entry.Length
    }
    if($total -gt 67108864 -or -not ($zip.Entries.FullName -contains 'original-spi-32MiB.bin') -or -not ($zip.Entries.FullName -contains 'manifest-private.json')){throw 'Incomplete recovery ZIP'}
} finally {$zip.Dispose();$memory.Dispose()}
if($VerifyOnly){Write-Output 'Authenticated recovery backup verified in memory. No modem accessed; no plaintext file written.';return}
if(-not $OutputZip){throw 'Use -VerifyOnly, or specify a new private -OutputZip path.'}
$stream=[IO.File]::Open($OutputZip,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try {$stream.Write($plain,0,$plain.Length)} finally {$stream.Dispose();[Array]::Clear($plain,0,$plain.Length)}
Write-Output 'Decrypted ZIP created. It contains private device data. This tool performs no flashing.'
