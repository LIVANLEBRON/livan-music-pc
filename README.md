# Livan Music

Aplicación personal de escritorio y servidor de música creada por **Livan Andrés**.
Permite administrar una biblioteca alojada en el propio equipo, reproducirla desde
la aplicación o desde otros dispositivos y descargar nuevas canciones en una
carpeta configurable.

El desarrollo principal se ejecuta y se prueba actualmente en una **PC con
Linux (Nobara)**. El proyecto también incluye el proceso de compilación para
Windows.

> Livan Music está pensado para bibliotecas personales. Cada usuario es
> responsable de utilizar únicamente contenido que tenga derecho a descargar.

## Qué ofrece

- Biblioteca local con carátulas, favoritos y playlists.
- Reproductor con búsqueda, progreso, salto temporal, volumen, repetición,
  reproducción aleatoria y velocidad configurable.
- Interfaz adaptable para escritorio, navegador y teléfono.
- Búsqueda y descarga con progreso en tiempo real.
- Cambio automático a **Biblioteca** al terminar una descarga, con acceso a
  **Reproducir ahora**.
- Carpeta de descargas configurable y soporte para varias carpetas de música.
- Acceso desde la red local mediante el puerto `8642`.
- Acceso remoto opcional mediante Cloudflare Tunnel.
- Protección de las operaciones sensibles: las rutas del sistema y el borrado
  de archivos solamente están disponibles en la ventana de escritorio.
- Bloqueo reversible de la suspensión automática mientras el servidor está
  activo.

## Tecnologías

| Capa | Tecnología | Responsabilidad |
| --- | --- | --- |
| Interfaz | HTML, CSS y JavaScript puro | Navegación, biblioteca y reproductor adaptable |
| Servidor | Python y `ThreadingHTTPServer` | API local, archivos estáticos y streaming |
| Escritorio | pywebview | Ventana nativa alrededor de la interfaz web |
| Descargas | yt-dlp | Búsqueda y obtención del audio |
| Audio | FFmpeg | Extracción y normalización a M4A |
| Compatibilidad con YouTube | Node.js o Deno | Motor JavaScript auxiliar para yt-dlp |
| Acceso remoto | cloudflared | Túnel opcional hacia el servidor local |
| Distribución | PyInstaller | Ejecutables independientes para Linux y Windows |

No se utiliza React, Electron, Flask ni una base de datos externa. La música y
la configuración permanecen en el equipo que ejecuta Livan Music.

## Cómo funciona

Al abrir la aplicación, `app_pc.py` inicia el servidor Python en segundo plano,
espera a que responda y abre la interfaz en una ventana pywebview. Si el túnel
está configurado, también inicia `cloudflared`. Al cerrar la ventana se detienen
el túnel y el bloqueo de suspensión.

```text
Livan Music
├── ventana de escritorio (pywebview)
├── interfaz HTML/CSS/JavaScript
├── servidor Python en el puerto 8642
│   ├── catálogo de carpetas locales
│   ├── streaming con soporte HTTP Range
│   ├── búsqueda y descarga mediante yt-dlp
│   └── progreso de descarga mediante Server-Sent Events
├── FFmpeg + motor JavaScript de YouTube
└── Cloudflare Tunnel opcional
```

La explicación detallada de componentes, rutas y flujos está en
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Estructura del repositorio

```text
livan-music-pc/
├── app_pc.py                    # Entrada de la aplicación de escritorio
├── yt_server.py                 # Servidor HTTP, API, descargas y streaming
├── library_config.py            # Carpetas y configuración persistente
├── tunnel_manager.py            # Ciclo de vida de Cloudflare Tunnel
├── sleep_inhibitor.py           # Bloqueo de suspensión por plataforma
├── public/
│   ├── index.html               # Estructura de la interfaz
│   ├── style.css                # Diseño responsivo
│   ├── script.js                # Reproductor y comunicación con la API
│   └── fonts/                   # Tipografías servidas localmente
├── iniciar-linux.sh             # Ejecución en desarrollo sobre Linux
├── compilar-linux.sh            # Ejecutable Linux con PyInstaller
├── preparar-windows.ps1         # Descarga dependencias de Windows
├── compilar.bat                 # Ejecutable Windows con PyInstaller
├── installer.iss                # Instalador de Windows con Inno Setup
├── requirements.txt             # Dependencias Python de desarrollo
└── docs/
    ├── ARCHITECTURE.md           # Diseño técnico completo
    └── SECURITY.md               # Modelo de acceso y gestión de secretos
```

## Desarrollo en Linux

### Requisitos

- Python 3.10 o superior.
- Dependencias Python de `requirements.txt`.
- yt-dlp y FFmpeg disponibles en el sistema.
- Node.js 22+ o Deno 2.3+.
- WebKitGTK/GTK para mostrar la ventana de pywebview.
- cloudflared solamente si se utilizará el túnel remoto.

Los nombres de los paquetes de GTK y WebKitGTK cambian según la distribución.

### Preparación y ejecución

```bash
python3 -m pip install -r requirements.txt
chmod +x iniciar-linux.sh compilar-linux.sh
./iniciar-linux.sh
```

La interfaz local queda disponible en `http://127.0.0.1:8642`. Otros equipos
de la misma red pueden utilizar la dirección IP local del servidor y ese mismo
puerto.

### Crear el ejecutable Linux

```bash
./compilar-linux.sh
```

El resultado se copia como `Livan-Music` en la carpeta de descargas del usuario.

## Desarrollo y compilación en Windows

Desde PowerShell o Símbolo del sistema:

```bat
preparar-windows.ps1
compilar.bat
```

`preparar-windows.ps1` obtiene yt-dlp, FFmpeg, Deno y cloudflared. PyInstaller
genera `dist\Livan Music.exe`. Para crear el instalador se puede compilar
`installer.iss` con Inno Setup.

## Carpetas y datos

Por defecto, las descargas se guardan en una subcarpeta `LivanMusic` dentro de
la carpeta Música del usuario. Desde **Ubicaciones** se puede cambiar ese destino
y registrar carpetas adicionales sin copiar ni mover sus canciones.

La configuración se almacena fuera del repositorio:

| Sistema | Directorio |
| --- | --- |
| Linux | `$XDG_CONFIG_HOME/livan-music` o `~/.config/livan-music` |
| Windows | `%APPDATA%\LivanMusic` |

## Cloudflare Tunnel y credenciales

La configuración normal nunca guarda el token en el repositorio ni lo añade a
una compilación pública. Para guardar la credencial de forma local:

```bash
# Linux
./configurar-tunel-linux.sh
```

```powershell
# Windows
.\configurar-tunel-windows.ps1
```

Existe una compilación portátil privada para mover el servidor entre equipos
propios:

```bash
./compilar-linux.sh --portable-tunnel
```

```bat
compilar.bat --portable-tunnel
```

Esa variante **sí contiene la credencial dentro del ejecutable**. No debe
subirse a GitHub, adjuntarse a una versión pública ni enviarse a terceros. El
modelo de seguridad completo está explicado en
[`docs/SECURITY.md`](docs/SECURITY.md).

## Autor

**Livan Andrés**

Diseño, desarrollo y mantenimiento de Livan Music.
