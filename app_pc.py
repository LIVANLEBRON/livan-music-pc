import webview
import threading
import sys
import os
import time
import urllib.request

# Aseguramos que Python encuentre yt_server.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from yt_server import run_server, PORT

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

    # 3. Ruta del ícono
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')

    # 4. Abrir la ventana de la App
    print("Abriendo aplicación de Windows...")
    webview.create_window(
        title='Livan Music', 
        url=f'http://127.0.0.1:{PORT}',
        width=1100,
        height=750,
        resizable=True,
        background_color='#070B19'
    )
    
    # Iniciar el motor gráfico con ícono
    webview.start(icon=icon_path)

