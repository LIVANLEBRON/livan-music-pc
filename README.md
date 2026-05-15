# 🎵 Livan Music — Reproductor de Música para PC

Reproductor de música de escritorio para Windows construido con Python + pywebview.  
Descarga canciones de YouTube directamente a tu PC y las reproduce sin necesidad de conexión.

---

## ✨ Características

- 🔍 **Búsqueda en YouTube** — Busca y descarga canciones en formato M4A
- 🎵 **Reproductor local** — Biblioteca con carátulas, control de velocidad, shuffle y repeat
- ❤️ **Favoritos y Playlists** — Organiza tu música como quieras
- 📜 **Historial de descargas** — Seguimiento en tiempo real del progreso
- 🖥️ **App nativa de Windows** — Se instala como cualquier programa

---

## 📦 Estructura del Proyecto

```
Livan_Music_PC/
├── app_pc.py          # Punto de entrada de la app (pywebview)
├── yt_server.py       # Servidor HTTP interno (API + archivos estáticos)
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
- Instalar dependencias:
```bash
pip install pywebview
```

---

## 🚀 Ejecutar en modo desarrollo

```bash
python app_pc.py
```

---

## 📦 Compilar el instalador

### Paso 1 — Descargar binarios necesarios
Antes de compilar, descarga estos archivos y colócalos en la raíz del proyecto:

| Archivo | Enlace |
|---|---|
| `ffmpeg.exe` | https://github.com/BtbN/FFmpeg-Builds/releases |
| `yt-dlp.exe` | https://github.com/yt-dlp/yt-dlp/releases/latest |

### Paso 2 — Instalar Inno Setup
```
winget install JRSoftware.InnoSetup
```

### Paso 3 — Compilar
```bash
compilar.bat
```

### Paso 4 — Generar instalador
```
"C:\Users\...\Inno Setup 6\ISCC.exe" installer.iss
```

El instalador final estará en `installer_output\LivanMusicSetup.exe`

---

## 📁 ¿Dónde se guarda la música?

La música descargada se guarda en:
```
C:\Users\{TuUsuario}\Music\LivanMusic\
```

---

## 👨‍💻 Autor

**Livan Andres** — Proyecto personal de reproductor de música.
