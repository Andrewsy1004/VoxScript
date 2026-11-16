"""Documentos de estudio (PDF, Word, Markdown, texto) convertidos a Markdown.

El Markdown conserva títulos, listas y tablas, que ayudan al modelo a entender
la estructura del material al crear las flashcards.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import DocumentError

SUPPORTED_DOC_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


@dataclass(frozen=True)
class StudySource:
    name: str      # nombre visible de la fuente (p. ej., el archivo)
    markdown: str  # contenido en Markdown


def to_markdown(path: Path) -> StudySource:
    """Convierte un documento a Markdown. Lanza DocumentError si no se puede."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".doc":
        raise DocumentError(f"'{path.name}' es un Word antiguo (.doc). "
                            "Ábrelo en Word y guárdalo como .docx.")
    if ext not in SUPPORTED_DOC_EXTENSIONS:
        raise DocumentError(f"Formato de documento no compatible: '{path.name}'.")
    if not path.is_file():
        raise DocumentError(f"No se encontró el documento '{path.name}'.")
    try:
        if ext == ".pdf":
            text = _pdf_to_markdown(path)
        elif ext == ".docx":
            text = _docx_to_markdown(path)
        else:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
    except DocumentError:
        raise
    except Exception as exc:  # archivo dañado, protegido con contraseña, etc.
        raise DocumentError(f"No se pudo leer '{path.name}': {exc}") from exc
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not re.search(r"\w", text):
        if ext == ".pdf":
            raise DocumentError(f"'{path.name}' no tiene texto seleccionable "
                                "(parece un PDF escaneado).")
        raise DocumentError(f"'{path.name}' está vacío.")
    return StudySource(path.name, text)


# ---------- PDF ----------

def _pdf_to_markdown(path: Path) -> str:
    import pymupdf
    import pymupdf4llm

    # Sin el motor de diseño (red neuronal + OCR): es mucho más liviano para el
    # ejecutable y basta para PDFs con texto seleccionable.
    pymupdf4llm.use_layout(False)
    # Se abre aquí para cerrar el archivo al terminar (si no, queda bloqueado en Windows).
    with pymupdf.open(str(path)) as doc:
        if doc.needs_pass:
            raise DocumentError(f"'{path.name}' está protegido con contraseña.")
        return pymupdf4llm.to_markdown(doc, show_progress=False)


# ---------- Word ----------

def _docx_to_markdown(path: Path) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path))
    body = document.element.body
    lines: list[str] = []
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            line = _paragraph_md(Paragraph(child, document))
            if line:
                lines.append(line)
        elif tag == "tbl":
            table = _table_md(Table(child, document))
            if table:
                lines.append(table)
    return "\n\n".join(lines)


def _heading_level(style_name: str) -> int:
    name = style_name.lower()
    if name in ("title", "título"):
        return 1
    m = re.match(r"(heading|título|titulo|encabezado)\s*(\d)", name)
    return min(int(m.group(2)), 6) if m else 0


def _runs_md(paragraph) -> str:
    parts = []
    for run in paragraph.runs:
        text = run.text
        if run.bold and text.strip():
            lead, core, trail = re.match(r"(\s*)(.*?)(\s*)$", text, re.S).groups()
            text = f"{lead}**{core}**{trail}"
        parts.append(text)
    return "".join(parts).strip() or paragraph.text.strip()


def _paragraph_md(paragraph) -> str:
    style = paragraph.style.name if paragraph.style is not None else ""
    level = _heading_level(style)
    if level:
        text = paragraph.text.strip()
        return f"{'#' * level} {text}" if text else ""
    text = _runs_md(paragraph)
    if not text:
        return ""
    lower = style.lower()
    if "list number" in lower or "lista con números" in lower:
        return f"1. {text}"
    if "list" in lower or "lista" in lower or paragraph._p.pPr is not None and \
            paragraph._p.pPr.numPr is not None:
        return f"- {text}"
    return text


def _table_md(table) -> str:
    rows = []
    for row in table.rows:
        cells = [" ".join(c.text.split()).replace("|", "\\|") for c in row.cells]
        rows.append(cells)
    if not rows or not any(any(c for c in r) for r in rows):
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)
