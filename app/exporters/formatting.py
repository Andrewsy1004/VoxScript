"""Utilidades de presentación compartidas por todos los exportadores."""

from __future__ import annotations

import re
from typing import Optional

from app.config import LANGUAGES
from app.core.models import ExportOptions, Segment, Transcript

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "desconocida"
    total = int(round(seconds))
    h, m, s = total // 3600, total % 3600 // 60, total % 60
    if h:
        return f"{h} h {m:02d} min {s:02d} s"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


def language_label(code: Optional[str]) -> str:
    for label, value in LANGUAGES:
        if value and value == code:
            return label
    return code or "Detectado automáticamente"


def header_fields(t: Transcript) -> list[tuple[str, str]]:
    fields = [
        ("Archivo", t.source_name),
        ("Fecha", t.created_at.strftime("%d/%m/%Y %H:%M")),
        ("Duración", format_duration(t.duration)),
        ("Idioma", language_label(t.language)),
        ("Modelo", t.model or "—"),
    ]
    if t.context:
        fields.append(("Contexto", " ".join(t.context.split())))
    if t.corrected_by:
        fields.append(("Corrección", f"Revisada con IA ({t.corrected_by}) usando el contexto"))
    return fields


def _group_segments(segments: list[Segment], max_segments: int = 6,
                    pause: float = 2.0) -> list[tuple[float, str]]:
    """Agrupa segmentos en párrafos: corta tras N segmentos o una pausa larga."""
    paragraphs: list[tuple[float, str]] = []
    current: list[Segment] = []
    for seg in segments:
        if current and (len(current) >= max_segments or seg.start - current[-1].end >= pause):
            paragraphs.append((current[0].start, " ".join(s.text for s in current)))
            current = []
        current.append(seg)
    if current:
        paragraphs.append((current[0].start, " ".join(s.text for s in current)))
    return paragraphs


def _split_text(text: str, sentences_per_paragraph: int = 4) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_END.split(text.strip()) if s.strip()]
    return [" ".join(sentences[i:i + sentences_per_paragraph])
            for i in range(0, len(sentences), sentences_per_paragraph)]


def build_paragraphs(t: Transcript, options: ExportOptions) -> list[tuple[Optional[float], str]]:
    """Devuelve (inicio en segundos o None, texto) por párrafo."""
    if t.segments:
        grouped = _group_segments(t.segments)
        if options.include_timestamps:
            return [(start, text) for start, text in grouped]
        return [(None, text) for _, text in grouped]
    return [(None, p) for p in _split_text(t.text)]
