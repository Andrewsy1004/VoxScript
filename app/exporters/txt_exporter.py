"""Exporta la transcripción a texto plano UTF-8."""

from __future__ import annotations

from pathlib import Path

from app.core.errors import ExportError
from app.core.models import ExportOptions, Transcript
from app.exporters.base import Exporter
from app.exporters.formatting import build_paragraphs, format_timestamp, header_fields


class TxtExporter(Exporter):
    key = "txt"
    label = "Texto (.txt)"
    extension = ".txt"

    def render(self, t: Transcript, options: ExportOptions) -> str:
        lines: list[str] = []
        if options.include_header:
            lines += ["TRANSCRIPCIÓN", "=" * 13]
            lines += [f"{label}: {value}" for label, value in header_fields(t)]
            lines.append("")
        for start, text in build_paragraphs(t, options):
            prefix = f"[{format_timestamp(start)}] " if start is not None else ""
            lines += [prefix + text, ""]
        return "\n".join(lines).rstrip() + "\n"

    def export(self, transcript: Transcript, path: Path, options: ExportOptions) -> Path:
        try:
            path.write_text(self.render(transcript, options), encoding="utf-8")
        except OSError as exc:
            raise ExportError(f"No se pudo guardar el archivo de texto: {exc}") from exc
        return path
