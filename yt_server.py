import subprocess, json, os, socket, tempfile, shutil, secrets, re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
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
DESKTOP_SESSION_TOKEN = secrets.token_urlsafe(48)
DESKTOP_COOKIE_NAME = "livan_desktop_session"

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

    def log_message(self, format, *args):
        """Evita que el token efímero de escritorio aparezca en los logs."""
        message = format % args
        message = re.sub(r"desktop_token=[^&\s\"]+", "desktop_token=[OCULTO]", message)
        print(f"{self.address_string()} - - [{self.log_date_time_string()}] {message}")

    def _is_desktop_session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        value = cookie.get(DESKTOP_COOKIE_NAME)
        return bool(value and secrets.compare_digest(value.value, DESKTOP_SESSION_TOKEN))

    def _start_desktop_session(self, parsed):
        """Canjea un token de un solo proceso por una cookie HTTP-only local."""
        values = parse_qs(parsed.query).get("desktop_token", [])
        if parsed.path != "/" or not values:
            return False
        host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]").lower()
        local_host = host in {"127.0.0.1", "localhost", "::1"}
        if not local_host or not secrets.compare_digest(values[0], DESKTOP_SESSION_TOKEN):
            self._json(403, {"error": "Sesión de escritorio no válida"})
            return True

        self.send_response(302)
        self.send_header("Location", "/")
        self.send_header(
            "Set-Cookie",
            f"{DESKTOP_COOKIE_NAME}={DESKTOP_SESSION_TOKEN}; Path=/; HttpOnly; SameSite=Strict",
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        return True

    def _require_desktop_session(self):
        if self._is_desktop_session():
            return True
        self._json(403, {"error": "Disponible únicamente en la aplicación de escritorio"})
        return False

    def _read_json_body(self, max_bytes=2 * 1024 * 1024):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError as error:
            raise ValueError("Tamaño de solicitud no válido") from error
        if length <= 0 or length > max_bytes:
            raise ValueError("Solicitud vacía o demasiado grande")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)

        if self._start_desktop_session(parsed):
            return
        
        # API: Verificar estado
        if parsed.path == "/api/status":
            status = {
                "status": "ok",
                "desktop_session": self._is_desktop_session(),
            }
            if status["desktop_session"]:
                status.update({
                    "music_dir": str(get_download_dir()),
                    "yt_dlp": YTDLP_PATH,
                    "ffmpeg": FFMPEG_PATH,
                })
            self._json(200, status)

        # API: Configuración de descargas y carpetas de biblioteca
        elif parsed.path == "/api/settings":
            if not self._require_desktop_session():
                return
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
                desktop_session = self._is_desktop_session()
                url = f"https://www.youtube.com/watch?v={vid}"
                download_dir = get_download_dir()
                print(f"Descargando (SSE) en PC: {url}")
                print(f"Destino de descarga: {download_dir}")
                output = os.path.join(download_dir, "%(title)s - %(channel)s.%(ext)s")

                preparing_event = {
                    "status": "preparing",
                    "text": "Preparando descarga...",
                }
                if desktop_session:
                    preparing_event["text"] = f"Preparando descarga en {download_dir}"
                    preparing_event["download_dir"] = str(download_dir)
                self._send_event(preparing_event)
                
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
                    data_to_send = {"status": "processing", "text": "Procesando audio..."}
                    
                    if "[download]" in line and "%" in line:
                        data_to_send["status"] = "downloading"
                        progress = re.search(r"\[download\]\s+([\d.]+)%", last_msg)
                        data_to_send["text"] = (
                            f"[download] {progress.group(1)}%" if progress else "Descargando..."
                        )
                    elif desktop_session:
                        data_to_send["text"] = last_msg
                        
                    self._send_event(data_to_send)
                
                process.wait()
                if process.returncode == 0:
                    destination = final_path or str(download_dir)
                    completed_event = {
                        "status": "done",
                        "text": "Descarga completada",
                    }
                    if desktop_session:
                        completed_event.update({
                            "text": f"Guardada en: {destination}",
                            "file": final_path,
                            "download_dir": str(download_dir),
                        })
                    self._send_event(completed_event)
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
            self._stream_file(filepath, filename)

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
            icon_file = next((candidate for candidate in (
                os.path.join(exe_dir, "icon.ico"),
                os.path.join(application_path, "icon.ico"),
            ) if os.path.isfile(candidate)), None)
            if icon_file:
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

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/stream"):
            filename = parse_qs(parsed.query).get("file", [""])[0]
            source = parse_qs(parsed.query).get("source", [""])[0]
            filepath = resolve_library_file(source, filename)
            if not filepath:
                self.send_error(404, "Archivo no encontrado")
                return
            self._stream_file(filepath, filename, send_body=False)
            return
        super().do_HEAD()

    def do_POST(self):
        parsed = urlparse(self.path)
        
        # API: Guardar Playlists
        if parsed.path == "/api/playlists":
            try:
                data = self._read_json_body()
                if not isinstance(data, dict):
                    raise ValueError("Formato de playlists no válido")
                PLAYLISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
                with PLAYLISTS_FILE.open("w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                self._json(200, {"status": "ok"})
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
                self._json(400, {"error": str(error)})
            
        # API: Eliminar canción
        elif parsed.path == "/api/delete_song":
            if not self._require_desktop_session():
                return
            try:
                data = self._read_json_body(max_bytes=64 * 1024)
            except (ValueError, UnicodeDecodeError) as error:
                return self._json(400, {"error": str(error)})
            
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
            if not self._require_desktop_session():
                return
            try:
                data = self._read_json_body(max_bytes=64 * 1024)
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

    def _stream_file(self, filepath, filename, send_body=True):
        """Entrega audio e imágenes con soporte real para HTTP Range."""
        try:
            filesize = os.path.getsize(filepath)
            start = 0
            end = filesize - 1
            status = 200
            range_header = self.headers.get("Range", "").strip()

            if range_header:
                try:
                    unit, range_value = range_header.split("=", 1)
                    if unit.lower() != "bytes" or "," in range_value:
                        raise ValueError
                    start_text, end_text = range_value.split("-", 1)
                    if start_text:
                        start = int(start_text)
                        end = int(end_text) if end_text else end
                    else:
                        suffix_length = int(end_text)
                        if suffix_length <= 0:
                            raise ValueError
                        start = max(filesize - suffix_length, 0)
                    end = min(end, filesize - 1)
                    if start < 0 or start >= filesize or end < start:
                        raise ValueError
                    status = 206
                except (TypeError, ValueError):
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{filesize}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

            lower_name = filename.lower()
            if lower_name.endswith((".jpg", ".jpeg")):
                content_type = "image/jpeg"
            elif lower_name.endswith(".webp"):
                content_type = "image/webp"
            elif lower_name.endswith(".png"):
                content_type = "image/png"
            elif lower_name.endswith((".m4a", ".mp4")):
                content_type = "audio/mp4"
            elif lower_name.endswith(".wav"):
                content_type = "audio/wav"
            elif lower_name.endswith(".flac"):
                content_type = "audio/flac"
            elif lower_name.endswith(".ogg"):
                content_type = "audio/ogg"
            else:
                content_type = "audio/mpeg"

            content_length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(content_length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "private, max-age=3600")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{filesize}")
            self.end_headers()

            if not send_body:
                return
            with open(filepath, "rb") as file_handle:
                file_handle.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk = file_handle.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except OSError as error:
            print(f"Error streaming {filename}: {error}")

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
