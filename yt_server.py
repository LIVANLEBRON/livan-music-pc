import subprocess, json, os, socket, tempfile
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import mimetypes

import sys

PORT = int(os.environ.get("PORT", 8642))
# Carpeta permanente para la música de la PC
PC_MUSIC_DIR = os.path.join(os.path.expanduser("~"), "Music", "LivanMusic")
os.makedirs(PC_MUSIC_DIR, exist_ok=True)

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

# Ruta a yt-dlp y ffmpeg empaquetados
YTDLP_PATH = os.path.join(exe_dir, "yt-dlp.exe")
FFMPEG_PATH = os.path.join(exe_dir, "ffmpeg.exe")

# Fallback: si no existe en exe_dir, buscar en _MEIPASS
if not os.path.exists(YTDLP_PATH):
    YTDLP_PATH = os.path.join(application_path, "yt-dlp.exe")
if not os.path.exists(FFMPEG_PATH):
    FFMPEG_PATH = os.path.join(application_path, "ffmpeg.exe")


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
            self._json(200, {"status": "ok"})
            
        # API: Búsqueda en YouTube
        elif parsed.path == "/search":
            q = parse_qs(parsed.query).get("q", [""])[0]
            if not q:
                return self._json(400, {"error": "Falta q"})
            try:
                cmd = [YTDLP_PATH, f"ytsearch15:{q}", "--flat-playlist", "-j", "--no-download", "--no-warnings"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
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
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            try:
                url = f"https://www.youtube.com/watch?v={vid}"
                print(f"Descargando (SSE) en PC: {url}")
                output = os.path.join(PC_MUSIC_DIR, "%(title)s - %(channel)s.%(ext)s")
                
                cmd = [
                    YTDLP_PATH, "-f", "18/best", 
                    "--extract-audio", "--audio-format", "m4a",
                    "--ffmpeg-location", FFMPEG_PATH,
                    "--write-thumbnail", "-o", output, 
                    "--newline", "--no-playlist", "--no-warnings", 
                    "--extractor-args", "youtube:player_client=android", url
                ]
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
                
                last_msg = "Fallo desconocido"
                for line in process.stdout:
                    if not line.strip(): continue
                    
                    last_msg = line.strip()
                    data_to_send = {"status": "processing", "text": last_msg}
                    
                    if "[download]" in line and "%" in line:
                        data_to_send["status"] = "downloading"
                        
                    self.wfile.write(f"data: {json.dumps(data_to_send)}\n\n".encode())
                    self.wfile.flush()
                
                process.wait()
                if process.returncode == 0:
                    self.wfile.write(f"data: {json.dumps({'status': 'done', 'text': 'Descarga Completada'})}\n\n".encode())
                else:
                    self.wfile.write(f"data: {json.dumps({'status': 'error', 'text': f'Error: {last_msg[:60]}'})}\n\n".encode())
                self.wfile.flush()
                
            except Exception as e:
                self.wfile.write(f"data: {json.dumps({'status': 'error', 'text': str(e)})}\n\n".encode())
                self.wfile.flush()

        # API: Obtener biblioteca de música local (para el reproductor web)
        elif parsed.path == "/library":
            songs = []
            for f in os.listdir(PC_MUSIC_DIR):
                if f.endswith(".m4a") or f.endswith(".mp3") or f.endswith(".mp4"):
                    # Parsear nombre básico "Titulo - Artista.ext"
                    base_name = f.rsplit(".", 1)[0]
                    name_parts = base_name.split(" - ", 1)
                    title = name_parts[0]
                    artist = name_parts[1] if len(name_parts) > 1 else "Unknown"
                    
                    thumbnail_url = ""
                    for ext in [".jpg", ".webp", ".png"]:
                        if os.path.exists(os.path.join(PC_MUSIC_DIR, base_name + ext)):
                            thumbnail_url = f"/stream?file={base_name + ext}"
                            break
                            
                    songs.append({
                        "filename": f,
                        "title": title,
                        "artist": artist,
                        "thumbnail_url": thumbnail_url
                    })
            self._json(200, {"songs": songs})

        # API: Stream audio local
        elif parsed.path.startswith("/stream"):
            filename = parse_qs(parsed.query).get("file", [""])[0]
            filepath = os.path.join(PC_MUSIC_DIR, filename)
            if not os.path.exists(filepath):
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
                else:
                    content_type = "audio/mp4" if filename.endswith(".m4a") else "audio/mpeg"
                    
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
            playlist_file = os.path.join(PC_MUSIC_DIR, "playlists.json")
            if os.path.exists(playlist_file):
                with open(playlist_file, "r", encoding="utf-8") as f:
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
            
            playlist_file = os.path.join(PC_MUSIC_DIR, "playlists.json")
            with open(playlist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
            self._json(200, {"status": "ok"})
            
        # API: Eliminar canción
        elif parsed.path == "/api/delete_song":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode('utf-8'))
            
            filename = data.get("filename", "")
            if filename:
                filepath = os.path.join(PC_MUSIC_DIR, filename)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        # También eliminar la portada si existe
                        base_name = filename.rsplit(".", 1)[0]
                        for ext in [".jpg", ".webp", ".png"]:
                            thumb_path = os.path.join(PC_MUSIC_DIR, base_name + ext)
                            if os.path.exists(thumb_path):
                                os.remove(thumb_path)
                        self._json(200, {"status": "ok"})
                        return
                    except Exception as e:
                        self._json(500, {"error": str(e)})
                        return
            self._json(400, {"error": "Archivo no encontrado"})
            
        else:
            self.send_error(404)

    def _handle_download(self, vid, out_dir, delete_after):
        try:
            url = f"https://www.youtube.com/watch?v={vid}"
            print(f"Descargando: {url}")
            output = os.path.join(out_dir, "%(id)s.%(ext)s")
            
            cmd = [YTDLP_PATH, "-f", "bestaudio[ext=m4a]/bestaudio", "-o", output, "--no-playlist", "--no-mtime", "--no-warnings", "--print", "after_move:filepath", url]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
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
        self.wfile.write(json.dumps(data).encode())

def run_server():
    ip = get_local_ip()
    print("="*50)
    print("Servidor y Reproductor Web Livan")
    print("="*50)
    print(f"API para celular: http://{ip}:{PORT}")
    print(f"Reproductor Local: http://localhost:{PORT}")
    print(f"Musica PC: {PC_MUSIC_DIR}")
    print("="*50)
    
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()

if __name__ == "__main__":
    run_server()
