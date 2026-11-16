"""Punto de entrada de la aplicación de escritorio (y del ejecutable)."""

import sys

from app.config import load_env
from app.ui.main_window import run

if __name__ == "__main__":
    load_env()
    sys.exit(run())
