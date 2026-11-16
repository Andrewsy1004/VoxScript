"""Exporta la transcripción a un documento de Word (.docx)."""

from __future__ import annotations

from pathlib import Path

from app.core.errors import ConfigError, ExportError
from app.core.models import ExportOptions, Transcript
from app.exporters.base import Exporter
from app.exporters.formatting import build_paragraphs, format_timestamp, header_fields

GRAY = (0x6B, 0x72, 0x80)


class DocxExporter(Exporter):
    key = "docx"
    label = "Word (.docx)"
    extension = ".docx"

    def export(self, transcript: Transcript, path: Path, options: ExportOptions) -> Path:
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor
        except ImportError as exc:
            raise ConfigError("Falta la librería 'python-docx'. Ejecuta: pip install python-docx") from exc

        doc = Document()
        normal = doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(11)
        normal.paragraph_format.space_after = Pt(8)
        normal.paragraph_format.line_spacing = 1.15
        gray = RGBColor(*GRAY)

        doc.core_properties.title = f"Transcripción de {transcript.source_name}".strip()
        doc.add_heading("Transcripción", level=0)

        if options.include_header:
            for label, value in header_fields(transcript):
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                run = p.add_run(f"{label}: ")
                run.bold = True
                p.add_run(value)
            doc.add_paragraph()

        for start, text in build_paragraphs(transcript, options):
            p = doc.add_paragraph()
            if start is not None:
                stamp = p.add_run(f"[{format_timestamp(start)}]  ")
                stamp.bold = True
                stamp.font.size = Pt(9)
                stamp.font.color.rgb = gray
            p.add_run(text)

        try:
            doc.save(str(path))
        except OSError as exc:
            raise ExportError(
                f"No se pudo guardar el documento de Word. ¿Está abierto en otro programa? ({exc})"
            ) from exc
        return path
