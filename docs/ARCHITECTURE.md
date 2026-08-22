# Arquitectura técnica de Livan Music

Este documento describe cómo está construido Livan Music y cómo se comunican
sus componentes. El proyecto fue diseñado y desarrollado por **Livan Andrés**
como una aplicación personal de música que mantiene los archivos en el equipo
del usuario.

## 1. Modelo general

Livan Music es una aplicación híbrida local:

1. Python inicia un servidor HTTP en el puerto `8642`.
2. pywebview abre ese servidor dentro de una ventana de escritorio.
3. La misma interfaz puede abrirse desde un navegador de la red local.
4. Cloudflare Tunnel puede publicar el servidor de forma opcional.

La ventana de escritorio no contiene una segunda interfaz: carga exactamente el
mismo frontend que reciben los navegadores. Esto mantiene una sola experiencia
visual para Linux, Windows, PC y teléfono.

## 2. Componentes

### `app_pc.py`

Es el punto de entrada y coordina el ciclo de vida completo:

- activa el bloqueo temporal de suspensión;
- ejecuta el servidor en un hilo de fondo;
- espera la respuesta de `/api/status`;
- inicia Cloudflare Tunnel si existe una configuración local;
- crea la ventana pywebview;
- expone un selector nativo de carpetas al frontend;
- detiene el túnel y libera el bloqueo de suspensión al cerrar.

En Linux se desactiva el renderizador DMABUF de WebKit cuando es necesario para
evitar ventanas en blanco con determinadas combinaciones de Wayland/X11 y
controladores gráficos.

### `yt_server.py`

Implementa un servidor concurrente con `ThreadingHTTPServer`. Sirve el contenido
de `public/` y las rutas de la API:

| Ruta | Método | Función |
| --- | --- | --- |
| `/api/status` | GET | Estado básico del servidor |
| `/library` | GET | Catálogo de canciones disponibles |
| `/stream` | GET/HEAD | Audio y carátulas con soporte HTTP Range |
| `/search` | GET | Búsqueda mediante yt-dlp |
| `/pc/download` | GET/SSE | Descarga permanente y progreso en vivo |
| `/download` | GET | Entrega temporal de un audio al cliente |
| `/api/playlists` | GET/POST | Lectura y almacenamiento de playlists |
| `/api/settings` | GET/POST | Gestión privada de carpetas |
| `/api/delete_song` | POST | Borrado privado de una canción |

El uso de un servidor concurrente permite reproducir una canción, cargar
carátulas y mantener una descarga activa sin bloquear el resto de solicitudes.

### `library_config.py`

Centraliza la persistencia y la seguridad de las rutas:

- detecta la carpeta Música nativa de Linux o Windows;
- establece `Música/LivanMusic` como destino inicial;
- permite registrar carpetas adicionales;
- crea un identificador estable para cada origen;
- normaliza y valida rutas antes de utilizarlas;
- impide que una solicitud con `..` salga de las carpetas autorizadas.

Los ajustes y las playlists se guardan en el directorio de configuración del
usuario, nunca dentro del código fuente.

### `public/`

El frontend usa HTML semántico, CSS responsivo y JavaScript sin frameworks.
`script.js` mantiene el estado del reproductor, consulta la API y sincroniza la
interfaz de escritorio y móvil.

En pantallas pequeñas se transforma la navegación, aparece un minirreproductor
y el reproductor completo se presenta como una vista móvil. Las operaciones de
descarga conservan botones táctiles de al menos 44 píxeles.

### `tunnel_manager.py`

Busca `cloudflared` dentro del ejecutable o en el sistema. Si existe una
credencial local, inicia un único proceso hijo y conserva el mismo ciclo de vida
de Livan Music. El token se entrega mediante `--token-file`, no como argumento
visible con su contenido.

### `sleep_inhibitor.py`

Mantiene disponible el servidor mientras la aplicación está abierta:

- Linux: proceso separado con `systemd-inhibit`;
- Windows: `SetThreadExecutionState`;
- macOS: `caffeinate`, aunque macOS no es una plataforma de distribución actual.

El bloqueo se libera al cerrar la aplicación; no modifica permanentemente la
configuración energética del sistema.

## 3. Flujo de inicio

```text
usuario abre Livan Music
        │
        ├─ activa inhibidor de suspensión
        ├─ inicia ThreadingHTTPServer en 0.0.0.0:8642
        ├─ comprueba /api/status
        ├─ inicia cloudflared si está configurado
        └─ abre pywebview en http://127.0.0.1:8642
```

El servidor escucha en todas las interfaces de red para permitir el acceso
desde otros dispositivos, mientras que la sesión privilegiada de escritorio
solo puede iniciarse desde `localhost`.

## 4. Flujo de búsqueda y descarga

```text
Buscar en la interfaz
        │
        ├─ GET /search?q=...
        ├─ yt-dlp devuelve hasta 15 resultados sin descargarlos
        └─ JavaScript construye las tarjetas de resultado

Descargar una canción
        │
        ├─ EventSource abre /pc/download?id=...
        ├─ yt-dlp obtiene la mejor pista de audio
        ├─ Node.js o Deno resuelve el JavaScript requerido por YouTube
        ├─ FFmpeg produce el archivo M4A
        ├─ el servidor emite progreso mediante Server-Sent Events
        └─ el frontend abre Biblioteca, resalta la canción y ofrece reproducirla
```

El audio y la miniatura quedan en la carpeta de descargas configurada.

## 5. Catálogo y reproducción

`/library` recorre únicamente los directorios registrados y admite M4A, MP3,
MP4, WAV, FLAC y OGG. Cada canción se devuelve con un identificador de origen y
una ruta relativa.

`/stream` vuelve a resolver esa combinación dentro de la carpeta permitida. La
respuesta implementa solicitudes `Range`, por lo que el navegador puede saltar
a otro punto de una canción sin descargar nuevamente el archivo completo.

## 6. Sesión de escritorio

Al crear la ventana, Python genera un token efímero distinto en cada proceso.
pywebview lo presenta una sola vez a través de una URL local. El servidor lo
canjea por una cookie `HttpOnly` con `SameSite=Strict` y redirige a una URL
limpia.

Esa sesión habilita la selección de carpetas, el cambio del destino y el borrado
de archivos. Un navegador remoto recibe `403` al intentar usar esas rutas.

Este token efímero no es la credencial de Cloudflare y nunca se escribe en disco.

## 7. Persistencia

No existe una base de datos central. El estado se compone de:

- archivos de audio y carátulas en las carpetas elegidas;
- `settings.json` para las ubicaciones;
- `playlists.json` para favoritos y listas;
- configuración opcional de Cloudflare en archivos separados y privados.

Esto permite mover o respaldar la colección sin depender de un servicio externo.

## 8. Distribución

PyInstaller empaqueta Python, la interfaz y los recursos en un ejecutable.

- En Linux, `compilar-linux.sh` genera `Livan-Music`.
- En Windows, `compilar.bat` genera `Livan Music.exe`.
- `installer.iss` crea un instalador tradicional de Windows con Inno Setup.

La compilación normal no incorpora la credencial del túnel. La opción
`--portable-tunnel` es una variante privada deliberada y se construye en un
directorio temporal fuera del repositorio.
