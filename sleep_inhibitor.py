"""Evita que el equipo suspenda el servidor mientras Livan Music está abierto."""

import ctypes
import os
import shutil
import signal
import subprocess
import sys


class SleepInhibitor:
    """Bloqueo reversible de suspensión para Windows, Linux y macOS."""

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self):
        self._process = None
        self._windows_active = False

    def start(self):
        if os.name == "nt":
            result = ctypes.windll.kernel32.SetThreadExecutionState(
                self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
            )
            self._windows_active = bool(result)
            if self._windows_active:
                print("Suspensión automática bloqueada mientras Livan Music esté abierto.")
            else:
                print("ADVERTENCIA: Windows no permitió bloquear la suspensión automática.")
            return self._windows_active

        if sys.platform.startswith("linux"):
            inhibitor = shutil.which("systemd-inhibit")
            sleeper = shutil.which("sleep")
            if not inhibitor or not sleeper:
                print("ADVERTENCIA: systemd-inhibit no está disponible; no se bloqueó la suspensión.")
                return False
            command = [
                inhibitor,
                "--what=sleep:idle",
                "--who=Livan Music",
                "--why=Servidor de música activo",
                "--mode=block",
                sleeper,
                "infinity",
            ]
        elif sys.platform == "darwin":
            caffeinate = shutil.which("caffeinate")
            if not caffeinate:
                return False
            command = [caffeinate, "-i", "-s"]
        else:
            return False

        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print("Suspensión automática bloqueada mientras Livan Music esté abierto.")
            return True
        except OSError as error:
            self._process = None
            print(f"ADVERTENCIA: no se pudo bloquear la suspensión automática: {error}")
            return False

    def stop(self):
        if os.name == "nt" and self._windows_active:
            ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
            self._windows_active = False

        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except OSError:
                pass
