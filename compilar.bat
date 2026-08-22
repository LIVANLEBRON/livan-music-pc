@echo off
setlocal
echo =================================================
echo Compilando Livan Music para Windows...
echo Preparando una aplicacion autocontenida.
echo =================================================

where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo ERROR: PowerShell no esta disponible.
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0preparar-windows.ps1"
if errorlevel 1 (
  echo ERROR: No se pudieron preparar yt-dlp, FFmpeg y Deno.
  exit /b 1
)

py -m pip install --upgrade pyinstaller pywebview
if errorlevel 1 exit /b 1

py -m PyInstaller --noconsole --onefile --clean -y ^
  --add-data "public;public" ^
  --add-binary "ffmpeg.exe;." ^
  --add-binary "yt-dlp.exe;." ^
  --add-binary "deno.exe;." ^
  --add-binary "cloudflared.exe;." ^
  --add-data "icon.ico;." ^
  --icon=icon.ico ^
  --name "Livan Music" ^
  app_pc.py

if errorlevel 1 (
  echo ERROR: PyInstaller no pudo crear el ejecutable.
  exit /b 1
)

echo.
echo =================================================
echo COMPILACION TERMINADA!
echo Tu archivo .exe se encuentra en la carpeta "dist".
echo Copia "dist\Livan Music.exe" donde quieras y ejecutalo.
echo =================================================
pause
endlocal
