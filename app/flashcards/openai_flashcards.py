"""Generación de flashcards con un modelo de chat de OpenAI."""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from app.config import DEFAULT_CORRECTION_MODEL
from app.core.errors import ConfigError, TranscriptionError
from app.flashcards.base import Flashcard, FlashcardGenerator

SYSTEM_PROMPT = """\
Eres un experto en aprendizaje y repetición espaciada. A partir de material de \
estudio creas flashcards para estudiar en Anki. El material puede ser la transcripción \
de un video o documentos convertidos a Markdown (títulos, listas y tablas).

Reglas:
- Una sola idea por tarjeta. Pregunta concreta y respuesta corta.
- Pregunta: máximo ~15 palabras. Respuesta: máximo ~25 palabras, idealmente menos.
- Prioriza conceptos, definiciones, causas y efectos, pasos de procesos, datos y \
comparaciones importantes del contenido.
- Si hay resultados de aprendizaje, las tarjetas se crean a partir de ellos: cada \
tarjeta debe ayudar a lograr al menos uno, usando la información del material. Omite \
el contenido que no se relaciona con ningún resultado. Cubre cada resultado que el \
fragmento trate; no fuerces tarjetas de resultados que el fragmento no trata.
- Si no hay resultados de aprendizaje, cubre las ideas principales del material.
- Nada de logística ni relleno (saludos, quién habla, "en este video…", índices, \
encabezados de página).
- Usa solo información que esté en el material. No inventes datos.
- La pregunta debe entenderse sola, sin necesidad de ver el video ni el documento.
- Escribe en el mismo idioma del material.
- Si el contenido no da para más tarjetas útiles, genera menos.
- Responde solo con JSON: {"tarjetas": [{"pregunta": "...", "respuesta": "..."}]}\
"""


class OpenAIFlashcardGenerator(FlashcardGenerator):
    def __init__(self, api_key: str, model: str = DEFAULT_CORRECTION_MODEL,
                 timeout: float = 300.0, max_retries: int = 3, client: Any = None) -> None:
        if client is None and not api_key:
            raise ConfigError("Falta la API key de OpenAI para generar las flashcards.")
        self.model = model or DEFAULT_CORRECTION_MODEL
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
        self._client = client

    def generate_chunk(self, text: str, context: str, max_cards: int,
                       language: Optional[str], source_name: str = "",
                       outcomes: Sequence[str] = ()) -> list[Flashcard]:
        import openai

        user = f"Genera como máximo {max_cards} tarjetas.\n\n"
        if context.strip():
            user += f"Contexto del tema (para entender términos y nombres):\n{context.strip()}\n\n"
        if outcomes:
            user += ("Resultados de aprendizaje (crea las tarjetas a partir de ellos):\n"
                     + "\n".join(f"- {o}" for o in outcomes) + "\n\n")
        user += f"Fuente: {source_name or 'Material'}\n\n{text}"
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": user}],
                response_format={"type": "json_object"},
            )
        except openai.NotFoundError as exc:
            raise TranscriptionError(
                f"El modelo de IA '{self.model}' no existe. Cámbialo en Configuración.") from exc
        except openai.PermissionDeniedError as exc:
            raise TranscriptionError(
                f"Tu cuenta no tiene acceso al modelo de IA '{self.model}'.") from exc
        except openai.APIError as exc:
            raise TranscriptionError(f"Error de OpenAI al crear las flashcards: {exc}") from exc

        self.usage.add(getattr(resp, "usage", None))
        try:
            data = json.loads(resp.choices[0].message.content or "{}")
            items = data.get("tarjetas", [])
            return [Flashcard(str(c.get("pregunta", "")), str(c.get("respuesta", "")))
                    for c in items if isinstance(c, dict)]
        except (ValueError, TypeError, AttributeError, IndexError):
            return []
