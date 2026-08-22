import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path


APP_DIR_NAME = "LivanMusic"
_LOCK = threading.RLock()


def _system_music_dir():
    """Devuelve la carpeta Música propia del sistema operativo."""
    if os.name == "nt":
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "My Music")
            if value:
                return Path(os.path.expandvars(value)).expanduser()
        except (ImportError, OSError):
            pass
    if sys.platform.startswith("linux"):
        try:
            result = subprocess.run(
                ["xdg-user-dir", "MUSIC"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            value = result.stdout.strip()
            if value:
                return Path(value).expanduser()
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
    return Path.home() / "Music"


def _config_dir():
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "livan-music"


SYSTEM_MUSIC_DIR = _system_music_dir().resolve()
DEFAULT_DOWNLOAD_DIR = (SYSTEM_MUSIC_DIR / APP_DIR_NAME).resolve()
CONFIG_DIR = _config_dir().resolve()
SETTINGS_FILE = CONFIG_DIR / "settings.json"
PLAYLISTS_FILE = CONFIG_DIR / "playlists.json"


def _normal_path(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("La ruta no puede estar vacía")
    return Path(os.path.abspath(os.path.expandvars(os.path.expanduser(value.strip())))).resolve()


def _defaults():
    return {"download_dir": str(DEFAULT_DOWNLOAD_DIR), "library_dirs": []}


def _unique_paths(values):
    result = []
    seen = set()
    for value in values:
        try:
            path = _normal_path(value)
        except ValueError:
            continue
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def load_settings():
    with _LOCK:
        data = _defaults()
        if SETTINGS_FILE.is_file():
            try:
                stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    data.update(stored)
            except (OSError, json.JSONDecodeError):
                pass

        try:
            download_dir = _normal_path(data.get("download_dir", ""))
        except ValueError:
            download_dir = DEFAULT_DOWNLOAD_DIR

        extras = _unique_paths(data.get("library_dirs", []))
        extras = [path for path in extras if path != download_dir]
        return {"download_dir": str(download_dir), "library_dirs": [str(path) for path in extras]}


def save_settings(data):
    with _LOCK:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        temporary = SETTINGS_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(SETTINGS_FILE)


def get_download_dir(create=True):
    path = Path(load_settings()["download_dir"])
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_library_dirs(existing_only=True):
    settings = load_settings()
    paths = _unique_paths([settings["download_dir"], *settings["library_dirs"]])
    if existing_only:
        paths = [path for path in paths if path.is_dir()]
    return paths


def source_id(path):
    normalized = os.path.normcase(str(Path(path).resolve()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def describe_library_dirs():
    download_dir = get_download_dir()
    descriptions = []
    for path in get_library_dirs(existing_only=True):
        descriptions.append({
            "id": source_id(path),
            "path": str(path),
            "name": path.name or str(path),
            "is_download": path == download_dir,
        })
    return descriptions


def public_settings():
    download_dir = get_download_dir()
    settings = load_settings()
    return {
        "download_dir": str(download_dir),
        "default_download_dir": str(DEFAULT_DOWNLOAD_DIR),
        "system_music_dir": str(SYSTEM_MUSIC_DIR),
        "library_dirs": describe_library_dirs(),
        "additional_dirs": settings["library_dirs"],
    }


def set_download_dir(value):
    path = _normal_path(value)
    path.mkdir(parents=True, exist_ok=True)
    if not os.access(path, os.W_OK):
        raise PermissionError(f"No se puede escribir en: {path}")

    settings = load_settings()
    settings["download_dir"] = str(path)
    settings["library_dirs"] = [item for item in settings["library_dirs"] if _normal_path(item) != path]
    save_settings(settings)
    return public_settings()


def add_library_dir(value):
    path = _normal_path(value)
    if not path.is_dir():
        raise FileNotFoundError(f"La carpeta no existe: {path}")
    if not os.access(path, os.R_OK):
        raise PermissionError(f"No se puede leer: {path}")

    settings = load_settings()
    download_dir = _normal_path(settings["download_dir"])
    extras = _unique_paths(settings["library_dirs"])
    if path != download_dir and path not in extras:
        extras.append(path)
    settings["library_dirs"] = [str(item) for item in extras]
    save_settings(settings)
    return public_settings()


def remove_library_dir(value):
    path = _normal_path(value)
    settings = load_settings()
    if path == _normal_path(settings["download_dir"]):
        raise ValueError("La carpeta de descargas siempre forma parte de la biblioteca")
    settings["library_dirs"] = [
        str(item) for item in _unique_paths(settings["library_dirs"]) if item != path
    ]
    save_settings(settings)
    return public_settings()


def find_source(source):
    for description in describe_library_dirs():
        if description["id"] == source:
            return Path(description["path"])
    return None


def resolve_library_file(source, relative_name):
    """Resuelve un archivo sin permitir escapar de las carpetas configuradas."""
    if not isinstance(relative_name, str) or not relative_name:
        return None

    candidates = []
    selected = find_source(source) if source else None
    if selected:
        candidates.append(selected)
    else:
        candidates.extend(get_library_dirs(existing_only=True))

    for directory in candidates:
        candidate = (directory / relative_name).resolve()
        try:
            candidate.relative_to(directory.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None
