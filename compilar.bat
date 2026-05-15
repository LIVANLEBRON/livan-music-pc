@echo off
echo =================================================
echo Compilando Livan Music para Windows...
echo Por favor, espera aproximadamente 1 a 2 minutos.
echo =================================================

pip install pyinstaller pywebview

pyinstaller --noconsole --onefile --clean -y ^
  --add-data "public;public" ^
  --add-data "ffmpeg.exe;." ^
  --add-data "yt-dlp.exe;." ^
  --add-data "icon.ico;." ^
  --add-data "yt_server.py;." ^
  --icon=icon.ico ^
  --name "Livan Music" ^
  app_pc.py

echo.
echo =================================================
echo COMPILACION TERMINADA!
echo Tu archivo .exe se encuentra en la carpeta "dist".
echo Copia "dist\Livan Music.exe" donde quieras y ejecutalo.
echo =================================================
pause
