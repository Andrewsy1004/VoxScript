"""Flashcards para Anki generadas a partir del contenido del video."""

from __future__ import annotations

from typing import Optional

from app.config import Settings
from app.flashcards.base import Flashcard, FlashcardGenerator  # noqa: F401


def create_flashcard_generator(settings: Settings) -> Optional[FlashcardGenerator]:
    """Devuelve un generador si el usuario activó las flashcards; si no, None."""
    if not settings.make_flashcards:
        return None
    if settings.provider == "openai":
        from app.flashcards.openai_flashcards import OpenAIFlashcardGenerator

        return OpenAIFlashcardGenerator(api_key=settings.effective_api_key(),
                                        model=settings.correction_model)
    return None
