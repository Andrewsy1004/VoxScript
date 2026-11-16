"""Utilidades de prueba: genera videos sintéticos y un motor falso (sin gastar en la API)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from app.core.models import Segment
from app.media import find_ffmpeg
from app.transcription.base import ChunkTranscription, Transcriber


def make_video(path: Path, seconds: int = 5, audio: bool = True) -> Path:
    args = [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc=size=160x120:rate=10:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-shortest"]
    args.append(str(path))
    subprocess.run(args, check=True)
    return path


class FakeTranscriber(Transcriber):
    model = "modelo-de-prueba"

    def __init__(self, max_file_bytes: int = 24 * 1024 * 1024, with_segments: bool = True) -> None:
        self.max_file_bytes = max_file_bytes
        self.with_segments = with_segments
        self.calls: list[tuple[Path, Optional[str], Optional[str]]] = []

    def transcribe(self, audio_path, language=None, prompt=None) -> ChunkTranscription:
        self.calls.append((audio_path, language, prompt))
        n = len(self.calls)
        text = f"Hola, esta es la parte {n}. Segunda frase de la parte {n}."
        segments = [Segment(0.0, 2.0, f"Hola, esta es la parte {n}."),
                    Segment(2.0, 4.0, f"Segunda frase de la parte {n}.")] if self.with_segments else []
        return ChunkTranscription(text, segments)
