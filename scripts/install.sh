#!/usr/bin/env bash
set -e

echo "Instalando Spilberg Agent..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

echo "Baixando dependências externas (ffmpeg, yt-dlp, auto-editor)..."
# No Mac, ffmpeg pode ser instalado via brew
if command -v brew &> /dev/null; then
    brew install ffmpeg
else
    echo "Aviso: brew não encontrado. Certifique-se de instalar o ffmpeg."
fi

echo "Instalação concluída! Rode 'spilberg doctor' para testar."
