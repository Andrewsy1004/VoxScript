"""Guarda en disco cada parte ya transcrita para no pagarla dos veces.

Si un video largo falla a mitad (sin conexión, sin saldo), las partes terminadas
quedan guardadas. Al reintentar con el mismo archivo y la misma configuración,
se reutilizan y solo se envían a la API las que faltan. Al terminar bien, se borran.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from app.core.models import Segment
from app.transcription.base import ChunkTranscription

log = logging.getLogger(__name__)

SAMPLE_BYTES = 1024 * 1024        # se leen el primer y el último MB del archivo
MAX_AGE_SECONDS = 7 * 24 * 3600   # partes huérfanas de más de 7 días se borran


def file_fingerprint(path: Path) -> str:
    """Huella rápida del archivo: tamaño, fecha de modificación y muestras del contenido.

    Leer un video de varios GB completo sería lento; esto basta para detectar
    si es el mismo archivo sin cambios.
    """
    stat = path.stat()
    h = hashlib.sha256(f"{stat.st_size}:{stat.st_mtime_ns}".encode())
    with open(path, "rb") as f:
        h.update(f.read(SAMPLE_BYTES))
        if stat.st_size > SAMPLE_BYTES:
            f.seek(max(SAMPLE_BYTES, stat.st_size - SAMPLE_BYTES))
            h.update(f.read(SAMPLE_BYTES))
    return h.hexdigest()


class ChunkCache:
    def __init__(self, root: Path, max_age_seconds: float = MAX_AGE_SECONDS) -> None:
        self.root = Path(root)
        self.max_age_seconds = max_age_seconds

    def key_for(self, source: Path, *, model: str, language: Optional[str], context: str,
                total_parts: int) -> str:
        """Clave del trabajo: cambia si cambia el archivo o algo que afecte al texto."""
        parts = [file_fingerprint(source), model, language or "", " ".join(context.split()),
                 str(total_parts)]
        return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]

    def _part_path(self, key: str, index: int) -> Path:
        return self.root / key / f"part_{index:04d}.json"

    def get(self, key: str, index: int) -> Optional[ChunkTranscription]:
        try:
            raw = json.loads(self._part_path(key, index).read_text(encoding="utf-8"))
            return ChunkTranscription(
                text=raw["text"],
                segments=[Segment(float(s["start"]), float(s["end"]), s["text"])
                          for s in raw.get("segments", [])])
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("Parte guardada ilegible (%s, %d): %s", key, index, exc)
            return None

    def put(self, key: str, index: int, result: ChunkTranscription) -> None:
        """Guarda una parte. Si falla el disco, solo se registra: no detiene la transcripción."""
        path = self._part_path(key, index)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            data = {"text": result.text, "segments": [asdict(s) for s in result.segments]}
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            log.warning("No se pudo guardar la parte %d: %s", index, exc)

    def clear(self, key: str) -> None:
        shutil.rmtree(self.root / key, ignore_errors=True)

    def prune(self) -> None:
        """Borra trabajos abandonados hace más de `max_age_seconds`."""
        if not self.root.is_dir():
            return
        limit = time.time() - self.max_age_seconds
        for entry in self.root.iterdir():
            try:
                if entry.is_dir() and entry.stat().st_mtime < limit:
                    shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                pass
