#!/usr/bin/env bash
# Abre Transcriptor desde el código fuente (macOS / Linux).
# La primera vez prepara el entorno (unos minutos); después abre directo.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .venv/.instalado ]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "No se encontró Python 3. Instálalo desde https://www.python.org/downloads/"
    read -r -p "Pulsa Enter para cerrar…"
    exit 1
  fi
  echo "Preparando Transcriptor por primera vez. Esto tarda unos minutos…"
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/.instalado
fi

nohup .venv/bin/python main.py >/dev/null 2>&1 &
