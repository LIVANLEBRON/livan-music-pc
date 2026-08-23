#!/usr/bin/env bash

set -euo pipefail

YT_DLP_URL="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux"
YT_DLP_SUMS_URL="https://github.com/yt-dlp/yt-dlp/releases/latest/download/SHA2-256SUMS"
DENO_ARCHIVE="deno-x86_64-unknown-linux-gnu.zip"
DENO_URL="https://github.com/denoland/deno/releases/latest/download/$DENO_ARCHIVE"
DENO_SUM_URL="$DENO_URL.sha256sum"

info() {
    printf '\n\033[1;36m%s\033[0m\n' "$1"
}

fail() {
    printf '\nERROR: %s\n' "$1" >&2
    exit 1
}

[[ "$(uname -s)" == "Linux" ]] || fail "Este instalador solamente funciona en Linux."
case "$(uname -m)" in
    x86_64|amd64) ;;
    *) fail "Livan-Music fue compilado para PCs x86_64; esta máquina usa $(uname -m)." ;;
esac

command -v apt-get >/dev/null 2>&1 || fail "No se encontró apt. Usa este script en Linux Mint, Ubuntu o Debian."

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    DISTRO_NAME="${PRETTY_NAME:-Linux basado en Debian}"
else
    DISTRO_NAME="Linux basado en Debian"
fi

printf '%s\n' "=================================================="
printf '%s\n' "  Dependencias de Livan Music para Linux Mint"
printf '%s\n' "=================================================="
printf 'Sistema detectado: %s\n' "$DISTRO_NAME"
printf '%s\n' "Este script no modifica el ejecutable Livan-Music."
printf '%s\n' "Solicitará la contraseña de administrador para instalar dependencias."

info "1/4 - Instalando bibliotecas del sistema y FFmpeg"
sudo -v
sudo apt-get update
sudo apt-get install -y \
    ca-certificates \
    curl \
    unzip \
    ffmpeg \
    libwebkit2gtk-4.1-0 \
    gir1.2-webkit2-4.1 \
    gir1.2-gtk-3.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-libav \
    xdg-user-dirs

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT

info "2/4 - Instalando la versión oficial más reciente de yt-dlp"
curl --fail --location --retry 3 --output "$TEMP_DIR/yt-dlp_linux" "$YT_DLP_URL"
curl --fail --location --retry 3 --output "$TEMP_DIR/SHA2-256SUMS" "$YT_DLP_SUMS_URL"
YT_DLP_SUM="$(grep -E '  yt-dlp_linux$' "$TEMP_DIR/SHA2-256SUMS" | head -n 1 || true)"
[[ -n "$YT_DLP_SUM" ]] || fail "No se encontró la suma SHA-256 de yt-dlp."
(
    cd "$TEMP_DIR"
    printf '%s\n' "$YT_DLP_SUM" | sha256sum --check --strict -
)
sudo install -m 0755 "$TEMP_DIR/yt-dlp_linux" /usr/local/bin/yt-dlp

info "3/4 - Instalando Deno como motor JavaScript para YouTube"
curl --fail --location --retry 3 --output "$TEMP_DIR/$DENO_ARCHIVE" "$DENO_URL"
curl --fail --location --retry 3 --output "$TEMP_DIR/$DENO_ARCHIVE.sha256sum" "$DENO_SUM_URL"
(
    cd "$TEMP_DIR"
    sha256sum --check --strict "$DENO_ARCHIVE.sha256sum"
    unzip -q -o "$DENO_ARCHIVE"
)
[[ -x "$TEMP_DIR/deno" ]] || fail "El paquete descargado no contenía el ejecutable de Deno."
sudo install -m 0755 "$TEMP_DIR/deno" /usr/local/bin/deno

info "4/4 - Verificando la instalación"
command -v ffmpeg >/dev/null 2>&1 || fail "FFmpeg no quedó disponible."
command -v yt-dlp >/dev/null 2>&1 || fail "yt-dlp no quedó disponible."
command -v deno >/dev/null 2>&1 || fail "Deno no quedó disponible."

printf 'FFmpeg: '
ffmpeg -version 2>/dev/null | head -n 1
printf 'yt-dlp: '
yt-dlp --version
printf 'Deno: '
deno --version | head -n 1

printf '\n\033[1;32mInstalación terminada correctamente.\033[0m\n'
printf '%s\n' "Ahora puedes colocar Livan-Music donde quieras, darle permiso y abrirlo:"
printf '%s\n' "  chmod +x Livan-Music"
printf '%s\n' "  ./Livan-Music"
printf '%s\n' "El servidor y el túnel se iniciarán desde el ejecutable privado."
