"""Arranque y cierre del conector privado de Cloudflare Tunnel."""

import atexit
import os
import shutil
import subprocess
import sys
from pathlib import Path

from library_config import CONFIG_DIR


TOKEN_FILE = CONFIG_DIR / "cloudflare-tunnel.token"
HOSTNAME_FILE = CONFIG_DIR / "cloudflare-hostname.txt"
LOG_FILE = CONFIG_DIR / "cloudflared.log"
EMBEDDED_CONFIG_DIR = "private_defaults"

_process = None
_log_handle = None


def _application_dirs():
    if getattr(sys, "frozen", False):
        yield Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        yield Path(sys.executable).parent
    else:
        yield Path(__file__).resolve().parent


def _private_file(filename):
    """Usa primero la configuración del usuario y luego la incluida en la app."""
    user_file = CONFIG_DIR / filename
    try:
        if user_file.is_file() and user_file.stat().st_size > 0:
            return user_file
    except OSError:
        pass

    for directory in _application_dirs():
        candidate = directory / EMBEDDED_CONFIG_DIR / filename
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
        except OSError:
            continue
    return None


def find_cloudflared():
    """Busca primero el binario empaquetado y luego una instalación del sistema."""
    executable = "cloudflared.exe" if os.name == "nt" else "cloudflared"
    override = os.environ.get("LIVAN_MUSIC_CLOUDFLARED", "").strip()
    candidates = [Path(override)] if override else []
    candidates.extend(directory / executable for directory in _application_dirs())

    system_binary = shutil.which(executable) or shutil.which("cloudflared")
    if system_binary:
        candidates.append(Path(system_binary))
    if sys.platform.startswith("linux"):
        candidates.append(Path.home() / ".local" / "bin" / "cloudflared")

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def configured_hostname():
    hostname_file = _private_file(HOSTNAME_FILE.name)
    if hostname_file is None:
        return ""
    try:
        return hostname_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def tunnel_status():
    running = _process is not None and _process.poll() is None
    return {
        "configured": _private_file(TOKEN_FILE.name) is not None,
        "running": running,
        "hostname": configured_hostname(),
        "log_file": str(LOG_FILE),
    }


def start_tunnel():
    """Inicia un túnel administrado remotamente si existe un token privado."""
    global _process, _log_handle

    if _process is not None and _process.poll() is None:
        return tunnel_status()
    token_file = _private_file(TOKEN_FILE.name)
    if token_file is None:
        print(f"Cloudflare Tunnel no configurado: falta {TOKEN_FILE}")
        return tunnel_status()

    cloudflared = find_cloudflared()
    if not cloudflared:
        print("Cloudflare Tunnel no disponible: no se encontró cloudflared.")
        return tunnel_status()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _log_handle = LOG_FILE.open("a", encoding="utf-8")
    command = [
        cloudflared,
        "tunnel",
        "--no-autoupdate",
        "--loglevel",
        "info",
        "run",
        "--token-file",
        str(token_file),
    ]
    options = {
        "stdin": subprocess.DEVNULL,
        "stdout": _log_handle,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True

    try:
        _process = subprocess.Popen(command, **options)
        print(f"Cloudflare Tunnel iniciado (PID {_process.pid}).")
        hostname = configured_hostname()
        if hostname:
            print(f"Acceso remoto: https://{hostname}")
    except OSError as error:
        print(f"No se pudo iniciar Cloudflare Tunnel: {error}")
        _process = None
        _log_handle.close()
        _log_handle = None
    return tunnel_status()


def stop_tunnel():
    """Cierra únicamente el conector iniciado por esta instancia de la app."""
    global _process, _log_handle

    process = _process
    _process = None
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=6)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        print("Cloudflare Tunnel detenido.")

    if _log_handle is not None:
        _log_handle.close()
        _log_handle = None


atexit.register(stop_tunnel)
