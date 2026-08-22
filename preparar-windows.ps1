$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$depsDir = Join-Path $projectDir ".windows-deps"
New-Item -ItemType Directory -Force -Path $depsDir | Out-Null

function Get-Dependency {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (Test-Path $Destination) {
        Write-Host "[OK] $Name ya existe: $Destination"
        return
    }

    Write-Host "[DESCARGANDO] $Name"
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

$ytDlpPath = Join-Path $projectDir "yt-dlp.exe"
Get-Dependency `
    -Name "yt-dlp" `
    -Url "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" `
    -Destination $ytDlpPath

$denoPath = Join-Path $projectDir "deno.exe"
if (-not (Test-Path $denoPath)) {
    $denoZip = Join-Path $depsDir "deno.zip"
    Get-Dependency `
        -Name "Deno" `
        -Url "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip" `
        -Destination $denoZip
    Expand-Archive -Path $denoZip -DestinationPath $depsDir -Force
    Copy-Item (Join-Path $depsDir "deno.exe") $denoPath -Force
}

$ffmpegPath = Join-Path $projectDir "ffmpeg.exe"
if (-not (Test-Path $ffmpegPath)) {
    $ffmpegZip = Join-Path $depsDir "ffmpeg.zip"
    Get-Dependency `
        -Name "FFmpeg" `
        -Url "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip" `
        -Destination $ffmpegZip
    $ffmpegExtract = Join-Path $depsDir "ffmpeg"
    Expand-Archive -Path $ffmpegZip -DestinationPath $ffmpegExtract -Force
    $ffmpegBinary = Get-ChildItem -Path $ffmpegExtract -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
    if (-not $ffmpegBinary) {
        throw "El paquete de FFmpeg no contenia ffmpeg.exe"
    }
    Copy-Item $ffmpegBinary.FullName $ffmpegPath -Force
}

foreach ($dependency in @($ytDlpPath, $denoPath, $ffmpegPath)) {
    if (-not (Test-Path $dependency)) {
        throw "Dependencia ausente: $dependency"
    }
}

Write-Host ""
Write-Host "Dependencias de Windows preparadas correctamente:"
& $ytDlpPath --version
& $denoPath --version | Select-Object -First 1
& $ffmpegPath -version | Select-Object -First 1
