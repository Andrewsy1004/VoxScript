"""Transcripción con la API de OpenAI (/v1/audio/transcriptions)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.config import DEFAULT_MODEL
from app.core.errors import ConfigError, TranscriptionError
from app.core.models import Segment
from app.transcription.base import ChunkTranscription, Transcriber


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Lee un campo tanto de objetos del SDK como de diccionarios."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class OpenAITranscriber(Transcriber):
    # La API acepta hasta 25 MB por archivo; dejamos 1 MB de margen.
    max_file_bytes = 24 * 1024 * 1024

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, timeout: float = 600.0,
                 max_retries: int = 3, client: Any = None) -> None:
        if client is None and not api_key:
            raise ConfigError(
                "Falta la API key de OpenAI. Agrégala en Configuración "
                "o en la variable de entorno OPENAI_API_KEY."
            )
        self.model = model or DEFAULT_MODEL
        self._client = client or self._make_client(api_key, timeout, max_retries)
        # No todos los modelos devuelven marcas de tiempo (verbose_json).
        # Se averigua en la primera llamada y se recuerda.
        self._segments_supported: Optional[bool] = None

    @staticmethod
    def _make_client(api_key: str, timeout: float, max_retries: int) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ConfigError("Falta la librería 'openai'. Ejecuta: pip install openai") from exc
        return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def _create(self, audio_path: Path, **params: Any) -> Any:
        with open(audio_path, "rb") as f:
            return self._client.audio.transcriptions.create(file=f, **params)

    def transcribe(self, audio_path: Path, language: Optional[str] = None,
                   prompt: Optional[str] = None) -> ChunkTranscription:
        import openai

        params: dict[str, Any] = {"model": self.model}
        if language:
            params["language"] = language
        if prompt:
            params["prompt"] = prompt

        try:
            if self._segments_supported is not False:
                try:
                    resp = self._create(audio_path, response_format="verbose_json",
                                        timestamp_granularities=["segment"], **params)
                    self._segments_supported = True
                    return self._parse_verbose(resp)
                except openai.BadRequestError:
                    if self._segments_supported:
                        raise  # el modelo sí soporta tiempos: el error es otro
                    self._segments_supported = False
            resp = self._create(audio_path, response_format="json", **params)
            return ChunkTranscription(text=(_get(resp, "text") or "").strip())

        except openai.AuthenticationError as exc:
            raise TranscriptionError(
                "OpenAI rechazó la API key. Revísala en Configuración.") from exc
        except openai.PermissionDeniedError as exc:
            raise TranscriptionError(
                f"Tu cuenta de OpenAI no tiene acceso al modelo '{self.model}'.") from exc
        except openai.NotFoundError as exc:
            raise TranscriptionError(
                f"El modelo '{self.model}' no existe. Cámbialo en Configuración.") from exc
        except openai.RateLimitError as exc:
            if _get(exc, "code") == "insufficient_quota" or "insufficient_quota" in str(exc):
                raise TranscriptionError(
                    "Tu cuenta de OpenAI no tiene saldo. Recárgalo en "
                    "platform.openai.com/settings/organization/billing.") from exc
            raise TranscriptionError(
                "OpenAI está limitando las solicitudes. Espera un momento y vuelve a intentarlo."
            ) from exc
        except openai.APITimeoutError as exc:
            raise TranscriptionError(
                "OpenAI tardó demasiado en responder. Vuelve a intentarlo.") from exc
        except openai.APIConnectionError as exc:
            raise TranscriptionError(
                "No hay conexión con OpenAI. Revisa tu conexión a internet.") from exc
        except openai.BadRequestError as exc:
            raise TranscriptionError(f"OpenAI rechazó el audio: {exc}") from exc
        except openai.APIError as exc:
            raise TranscriptionError(f"Error de OpenAI: {exc}") from exc

    @staticmethod
    def _parse_verbose(resp: Any) -> ChunkTranscription:
        segments = [
            Segment(float(_get(s, "start", 0.0)), float(_get(s, "end", 0.0)),
                    (_get(s, "text") or "").strip())
            for s in (_get(resp, "segments") or [])
        ]
        return ChunkTranscription(text=(_get(resp, "text") or "").strip(),
                                  segments=[s for s in segments if s.text])
