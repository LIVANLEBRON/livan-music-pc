# 🎵 Livan Music — Reproductor de Música para PC

Reproductor de música de escritorio para Windows y Linux construido con Python y una interfaz web.
Descarga canciones de YouTube directamente a tu PC y las reproduce sin necesidad de conexión.

---

## ✨ Características

- 🔍 **Búsqueda en YouTube** — Busca y descarga canciones en formato M4A
- 🎵 **Reproductor local** — Biblioteca con carátulas, control de velocidad, shuffle y repeat
- 📁 **Varias carpetas** — Añade colecciones existentes sin mover los archivos
- ⬇️ **Destino configurable** — Elige dónde se guardan las nuevas descargas
- ❤️ **Favoritos y Playlists** — Organiza tu música como quieras
- 📜 **Historial de descargas** — Seguimiento en tiempo real del progreso
- 🖥️ **App nativa de Windows** — Se instala como cualquier programa
- 🐧 **Compatible con Linux** — Usa el navegador si pywebview no está instalado
- 🌐 **Acceso remoto opcional** — Inicia y detiene Cloudflare Tunnel junto con la app
- 🔒 **Modo web protegido** — Las rutas y el borrado de archivos solo existen en la app nativa

---

## 📦 Estructura del Proyecto

```
Livan_Music_PC/
├── app_pc.py          # Punto de entrada de la app (pywebview)
├── yt_server.py       # Servidor HTTP interno (API + archivos estáticos)
├── library_config.py  # Configuración persistente de carpetas
├── compilar.bat       # Script de compilación (PyInstaller)
├── installer.iss      # Script del instalador (Inno Setup)
├── icon.ico           # Ícono de la aplicación
└── public/
    ├── index.html     # Interfaz de usuario
    ├── style.css      # Estilos
    └── script.js      # Lógica del frontend
```

---

## 🛠️ Requisitos para Desarrollar

- Python 3.10+
- Node.js 22+ o Deno 2.3+ (necesario para resolver los desafíos actuales de YouTube)
- Instalar dependencias:
```bash
pip install pywebview
```

---

## 🚀 Ejecutar en modo desarrollo

```bash
python app_pc.py
```

### Linux

El sistema usa automáticamente `yt-dlp` y `ffmpeg` instalados. En este equipo,
el proyecto está en la unidad Datos:

```text
/run/media/livana/Datos/livan-music-pc
```

Para abrirla:

```bash
./iniciar-linux.sh
```

Para generar un ejecutable Linux con ventana nativa:

```bash
./compilar-linux.sh
```

El archivo final se copia automáticamente a la carpeta Descargas del usuario
con el nombre `Livan-Music`.

## 🌐 Acceso remoto con Cloudflare Tunnel

Livan Music puede iniciar automáticamente un túnel administrado remotamente.
El servidor y el túnel se abren al ejecutar la aplicación y el conector se
cierra al cerrar la ventana. El token nunca se guarda en Git ni dentro del EXE.

La primera vez, crea en Cloudflare una ruta publicada cuyo servicio sea
`http://localhost:8642`. Después guarda el token privado una sola vez:

```bash
./configurar-tunel-linux.sh
```

En Windows, ejecuta `configurar-tunel-windows.ps1` con PowerShell. A partir de
ese momento basta con abrir `Livan Music.exe` con doble clic. La compilación de
Windows incluye `cloudflared.exe` automáticamente.

---

## 📦 Compilar el instalador

### Paso 1 — Instalar Inno Setup
```
winget install JRSoftware.InnoSetup
```

### Paso 2 — Compilar
```bash
compilar.bat
```

El script prepara automáticamente `yt-dlp.exe`, `ffmpeg.exe` y `deno.exe`, y
los incluye dentro de la aplicación para que las descargas no dependan de una
instalación externa.

### Paso 3 — Generar instalador
```
"C:\Users\...\Inno Setup 6\ISCC.exe" installer.iss
```

El instalador final estará en `installer_output\LivanMusicSetup.exe`

---

## 📁 ¿Dónde se guarda la música?

De forma predeterminada, la música descargada se guarda en:
```
C:\Users\{TuUsuario}\Music\LivanMusic\
```

En Linux se usa la carpeta Música configurada por el sistema, por ejemplo
`~/Música/LivanMusic`. Desde **Ubicaciones** puedes cambiar el destino y añadir
otras carpetas a la biblioteca sin copiar ni mover su contenido. La selección
queda guardada en la configuración del usuario.

Al terminar una descarga, el historial de la aplicación muestra la ruta
completa del archivo guardado.


---

## 👨‍💻 Autor

**Livan Andres** — Proyecto personal de reproductor de música.
