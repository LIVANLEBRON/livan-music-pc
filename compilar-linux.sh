#!/usr/bin/env bash

set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESCARGAS="$(xdg-user-dir DOWNLOAD 2>/dev/null || true)"
if [[ -z "$DESCARGAS" ]]; then
    DESCARGAS="$HOME/Downloads"
fi

cd "$PROYECTO"
mkdir -p "$DESCARGAS"

CLOUDFLARED="$(command -v cloudflared 2>/dev/null || true)"
if [[ -z "$CLOUDFLARED" && -x "$HOME/.local/bin/cloudflared" ]]; then
    CLOUDFLARED="$HOME/.local/bin/cloudflared"
fi
if [[ -z "$CLOUDFLARED" ]]; then
    echo "ERROR: cloudflared no está instalado."
    exit 1
fi

python3 -m PyInstaller \
    --noconsole \
    --onefile \
    --clean \
    -y \
    --add-data "public:public" \
    --add-data "icon.ico:." \
    --add-data "icon.png:." \
    --add-binary "$CLOUDFLARED:." \
    --collect-all webview \
    --name "Livan-Music" \
    app_pc.py

install -m 755 "dist/Livan-Music" "$DESCARGAS/Livan-Music"

echo "Ejecutable creado en: $DESCARGAS/Livan-Music"
