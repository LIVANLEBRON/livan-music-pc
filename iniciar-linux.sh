#!/usr/bin/env bash

set -uo pipefail

PROYECTO="/run/media/livana/Datos/livan-music-pc"
cd "$PROYECTO" || exit 1
exec python3 app_pc.py
