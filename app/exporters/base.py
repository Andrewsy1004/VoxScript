"""Contrato común para los formatos de salida."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.core.models import ExportOptions, Transcript


class Exporter(ABC):
    key: str          # identificador interno: "txt", "docx"...
    label: str        # texto visible en la interfaz
    extension: str    # con punto: ".txt"

    @abstractmethod
    def export(self, transcript: Transcript, path: Path, options: ExportOptions) -> Path:
        """Escribe el archivo y devuelve su ruta."""
