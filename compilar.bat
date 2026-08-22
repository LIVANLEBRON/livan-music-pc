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

if /I "%~1"=="--portable-tunnel" goto compile_portable
if not "%~1"=="" (
  echo Uso: compilar.bat [--portable-tunnel]
  exit /b 2
)

:compile_normal
py -m PyInstaller --noconsole --onefile --clean -y ^
  --add-data "%~dp0public;public" ^
  --add-binary "%~dp0ffmpeg.exe;." ^
  --add-binary "%~dp0yt-dlp.exe;." ^
  --add-binary "%~dp0deno.exe;." ^
  --add-binary "%~dp0cloudflared.exe;." ^
  --add-data "%~dp0icon.ico;." ^
  --icon="%~dp0icon.ico" ^
  --name "Livan Music" ^
  "%~dp0app_pc.py"
goto compile_done

:compile_portable
set "TUNNEL_CONFIG=%APPDATA%\LivanMusic"
set "TOKEN_FILE=%TUNNEL_CONFIG%\cloudflare-tunnel.token"
set "HOSTNAME_FILE=%TUNNEL_CONFIG%\cloudflare-hostname.txt"
set "PORTABLE_BUILD=%TEMP%\LivanMusic-build-%RANDOM%%RANDOM%"
if not exist "%TOKEN_FILE%" (
  echo ERROR: falta %TOKEN_FILE%
  echo Ejecuta primero configurar-tunel-windows.ps1
  exit /b 1
)
if not exist "%HOSTNAME_FILE%" (
  echo ERROR: falta %HOSTNAME_FILE%
  echo Ejecuta primero configurar-tunel-windows.ps1
  exit /b 1
)
echo AVISO: creando una version privada con la credencial del tunel incluida.
mkdir "%PORTABLE_BUILD%\work" "%PORTABLE_BUILD%\spec" "%PORTABLE_BUILD%\dist"
py -m PyInstaller --noconsole --onefile --clean -y ^
  --workpath "%PORTABLE_BUILD%\work" ^
  --specpath "%PORTABLE_BUILD%\spec" ^
  --distpath "%PORTABLE_BUILD%\dist" ^
  --add-data "%~dp0public;public" ^
  --add-data "%TOKEN_FILE%;private_defaults" ^
  --add-data "%HOSTNAME_FILE%;private_defaults" ^
  --add-binary "%~dp0ffmpeg.exe;." ^
  --add-binary "%~dp0yt-dlp.exe;." ^
  --add-binary "%~dp0deno.exe;." ^
  --add-binary "%~dp0cloudflared.exe;." ^
  --add-data "%~dp0icon.ico;." ^
  --icon="%~dp0icon.ico" ^
  --name "Livan Music" ^
  "%~dp0app_pc.py"
if errorlevel 1 (
  rmdir /s /q "%PORTABLE_BUILD%"
  echo ERROR: PyInstaller no pudo crear el ejecutable.
  exit /b 1
)
copy /y "%PORTABLE_BUILD%\dist\Livan Music.exe" "%USERPROFILE%\Downloads\Livan Music.exe" >nul
if errorlevel 1 (
  rmdir /s /q "%PORTABLE_BUILD%"
  echo ERROR: no se pudo copiar el ejecutable a Descargas.
  exit /b 1
)
rmdir /s /q "%PORTABLE_BUILD%"

:compile_done

if errorlevel 1 (
  echo ERROR: PyInstaller no pudo crear el ejecutable.
  exit /b 1
)

echo.
echo =================================================
echo COMPILACION TERMINADA!
if /I "%~1"=="--portable-tunnel" (
  echo Tu archivo privado se encuentra en Descargas: "Livan Music.exe".
  echo VERSION PRIVADA: no compartas este ejecutable publicamente.
) else (
  echo Tu archivo .exe se encuentra en la carpeta "dist".
  echo Copia "dist\Livan Music.exe" donde quieras y ejecutalo.
)
echo =================================================
pause
endlocal
