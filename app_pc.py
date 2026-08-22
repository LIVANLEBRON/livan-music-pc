import threading
import sys
import os
import time
import urllib.request
import webbrowser

# WebKitGTK puede abrir una ventana vacía en algunos equipos Linux con
# Wayland/X11 cuando el renderizador DMABUF no es compatible con el driver.
# Debe definirse antes de importar pywebview/WebKit.
if sys.platform.startswith('linux'):
    os.environ.setdefault('WEBKIT_DISABLE_DMABUF_RENDERER', '1')

try:
    import webview
except ImportError:
    webview = None

# Aseguramos que Python encuentre yt_server.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from yt_server import run_server, PORT


class DesktopApi:
    """Puente mínimo para usar el selector nativo de carpetas."""

    def get_platform(self):
        if sys.platform.startswith('linux'):
            return 'linux'
        if os.name == 'nt':
            return 'windows'
        return 'other'

    def select_folder(self):
        if webview is None or not webview.windows:
            return ""
        try:
            window = webview.windows[0]
            file_dialog = getattr(webview, "FileDialog", None)
            dialog_type = file_dialog.FOLDER if file_dialog else getattr(webview, "FOLDER_DIALOG")
            result = window.create_file_dialog(dialog_type)
            if isinstance(result, (list, tuple)):
                return result[0] if result else ""
            return result or ""
        except Exception as error:
            print(f"No se pudo abrir el selector de carpetas: {error}")
            return ""

def start_background_server():
    print("Iniciando motor de descargas...")
    run_server()

def wait_for_server(port, timeout=15):
    """Espera hasta que el servidor HTTP responda, con timeout."""
    url = f"http://127.0.0.1:{port}/api/status"
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True  # Servidor listo
        except Exception:
            time.sleep(0.3)
    return False  # Timeout

if __name__ == '__main__':
    # 1. Iniciar el servidor local en un hilo invisible
    server_thread = threading.Thread(target=start_background_server, daemon=True)
    server_thread.start()

    # 2. Esperar a que el servidor responda (hasta 15 segundos)
    print("Esperando al servidor...")
    ready = wait_for_server(PORT, timeout=15)
    if not ready:
        print("ADVERTENCIA: El servidor tardó demasiado. Abriendo de todas formas...")

    url = f'http://127.0.0.1:{PORT}'

    if webview is None:
        # En Linux la interfaz web puede funcionar sin instalar pywebview.
        print(f"Abriendo Livan Music en el navegador: {url}")
        webbrowser.open(url)
        server_thread.join()
    else:
        icon_name = 'icon.ico' if os.name == 'nt' else 'icon.png'
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name)
        print("Abriendo Livan Music...")
        webview.create_window(
            title='Livan Music',
            url=url,
            width=1100,
            height=750,
            resizable=True,
            background_color='#070B19',
            js_api=DesktopApi()
        )
        start_options = {"icon": icon_path} if os.path.isfile(icon_path) else {}
        if sys.platform.startswith('linux'):
            start_options["gui"] = "gtk"
        webview.start(**start_options)
