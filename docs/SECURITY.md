# Seguridad y datos privados

Livan Music comparte una biblioteca alojada en el equipo que ejecuta el
servidor. Este documento deja claro qué se publica, qué permanece privado y
cómo se protegen las credenciales.

## Credencial de Cloudflare Tunnel

El token del túnel **no pertenece al repositorio**. Los scripts de configuración
lo guardan fuera del proyecto:

| Sistema | Archivo privado |
| --- | --- |
| Linux | `~/.config/livan-music/cloudflare-tunnel.token` |
| Windows | `%APPDATA%\LivanMusic\cloudflare-tunnel.token` |

En Linux se crea con permisos `0600`. El token se pasa a cloudflared mediante un
archivo y su valor no se imprime en la terminal ni en los logs de Livan Music.

El nombre de host se guarda junto a la configuración local para mostrar la URL
de acceso, pero tampoco es necesario versionarlo.

## Compilaciones normales y portátiles

Una compilación normal contiene cloudflared, pero **no contiene el token**. Cada
equipo debe configurarse de forma local.

La opción `--portable-tunnel` incorpora voluntariamente la credencial en el
ejecutable para mover el servidor entre computadoras propias. Ese binario debe
tratarse como una contraseña:

- no subirlo a GitHub;
- no adjuntarlo a Releases;
- no enviarlo a amigos;
- no alojarlo como descarga pública;
- no ejecutar dos copias con bibliotecas diferentes bajo el mismo túnel.

Si un ejecutable portátil sale del entorno privado, se debe revocar o rotar la
credencial desde Cloudflare antes de volver a usar el túnel.

## Separación entre escritorio y web

La aplicación diferencia una sesión local de escritorio de un visitante web.

| Capacidad | Escritorio | Navegador remoto |
| --- | ---: | ---: |
| Ver la biblioteca | Sí | Sí |
| Reproducir música | Sí | Sí |
| Buscar y descargar al servidor | Sí | Sí |
| Gestionar playlists | Sí | Sí |
| Ver rutas completas del equipo | Sí | No |
| Cambiar carpetas | Sí | No |
| Eliminar archivos locales | Sí | No |

Las operaciones privadas requieren una cookie de sesión creada desde localhost.
El token de arranque es efímero, se compara de forma segura, se oculta en los
logs y se canjea por una cookie `HttpOnly`.

El acceso web no concede acceso general al sistema de archivos. `/stream`
solamente puede resolver rutas relativas dentro de las carpetas registradas y
rechaza cualquier intento de escapar de ellas.

## Alcance del enlace público

Actualmente, cualquier persona que conozca el enlace del túnel puede usar las
funciones públicas indicadas en la tabla anterior. El enlace debe compartirse
únicamente con personas de confianza. Cloudflare Tunnel evita abrir puertos en
el router, pero no sustituye un sistema de autenticación de usuarios.

Para una publicación abierta sería necesario añadir autenticación antes de
considerar el servidor apto para Internet público.

## Archivos excluidos de Git

`.gitignore` bloquea, entre otros:

- tokens y credenciales;
- configuraciones privadas incorporables;
- archivos `.env`;
- ejecutables y dependencias descargadas;
- salidas de PyInstaller e Inno Setup;
- logs y cachés locales.

Antes de publicar cambios se recomienda ejecutar:

```bash
git status --short
git diff --check
git grep -n "cloudflare-tunnel.token"
```

El último comando debe mostrar solamente referencias al nombre del archivo, no
el contenido de ninguna credencial.
