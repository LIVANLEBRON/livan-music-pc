import subprocess, json, os, socket, tempfile, shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, urlencode

import sys

from library_config import (
    PLAYLISTS_FILE,
    add_library_dir,
    describe_library_dirs,
    get_download_dir,
    public_settings,
    remove_library_dir,
    resolve_library_file,
    set_download_dir,
)

PORT = int(os.environ.get("PORT", 8642))

# Carpeta temporal para la app de Android (para borrar tras enviar)
ANDROID_TEMP_DIR = os.path.join(tempfile.gettempdir(), "YTDownloads")
os.makedirs(ANDROID_TEMP_DIR, exist_ok=True)

# Soporte para PyInstaller
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    exe_dir = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    exe_dir = application_path

def find_tool(name):
    """Encuentra el binario empaquetado en Windows o el instalado en Linux."""
    candidates = [
        os.path.join(exe_dir, f"{name}.exe"),
        os.path.join(application_path, f"{name}.exe"),
        shutil.which(name),
        shutil.which(f"{name}.exe"),
    ]
    return next((path for path in candidates if path and os.path.isfile(path)), name)


YTDLP_PATH = find_tool("yt-dlp")
FFMPEG_PATH = find_tool("ffmpeg")


def youtube_runtime_args():
    """Activa el solucionador JS que YouTube exige en versiones actuales."""
    args = ["--remote-components", "ejs:github"]
    for runtime in ("deno", "node"):
        executable = f"{runtime}.exe" if os.name == "nt" else runtime
        candidates = (
            os.path.join(exe_dir, executable),
            os.path.join(application_path, executable),
            shutil.which(runtime),
        )
        runtime_path = next((path for path in candidates if path and os.path.isfile(path)), None)
        if runtime_path:
            args.extend(["--js-runtimes", f"{runtime}:{runtime_path}"])
            break
    return args


YOUTUBE_RUNTIME_ARGS = youtube_runtime_args()

# CREATE_NO_WINDOW solo existe en Windows.
SUBPROCESS_OPTIONS = {}
if os.name == "nt":
    SUBPROCESS_OPTIONS["creationflags"] = subprocess.CREATE_NO_WINDOW


