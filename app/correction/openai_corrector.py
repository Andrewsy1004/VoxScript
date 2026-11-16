"""Corrección de la transcripción con un modelo de chat de OpenAI."""

from __future__ import annotations

import json
from typing import Any

from app.config import DEFAULT_CORRECTION_MODEL
from app.core.errors import ConfigError, TranscriptionError
from app.correction.base import Corrector

SYSTEM_PROMPT = """\
Eres un corrector de transcripciones automáticas de audio. Recibes líneas numeradas \
de una transcripción y un contexto escrito por el usuario sobre el tema de la grabación.

Corrige SOLO errores evidentes del reconocimiento de voz: palabras mal oídas, nombres \
propios, marcas, términos técnicos, siglas y ortografía, usando el contexto como guía.

Reglas:
- No resumas, no traduzcas, no agregues ni quites ideas, no cambies el estilo ni el orden.
- Mantén el idioma original de cada línea.
- Si una línea está bien o no estás seguro, devuélvela exactamente igual.
- Responde solo con JSON: {"lineas": {"1": "...", "2": "..."}} con exactamente las mismas claves.\
"""


class OpenAICorrector(Corrector):
    def __init__(self, api_key: str, model: str = DEFAULT_CORRECTION_MODEL,
                 timeout: float = 300.0, max_retries: int = 3, client: Any = None) -> None:
        if client is None and not api_key:
            raise ConfigError("Falta la API key de OpenAI para corregir con el contexto.")
        self.model = model or DEFAULT_CORRECTION_MODEL
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
        self._client = client

    def correct_batch(self, lines: list[str], context: str) -> list[str]:
        import openai

        numbered = {str(i + 1): line for i, line in enumerate(lines)}
        user = (f"Contexto del tema:\n{context.strip()}\n\n"
                f"Líneas:\n{json.dumps({'lineas': numbered}, ensure_ascii=False)}")
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": user}],
                response_format={"type": "json_object"},
            )
        except openai.NotFoundError as exc:
            raise TranscriptionError(
                f"El modelo de corrección '{self.model}' no existe. Cámbialo en Configuración."
            ) from exc
        except openai.PermissionDeniedError as exc:
            raise TranscriptionError(
                f"Tu cuenta no tiene acceso al modelo de corrección '{self.model}'.") from exc
        except openai.APIError as exc:
            raise TranscriptionError(f"Error de OpenAI al corregir: {exc}") from exc

        self.usage.add(getattr(resp, "usage", None))
        try:
            data = json.loads(resp.choices[0].message.content or "{}")
            fixed = data.get("lineas", data)
            return [str(fixed[str(i + 1)]) for i in range(len(lines))]
        except (ValueError, KeyError, TypeError, AttributeError, IndexError):
            return lines  # respuesta mal formada: se conserva el original
