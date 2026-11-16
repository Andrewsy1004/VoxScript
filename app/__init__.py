"""Transcriptor: convierte videos en transcripciones TXT o Word usando OpenAI."""

import sys
from pathlib import Path

__version__ = "0.3.0"
APP_NAME = "Transcriptor"


def resource_path(relative: str) -> Path:
    """Ruta a un archivo incluido (assets/…), tanto en desarrollo como en el ejecutable."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative
