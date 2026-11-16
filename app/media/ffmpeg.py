"""Lectura de metadatos, extracción de audio y división en partes con FFmpeg.

Se usa el binario que trae el paquete `imageio-ffmpeg`, de modo que el
ejecutable final incluye FFmpeg y el usuario no tiene que instalar nada.
Si no está disponible, se busca `ffmpeg` en el PATH.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.errors import MediaError

SUPPORTED_EXTENSIONS = {
    # video
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".wmv", ".flv", ".m4v",
    ".mpeg", ".mpg", ".3gp", ".ts", ".mts",
    # audio
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus", ".wma",
}

# Audio de salida: mono, 16 kHz, MP3 a 32 kbps (~14 MB por hora).
# Es suficiente para reconocimiento de voz y mantiene los archivos pequeños.
AUDIO_ARGS = ["-vn", "-map", "0:a:0", "-ac", "1", "-ar", "16000",
              "-c:a", "libmp3lame", "-b:a", "32k"]

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_AUDIO_STREAM_RE = re.compile(r"Stream #\S+.*?: Audio:")


@dataclass(frozen=True)
class MediaInfo:
    duration: Optional[float]
    has_audio: bool


@dataclass(frozen=True)
class AudioChunk:
    path: Path
    offset: float  # segundo del audio original en el que empieza esta parte
    duration: Optional[float]


def find_ffmpeg() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # paquete ausente o sin binario para esta plataforma
        pass
    path = shutil.which("ffmpeg")
    if path:
        return path
    raise MediaError(
        "No se encontró FFmpeg. Instala el paquete 'imageio-ffmpeg' "
        "o añade FFmpeg al PATH del sistema."
    )


def _run(args: list[str]) -> subprocess.CompletedProcess:
    kwargs = {}
    if sys.platform == "win32":
        # Evita que se abra una consola negra en el ejecutable con ventana.
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        args,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )


def _tail(stderr: str, lines: int = 3) -> str:
    useful = [ln for ln in stderr.strip().splitlines() if ln.strip()]
    return "\n".join(useful[-lines:])


def probe(path: Path) -> MediaInfo:
    """Lee duración y si hay pista de audio, sin depender de ffprobe."""
    if not path.is_file():
        raise MediaError(f"No existe el archivo: {path}")
    result = _run([find_ffmpeg(), "-hide_banner", "-i", str(path)])
    err = result.stderr  # ffmpeg -i sin salida siempre "falla"; la info va a stderr
    if "Invalid data found" in err or "Stream #" not in err:
        raise MediaError(
            f"No se pudo leer '{path.name}'. El archivo puede estar dañado "
            "o tener un formato no compatible."
        )
    match = _DURATION_RE.search(err)
    duration = None
    if match:
        h, m, s = match.groups()
        duration = int(h) * 3600 + int(m) * 60 + float(s)
    return MediaInfo(duration=duration, has_audio=bool(_AUDIO_STREAM_RE.search(err)))


def extract_audio(source: Path, dest: Path) -> Path:
    """Extrae la primera pista de audio a MP3 mono 16 kHz."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = [find_ffmpeg(), "-hide_banner", "-nostdin", "-y", "-i", str(source),
            *AUDIO_ARGS, str(dest)]
    result = _run(args)
    if result.returncode != 0 or not dest.is_file() or dest.stat().st_size == 0:
        raise MediaError(
            f"No se pudo extraer el audio de '{source.name}'.\n{_tail(result.stderr)}"
        )
    return dest


def split_audio(audio: Path, duration: Optional[float], max_bytes: int,
                work_dir: Path) -> list[AudioChunk]:
    """Divide el audio en partes que no superen `max_bytes`.

    Si ya cabe, devuelve una sola parte. Las partes se cortan por tiempo
    (sin recodificar), con un 10 % de margen sobre el tamaño máximo.
    """
    size = audio.stat().st_size
    if size <= max_bytes:
        return [AudioChunk(audio, 0.0, duration)]

    if not duration:
        duration = probe(audio).duration
    if not duration:
        raise MediaError("No se pudo calcular la duración del audio para dividirlo.")

    parts = math.ceil(size / (max_bytes * 0.9))
    segment_time = math.ceil(duration / parts)
    work_dir.mkdir(parents=True, exist_ok=True)
    pattern = work_dir / "parte_%03d.mp3"
    result = _run([find_ffmpeg(), "-hide_banner", "-nostdin", "-y", "-i", str(audio),
                   "-f", "segment", "-segment_time", str(segment_time),
                   "-reset_timestamps", "1", "-c", "copy", str(pattern)])
    files = sorted(work_dir.glob("parte_*.mp3"))
    if result.returncode != 0 or not files:
        raise MediaError(f"No se pudo dividir el audio.\n{_tail(result.stderr)}")

    chunks: list[AudioChunk] = []
    offset = 0.0
    for f in files:
        if f.stat().st_size > max_bytes:
            raise MediaError("Una de las partes del audio sigue siendo demasiado grande.")
        part_duration = probe(f).duration
        chunks.append(AudioChunk(f, offset, part_duration))
        offset += part_duration if part_duration else segment_time
    return chunks
