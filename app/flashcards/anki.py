"""Exporta flashcards a un archivo .csv que Anki importa directamente.

Formato: CSV de dos columnas (pregunta, respuesta), sin líneas de metadatos,
para que también se vea limpio en Excel. En Anki: Archivo → Importar; Anki
detecta la coma como separador y el mazo se elige en el diálogo de importación.

Se guarda en UTF-8 con BOM para que Excel muestre bien los acentos y la «ñ».
Las comas dentro del texto van entre comillas (módulo csv), así que Excel y
Anki separan bien las columnas.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.core.errors import ExportError
from app.flashcards.base import Flashcard


def _clean(text: str) -> str:
    # Saltos de línea y tabs dentro de un campo partirían la tarjeta en Anki
    return " ".join(text.replace("\t", " ").split())


def export_anki(cards: list[Flashcard], path: Path) -> Path:
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            for c in cards:
                writer.writerow([_clean(c.front), _clean(c.back)])
    except OSError as exc:
        raise ExportError(f"No se pudo guardar el archivo de flashcards: {exc}") from exc
    return path
