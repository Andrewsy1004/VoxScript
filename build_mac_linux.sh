#!/usr/bin/env bash
# Genera dist/Transcriptor (Linux) o dist/Transcriptor.app (macOS).
# PyInstaller no compila para otro sistema: ejecútalo en el sistema de destino.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
python -m unittest discover -s tests -t .
[ -f assets/icon.png ] || python tools/make_icon.py
# En macOS, PyInstaller convierte el PNG a .icns (necesita Pillow, incluido en requirements-dev)
pyinstaller --noconfirm --clean --onefile --windowed --name Transcriptor \
  --icon assets/icon.png --add-data "assets:assets" \
  --collect-all imageio_ffmpeg --collect-all tkinterdnd2 --collect-data docx \
  --collect-all pymupdf4llm --collect-binaries pymupdf \
  --exclude-module onnxruntime --exclude-module pymupdf.layout --exclude-module pymupdf_layout \
  main.py
echo "Listo: revisa la carpeta dist/"
