"""Contrato de los correctores: revisan la transcripción usando el contexto del tema.

La lógica común (dividir en lotes, proteger contra respuestas raras, rearmar los
segmentos con sus tiempos) vive aquí. Cada motor solo implementa `correct_batch`.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Callable, Optional

from app.core.costs import TracksUsage
from app.core.models import Segment, Transcript

BATCH_CHARS = 6000  # texto por llamada: suficiente contexto sin respuestas enormes
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def _batches(lines: list[str], max_chars: int) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    size = 0
    for line in lines:
        if current and size + len(line) > max_chars:
            batches.append(current)
            current, size = [], 0
        current.append(line)
        size += len(line)
    if current:
        batches.append(current)
    return batches


def _is_safe(original: str, fixed: str) -> bool:
    """Descarta correcciones vacías o que cambian demasiado el largo (posible invención)."""
    fixed = fixed.strip()
    if not fixed:
        return False
    n = len(original.strip())
    return len(fixed) <= n * 1.6 + 20 and len(fixed) >= n * 0.5 - 10


class Corrector(TracksUsage, ABC):
    model: str = ""

    @abstractmethod
    def correct_batch(self, lines: list[str], context: str) -> list[str]:
        """Devuelve las mismas líneas, en el mismo orden, con los errores corregidos."""

    def correct(
        self,
        transcript: Transcript,
        context: str,
        on_progress: Optional[Callable[[float], None]] = None,
        check_cancel: Optional[Callable[[], None]] = None,
    ) -> Transcript:
        if transcript.segments:
            lines = [s.text for s in transcript.segments]
        else:
            lines = [s.strip() for s in _SENTENCE_END.split(transcript.text) if s.strip()]
        if not lines:
            return transcript

        batches = _batches(lines, BATCH_CHARS)
        fixed_lines: list[str] = []
        for i, batch in enumerate(batches):
            fixed = self.correct_batch(batch, context)
            if len(fixed) != len(batch):
                fixed = batch  # la respuesta no respeta la estructura: se deja sin corregir
            fixed_lines += [f.strip() if _is_safe(o, f) else o for o, f in zip(batch, fixed)]
            if on_progress:
                on_progress((i + 1) / len(batches))
            if check_cancel:
                check_cancel()

        if transcript.segments:
            segments = [Segment(s.start, s.end, t)
                        for s, t in zip(transcript.segments, fixed_lines)]
            return replace(transcript, segments=segments,
                           text=" ".join(fixed_lines), corrected_by=self.model)
        return replace(transcript, text=" ".join(fixed_lines), corrected_by=self.model)
