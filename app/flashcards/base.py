"""Contrato de los generadores de flashcards a partir del material de estudio.

El material puede ser la transcripción del video, documentos (PDF, Word…)
convertidos a Markdown, o ambos. Cuanto más material, más tarjetas.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from app.core.costs import TracksUsage
from app.core.models import Transcript
from app.documents import StudySource

CHUNK_CHARS = 12000      # texto por llamada al modelo
MIN_CARDS, MAX_CARDS = 5, 80
WORDS_PER_CARD = 250     # objetivo aproximado: una tarjeta cada ~250 palabras de material
CARDS_PER_OUTCOME = 2    # mínimo de tarjetas por resultado de aprendizaje
MIN_CARDS_PER_CHUNK = 2
TRANSCRIPT_SOURCE = "Transcripción del video"


@dataclass(frozen=True)
class Flashcard:
    front: str  # pregunta
    back: str   # respuesta


def target_cards(words: int, outcomes: int = 0) -> int:
    """Máximo de tarjetas según la cantidad de material (el modelo puede generar menos).

    Cada resultado de aprendizaje asegura un mínimo de tarjetas para cubrirlo.
    """
    by_words = round(words / WORDS_PER_CARD)
    return max(MIN_CARDS, min(MAX_CARDS, max(by_words, CARDS_PER_OUTCOME * outcomes)))


def parse_outcomes(text: str) -> list[str]:
    """Un resultado de aprendizaje por línea (se ignoran viñetas y líneas vacías)."""
    items = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if line:
            items.append(line)
    return items


def split_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Divide el texto en partes por frases, sin cortar palabras."""
    words, chunks, current, size = text.split(), [], [], 0
    for w in words:
        if current and size + len(w) + 1 > max_chars and current[-1].endswith((".", "?", "!", "…")):
            chunks.append(" ".join(current))
            current, size = [], 0
        current.append(w)
        size += len(w) + 1
        if size > max_chars * 1.3:  # sin puntuación: corte forzado
            chunks.append(" ".join(current))
            current, size = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks


def split_markdown(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Divide Markdown en partes por bloques (párrafos, títulos, tablas).

    Conserva los saltos de línea; un bloque más largo que `max_chars` se divide
    con `split_text`. Se prefiere cortar antes de un título.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for block in blocks:
        pieces = split_text(block, max_chars) if len(block) > max_chars else [block]
        for piece in pieces:
            is_heading = piece.startswith("#")
            over = size + len(piece) + 2 > max_chars
            # Antes de un título se corta si la parte ya va por la mitad.
            if current and (over or (is_heading and size > max_chars / 2)):
                chunks.append("\n\n".join(current))
                current, size = [], 0
            current.append(piece)
            size += len(piece) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _key(card: Flashcard) -> str:
    return "".join(ch for ch in card.front.lower() if ch.isalnum())


class FlashcardGenerator(TracksUsage, ABC):
    model: str = ""

    @abstractmethod
    def generate_chunk(self, text: str, context: str, max_cards: int,
                       language: Optional[str], source_name: str = "",
                       outcomes: Sequence[str] = ()) -> list[Flashcard]:
        """Tarjetas para un fragmento del material."""

    def generate(
        self,
        transcript: Transcript,
        context: str = "",
        on_progress: Optional[Callable[[float], None]] = None,
        check_cancel: Optional[Callable[[], None]] = None,
        documents: Sequence[StudySource] = (),
        outcomes: str = "",
    ) -> list[Flashcard]:
        """Tarjetas a partir de la transcripción y, opcionalmente, de documentos."""
        sources = [StudySource(TRANSCRIPT_SOURCE, transcript.text), *documents]
        return self.generate_from(sources, context, outcomes, transcript.language,
                                  on_progress, check_cancel)

    def generate_from(
        self,
        sources: Sequence[StudySource],
        context: str = "",
        outcomes: str = "",
        language: Optional[str] = None,
        on_progress: Optional[Callable[[float], None]] = None,
        check_cancel: Optional[Callable[[], None]] = None,
    ) -> list[Flashcard]:
        """Tarjetas a partir de varias fuentes; el total crece con la cantidad de material."""
        goals = parse_outcomes(outcomes)
        chunks = [(s.name, c) for s in sources for c in split_markdown(s.markdown)]
        if not chunks:
            return []
        words = sum(len(c.split()) for _, c in chunks)
        total = target_cards(words, len(goals))
        chars = sum(len(c) for _, c in chunks)

        cards: list[Flashcard] = []
        seen: set[str] = set()
        for i, (name, chunk) in enumerate(chunks):
            # Reparto proporcional al tamaño de cada parte
            per_chunk = max(MIN_CARDS_PER_CHUNK, round(total * len(chunk) / chars))
            for card in self.generate_chunk(chunk, context, per_chunk, language, name, goals):
                front, back = card.front.strip(), card.back.strip()
                k = _key(card)
                if front and back and k and k not in seen:
                    seen.add(k)
                    cards.append(Flashcard(front, back))
            if on_progress:
                on_progress((i + 1) / len(chunks))
            if check_cancel:
                check_cancel()
        return cards[:total]
