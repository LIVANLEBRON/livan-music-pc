#!/usr/bin/env bash

set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROYECTO"
exec python3 app_pc.py
