#!/usr/bin/env bash

set -euo pipefail

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/livan-music"
TOKEN_FILE="$CONFIG_DIR/cloudflare-tunnel.token"
HOSTNAME_FILE="$CONFIG_DIR/cloudflare-hostname.txt"

echo "Configuración privada de Cloudflare Tunnel para Livan Music"
read -rsp "Pega el token del túnel (no se mostrará): " TUNNEL_TOKEN
echo
if [[ ${#TUNNEL_TOKEN} -lt 40 ]]; then
    echo "ERROR: El token parece incompleto."
    exit 1
fi

read -rp "Dirección fija, por ejemplo musica.midominio.com: " TUNNEL_HOSTNAME
TUNNEL_HOSTNAME="${TUNNEL_HOSTNAME#https://}"
TUNNEL_HOSTNAME="${TUNNEL_HOSTNAME%/}"

umask 077
mkdir -p "$CONFIG_DIR"
printf '%s' "$TUNNEL_TOKEN" > "$TOKEN_FILE"
printf '%s' "$TUNNEL_HOSTNAME" > "$HOSTNAME_FILE"
chmod 600 "$TOKEN_FILE" "$HOSTNAME_FILE"

echo "Listo. Al abrir Livan Music también se iniciará el túnel."
