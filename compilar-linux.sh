#!/usr/bin/env bash

set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESCARGAS="$(xdg-user-dir DOWNLOAD 2>/dev/null || true)"
if [[ -z "$DESCARGAS" ]]; then
    DESCARGAS="$HOME/Downloads"
fi

cd "$PROYECTO"
mkdir -p "$DESCARGAS"

PORTABLE_TUNNEL=false
if [[ "${1:-}" == "--portable-tunnel" ]]; then
    PORTABLE_TUNNEL=true
elif [[ -n "${1:-}" ]]; then
    echo "Uso: $0 [--portable-tunnel]"
    exit 2
fi

CLOUDFLARED="$(command -v cloudflared 2>/dev/null || true)"
if [[ -z "$CLOUDFLARED" && -x "$HOME/.local/bin/cloudflared" ]]; then
    CLOUDFLARED="$HOME/.local/bin/cloudflared"
fi
if [[ -z "$CLOUDFLARED" ]]; then
    echo "ERROR: cloudflared no está instalado."
    exit 1
fi

PYINSTALLER_ARGS=(
    --noconsole
    --onefile
    --clean
    -y
    --add-data "$PROYECTO/public:public"
    --add-data "$PROYECTO/icon.ico:."
    --add-data "$PROYECTO/icon.png:."
    --add-binary "$CLOUDFLARED:."
    --collect-all webview
    --name "Livan-Music"
)
BUILD_OUTPUT="dist/Livan-Music"
PORTABLE_BUILD_DIR=""

if [[ "$PORTABLE_TUNNEL" == true ]]; then
    TOKEN_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/livan-music/cloudflare-tunnel.token"
    HOSTNAME_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/livan-music/cloudflare-hostname.txt"
    if [[ ! -s "$TOKEN_FILE" || ! -s "$HOSTNAME_FILE" ]]; then
        echo "ERROR: falta la configuración privada del túnel."
        echo "Ejecuta primero: ./configurar-tunel-linux.sh"
        exit 1
    fi
    PYINSTALLER_ARGS+=(
        --add-data "$TOKEN_FILE:private_defaults"
        --add-data "$HOSTNAME_FILE:private_defaults"
    )
    PORTABLE_BUILD_DIR="$(mktemp -d)"
    trap 'rm -rf -- "$PORTABLE_BUILD_DIR"' EXIT
    mkdir -p "$PORTABLE_BUILD_DIR/work" "$PORTABLE_BUILD_DIR/spec" "$PORTABLE_BUILD_DIR/dist"
    PYINSTALLER_ARGS+=(
        --workpath "$PORTABLE_BUILD_DIR/work"
        --specpath "$PORTABLE_BUILD_DIR/spec"
        --distpath "$PORTABLE_BUILD_DIR/dist"
    )
    BUILD_OUTPUT="$PORTABLE_BUILD_DIR/dist/Livan-Music"
    echo "AVISO: creando una versión privada con la credencial del túnel incluida."
fi

python3 -m PyInstaller "${PYINSTALLER_ARGS[@]}" "$PROYECTO/app_pc.py"

install -m 755 "$BUILD_OUTPUT" "$DESCARGAS/Livan-Music"

echo "Ejecutable creado en: $DESCARGAS/Livan-Music"
if [[ "$PORTABLE_TUNNEL" == true ]]; then
    echo "Versión portátil privada: no compartas este ejecutable públicamente."
fi
