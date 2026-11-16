"""Corrección opcional de la transcripción usando el contexto que escribe el usuario."""

from __future__ import annotations

from typing import Optional

from app.config import Settings
from app.correction.base import Corrector  # noqa: F401


def create_corrector(settings: Settings) -> Optional[Corrector]:
    """Devuelve un corrector si el usuario lo activó; si no, None."""
    if not settings.correct_with_context:
        return None
    if settings.provider == "openai":
        from app.correction.openai_corrector import OpenAICorrector

        return OpenAICorrector(api_key=settings.effective_api_key(),
                               model=settings.correction_model)
    return None
