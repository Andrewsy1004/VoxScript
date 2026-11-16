"""Registro de formatos de salida.

Para añadir un formato (PDF, SRT, Markdown...): crea una clase que herede de
`Exporter` y agrégala a `_ALL`. La interfaz la mostrará automáticamente.
"""

from __future__ import annotations

from app.core.errors import ConfigError
from app.exporters.base import Exporter
from app.exporters.docx_exporter import DocxExporter
from app.exporters.txt_exporter import TxtExporter

_ALL: list[Exporter] = [DocxExporter(), TxtExporter()]
EXPORTERS: dict[str, Exporter] = {e.key: e for e in _ALL}


def get_exporter(key: str) -> Exporter:
    try:
        return EXPORTERS[key]
    except KeyError:
        raise ConfigError(f"Formato de salida desconocido: '{key}'.") from None


def available_formats() -> list[tuple[str, str]]:
    """[(clave, etiqueta)] en el orden en que se muestran."""
    return [(e.key, e.label) for e in _ALL]
