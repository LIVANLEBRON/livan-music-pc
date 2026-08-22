#!/usr/bin/env bash

set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESCARGAS="$(xdg-user-dir DOWNLOAD 2>/dev/null || true)"
if [[ -z "$DESCARGAS" ]]; then
    DESCARGAS="$HOME/Downloads"
fi

cd "$PROYECTO"
mkdir -p "$DESCARGAS"

python3 -m PyInstaller \
    --noconsole \
    --onefile \
    --clean \
    -y \
    --add-data "public:public" \
    --add-data "icon.ico:." \
    --add-data "icon.png:." \
    --collect-all webview \
    --name "Livan-Music" \
    app_pc.py

install -m 755 "dist/Livan-Music" "$DESCARGAS/Livan-Music"

echo "Ejecutable creado en: $DESCARGAS/Livan-Music"
