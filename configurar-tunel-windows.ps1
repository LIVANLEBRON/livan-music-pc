$ErrorActionPreference = "Stop"

$configDir = Join-Path $env:APPDATA "LivanMusic"
$tokenFile = Join-Path $configDir "cloudflare-tunnel.token"
$hostnameFile = Join-Path $configDir "cloudflare-hostname.txt"

Write-Host "Configuracion privada de Cloudflare Tunnel para Livan Music"
$secureToken = Read-Host "Pega el token del tunel (no se mostrara)" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}

if ([string]::IsNullOrWhiteSpace($token) -or $token.Length -lt 40) {
    throw "El token parece incompleto."
}

$hostname = Read-Host "Direccion fija, por ejemplo musica.midominio.com"
$hostname = $hostname.Trim().Replace("https://", "").TrimEnd("/")

New-Item -ItemType Directory -Force -Path $configDir | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($tokenFile, $token.Trim(), $utf8NoBom)
[IO.File]::WriteAllText($hostnameFile, $hostname, $utf8NoBom)

Write-Host "Listo. Al abrir Livan Music tambien se iniciara el tunel."
