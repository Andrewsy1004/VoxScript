"""Contrato común para cualquier motor de transcripción."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.models import Segment


@dataclass
class ChunkTranscription:
    """Transcripción de una parte del audio. Los tiempos son relativos a esa parte."""

    text: str
    segments: list[Segment] = field(default_factory=list)


class Transcriber(ABC):
    #: Tamaño máximo de archivo que acepta el motor. El pipeline divide el audio para respetarlo.
    max_file_bytes: int = 24 * 1024 * 1024
    #: Nombre del modelo, para mostrarlo en el documento.
    model: str = ""

    @abstractmethod
    def transcribe(self, audio_path: Path, language: Optional[str] = None,
                   prompt: Optional[str] = None) -> ChunkTranscription:
        """Transcribe un archivo de audio.

        `language`: código ISO-639-1 ("es") o None para detección automática.
        `prompt`: texto previo para dar continuidad entre partes.
        """
