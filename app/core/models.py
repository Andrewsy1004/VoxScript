"""Modelos de datos compartidos entre módulos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Segment:
    """Fragmento de texto con su posición en el audio (en segundos)."""

    start: float
    end: float
    text: str


@dataclass
class Transcript:
    """Resultado completo de una transcripción, listo para exportar."""

    text: str
    segments: list[Segment] = field(default_factory=list)
    source_name: str = ""
    duration: Optional[float] = None
    language: Optional[str] = None
    model: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    context: str = ""          # tema o contexto que escribió el usuario
    corrected_by: str = ""     # modelo que corrigió el texto con el contexto (vacío = sin corregir)

    @property
    def has_timestamps(self) -> bool:
        return bool(self.segments)


@dataclass(frozen=True)
class ExportOptions:
    """Opciones de presentación del archivo de salida."""

    include_timestamps: bool = True
    include_header: bool = True
