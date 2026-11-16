"""Proveedores de transcripción.

Para añadir otro proveedor (AssemblyAI, Deepgram, un Whisper local...):
  1. Crea una clase que herede de `Transcriber` en un módulo nuevo.
  2. Regístrala en `create_transcriber`.
El resto de la aplicación no cambia.
"""

from __future__ import annotations

from app.config import Settings
from app.core.errors import ConfigError
from app.transcription.base import ChunkTranscription, Transcriber  # noqa: F401


def create_transcriber(settings: Settings) -> Transcriber:
    if settings.provider == "openai":
        from app.transcription.openai_provider import OpenAITranscriber

        return OpenAITranscriber(api_key=settings.effective_api_key(), model=settings.model)
    raise ConfigError(f"Proveedor de transcripción desconocido: '{settings.provider}'.")