# Asegurarse de que exista la carpeta public
PUBLIC_DIR = os.path.join(application_path, "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except:
        return "127.0.0.1"
    finally:
        s.close()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        
        # API: Verificar estado
        if parsed.path == "/api/status":
            self._json(200, {
                "status": "ok",
                "music_dir": str(get_download_dir()),
                "yt_dlp": YTDLP_PATH,
                "ffmpeg": FFMPEG_PATH,
            })

        # API: Configuración de descargas y carpetas de biblioteca
        elif parsed.path == "/api/settings":
            self._json(200, public_settings())
            
        # API: Búsqueda en YouTube
        elif parsed.path == "/search":
            q = parse_qs(parsed.query).get("q", [""])[0]
            if not q:
                return self._json(400, {"error": "Falta q"})
            try:
                cmd = [YTDLP_PATH, f"ytsearch15:{q}", "--flat-playlist", "-j", "--no-download", "--no-warnings"]
                res = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30,
                    **SUBPROCESS_OPTIONS
                )
                if res.returncode != 0:
                    raise RuntimeError(res.stderr.strip() or "yt-dlp no pudo completar la búsqueda")
                results = []
                for line in res.stdout.strip().split("\n"):
                    if not line: continue
                    data = json.loads(line)
                    results.append({
                        "title": data.get("title", "Sin titulo"),
                        "artist": data.get("channel", "YouTube"),
                        "videoId": data.get("id", ""),
                        "duration": data.get("duration", 0),
                        "thumbnail": f"https://i.ytimg.com/vi/{data.get('id','')}/mqdefault.jpg"
                    })
                self._json(200, {"results": results})
            except Exception as e:
                self._json(500, {"error": str(e)})

        # API: Descarga Android (Descarga a Temp, Envía al móvil y Elimina)
        elif parsed.path == "/download":
            vid = parse_qs(parsed.query).get("id", [""])[0]
            if not vid: return self._json(400, {"error": "Falta id"})
            self._handle_download(vid, ANDROID_TEMP_DIR, delete_after=True)

        # API: Descarga PC (Descarga permanente a Music con Progreso en Tiempo Real)
        elif parsed.path == "/pc/download":
            vid = parse_qs(parsed.query).get("id", [""])[0]
            if not vid: return self._json(400, {"error": "Falta id"})
            
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            # Es un flujo finito: al terminar la descarga cerramos la conexión.
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            try:
                url = f"https://www.youtube.com/watch?v={vid}"
                download_dir = get_download_dir()
                print(f"Descargando (SSE) en PC: {url}")
                print(f"Destino de descarga: {download_dir}")
                output = os.path.join(download_dir, "%(title)s - %(channel)s.%(ext)s")

                self._send_event({
                    "status": "preparing",
                    "text": f"Preparando descarga en {download_dir}",
                    "download_dir": str(download_dir),
                })
                
                cmd = [
                    YTDLP_PATH, "-f", "bestaudio[ext=m4a]/bestaudio/best",
                    *YOUTUBE_RUNTIME_ARGS,
                    "--extractor-args", "youtube:player_client=web_embedded",
                    "--force-ipv4",
                    "--extract-audio", "--audio-format", "m4a",
                    "--ffmpeg-location", FFMPEG_PATH,
                    "--write-thumbnail", "-o", output, 
                    "--print", "after_move:__LIVAN_FILE__:%(filepath)s",
                    "--newline", "--no-playlist", "--no-warnings", url
                ]
                
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, encoding="utf-8", errors="replace",
                    **SUBPROCESS_OPTIONS
                )
                
                last_msg = "Fallo desconocido"
                error_msg = ""
                final_path = ""
                for line in process.stdout:
                    if not line.strip(): continue
                    
                    last_msg = line.strip()
                    if last_msg.startswith("__LIVAN_FILE__:"):
                        final_path = last_msg.split(":", 1)[1]
                    if "ERROR:" in last_msg:
                        error_msg = last_msg
                    data_to_send = {"status": "processing", "text": last_msg}
                    
                    if "[download]" in line and "%" in line:
                        data_to_send["status"] = "downloading"
                        
                    self._send_event(data_to_send)
                
                process.wait()
                if process.returncode == 0:
                    destination = final_path or str(download_dir)
                    self._send_event({
                        "status": "done",
                        "text": f"Guardada en: {destination}",
                        "file": final_path,
                        "download_dir": str(download_dir),
                    })
                else:
                    detail = error_msg or last_msg
                    self._send_event({"status": "error", "text": detail[:300]})
                self.close_connection = True
                
            except Exception as e:
                self._send_event({"status": "error", "text": str(e)[:300]})
                self.close_connection = True

        # API: Obtener biblioteca de música local (para el reproductor web)
        elif parsed.path == "/library":
            songs = []
            seen_files = set()
            for source in describe_library_dirs():
                source_dir = source["path"]
                for root, dirs, files in os.walk(source_dir):
                    dirs[:] = [directory for directory in dirs if not directory.startswith(".")]
                    for filename in files:
                        if not filename.lower().endswith((".m4a", ".mp3", ".mp4", ".wav", ".flac", ".ogg")):
                            continue

                        filepath = os.path.join(root, filename)
                        file_key = os.path.normcase(os.path.realpath(filepath))
                        if file_key in seen_files:
                            continue
                        seen_files.add(file_key)
                        relative_name = os.path.relpath(filepath, source_dir)
                        base_name = filename.rsplit(".", 1)[0]
                        name_parts = base_name.split(" - ", 1)
                        title = name_parts[0]
                        artist = name_parts[1] if len(name_parts) > 1 else "Unknown"
                        query = urlencode({"source": source["id"], "file": relative_name})

                        thumbnail_url = ""
                        for ext in [".jpg", ".jpeg", ".webp", ".png"]:
                            thumbnail_path = os.path.join(root, base_name + ext)
                            if os.path.isfile(thumbnail_path):
                                thumbnail_relative = os.path.relpath(thumbnail_path, source_dir)
                                thumbnail_query = urlencode({"source": source["id"], "file": thumbnail_relative})
                                thumbnail_url = f"/stream?{thumbnail_query}"
                                break

                        songs.append({
                            "filename": relative_name,
                            "source_id": source["id"],
                            "source_name": source["name"],
                            "title": title,
                            "artist": artist,
                            "stream_url": f"/stream?{query}",
                            "thumbnail_url": thumbnail_url,
                        })
            songs.sort(key=lambda song: (song["title"].casefold(), song["artist"].casefold()))
            self._json(200, {"songs": songs})

        # API: Stream audio local
        elif parsed.path.startswith("/stream"):
            filename = parse_qs(parsed.query).get("file", [""])[0]
            source = parse_qs(parsed.query).get("source", [""])[0]
            filepath = resolve_library_file(source, filename)
            if not filepath:
                self._json(404, {"error": "Archivo no encontrado"})
                return
            
            try:
                filesize = os.path.getsize(filepath)
                self.send_response(200)
                # Configurar headers para permitir streaming o imagenes
                if filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
                    content_type = "image/jpeg"
                elif filename.lower().endswith(".webp"):
                    content_type = "image/webp"
                elif filename.lower().endswith(".png"):
                    content_type = "image/png"
                elif filename.lower().endswith((".m4a", ".mp4")):
                    content_type = "audio/mp4"
                elif filename.lower().endswith(".wav"):
                    content_type = "audio/wav"
                elif filename.lower().endswith(".flac"):
                    content_type = "audio/flac"
                elif filename.lower().endswith(".ogg"):
                    content_type = "audio/ogg"
                else:
                    content_type = "audio/mpeg"
                    
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(filesize))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                
                with open(filepath, "rb") as f:
                    while chunk := f.read(8192 * 4):
                        self.wfile.write(chunk)
            except Exception as e:
                print(f"Error streaming {filename}: {e}")

        # API: Obtener Playlists
        elif parsed.path == "/api/playlists":
            if PLAYLISTS_FILE.exists():
                with PLAYLISTS_FILE.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"Favoritos": [], "Mis Playlists": {}}
            self._json(200, data)

        # Favicon (icon.ico en la raíz del proyecto)
        elif parsed.path == "/favicon.ico":
            icon_file = os.path.join(exe_dir, "icon.ico")
            if os.path.exists(icon_file):
                with open(icon_file, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/x-icon")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404)

        # Si no es API, servir archivos estáticos (HTML/CSS/JS)
        else:
            if self.path == "/": self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        
        # API: Guardar Playlists
        if parsed.path == "/api/playlists":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode('utf-8'))
            
            PLAYLISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with PLAYLISTS_FILE.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
            self._json(200, {"status": "ok"})
            
        # API: Eliminar canción
        elif parsed.path == "/api/delete_song":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode('utf-8'))
            
            filename = data.get("filename", "")
            source = data.get("source_id", "")
            if filename:
                filepath = resolve_library_file(source, filename)
                if filepath:
                    try:
                        os.remove(filepath)
                        # También eliminar la portada si existe
                        base_name = str(filepath.with_suffix(""))
                        for ext in [".jpg", ".jpeg", ".webp", ".png"]:
                            thumb_path = base_name + ext
                            if os.path.exists(thumb_path):
                                os.remove(thumb_path)
                        self._json(200, {"status": "ok"})
                        return
                    except Exception as e:
                        self._json(500, {"error": str(e)})
                        return
            self._json(400, {"error": "Archivo no encontrado"})

        elif parsed.path == "/api/settings":
            length = int(self.headers.get('Content-Length', 0))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                action = data.get("action", "")
                path = data.get("path", "")
                if action == "set_download":
                    settings = set_download_dir(path)
                elif action == "add_library":
                    settings = add_library_dir(path)
                elif action == "remove_library":
                    settings = remove_library_dir(path)
                else:
                    return self._json(400, {"error": "Acción de configuración no válida"})
                self._json(200, settings)
            except (ValueError, OSError, PermissionError) as error:
                self._json(400, {"error": str(error)})
            
        else:
            self.send_error(404)

    def _handle_download(self, vid, out_dir, delete_after):
        try:
            url = f"https://www.youtube.com/watch?v={vid}"
            print(f"Descargando: {url}")
            output = os.path.join(out_dir, "%(id)s.%(ext)s")
            
            cmd = [
                YTDLP_PATH, "-f", "bestaudio[ext=m4a]/bestaudio/best",
                *YOUTUBE_RUNTIME_ARGS,
                "--extractor-args", "youtube:player_client=web_embedded",
                "--force-ipv4",
                "-o", output, "--no-playlist", "--no-mtime", "--no-warnings",
                "--print", "after_move:filepath", url,
            ]
            res = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
                **SUBPROCESS_OPTIONS
            )
            filepath = res.stdout.strip().split("\n")[-1].strip()
            
            if os.path.exists(filepath):
                filesize = os.path.getsize(filepath)
                self.send_response(200)
                self.send_header("Content-Type", "audio/mp4")
                self.send_header("Content-Length", str(filesize))
                self.end_headers()
                
                try:
                    with open(filepath, "rb") as f:
                        while chunk := f.read(8192 * 4):
                            self.wfile.write(chunk)
                except Exception as e:
                    print(f"Error enviando: {e}")
                finally:
                    if delete_after:
                        try:
                            os.remove(filepath)
                        except Exception as e:
                            print(f"No se pudo eliminar {filepath}: {e}")
            else:
                self._json(500, {"error": "Fallo descarga", "stderr": res.stderr})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(data).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_event(self, data):
        try:
            self.wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

def run_server():
    ip = get_local_ip()
    print("="*50)
    print("Servidor y Reproductor Web Livan")
    print("="*50)
    print(f"API para celular: http://{ip}:{PORT}")
    print(f"Reproductor Local: http://localhost:{PORT}")
    print(f"Descargas: {get_download_dir()}")
    print(f"Carpetas de biblioteca: {len(describe_library_dirs())}")
    print(f"Motor JavaScript: {YOUTUBE_RUNTIME_ARGS[-1] if '--js-runtimes' in YOUTUBE_RUNTIME_ARGS else 'no disponible'}")
    print("="*50)
    
    # El servidor concurrente permite navegar por la biblioteca mientras una
    # canción se descarga o se reproduce.
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()

if __name__ == "__main__":
    run_server()
