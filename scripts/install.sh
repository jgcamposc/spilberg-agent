#!/usr/bin/env bash
set -e

set -u

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "Esta v1 é suportada apenas no macOS Apple Silicon. Consulte docs/installation.md."
  exit 1
fi

RUNTIME_DIR="${SPILBERG_RUNTIME_DIR:-$HOME/Library/Application Support/Spilberg}"
echo "Instalando Spilberg Agent em runtime privado: $RUNTIME_DIR"
python3 "$(dirname "$0")/bootstrap.py" --runtime-dir "$RUNTIME_DIR"
