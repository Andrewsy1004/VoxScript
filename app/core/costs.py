"""Cálculo del costo estimado de cada transcripción.

Los precios son configurables (Configuración): OpenAI los cambia con el tiempo y
la app no puede consultarlos por API. El resultado es una estimación; el cobro
real está en platform.openai.com/usage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Valores por defecto (USD). Referencia de comparadores de terceros, nov. 2026:
# verifícalos en https://openai.com/api/pricing
DEFAULT_TRANSCRIPTION_PER_MINUTE = 0.0045   # gpt-transcribe
DEFAULT_CHAT_INPUT_PER_MILLION = 0.75       # gpt-5.4-mini, entrada
DEFAULT_CHAT_OUTPUT_PER_MILLION = 4.50      # gpt-5.4-mini, salida


@dataclass
class TokenUsage:
    input: int = 0
    output: int = 0

    def add(self, usage: Any) -> None:
        """Suma el `usage` de una respuesta de la API (objeto del SDK o dict)."""
        if usage is None:
            return
        get = usage.get if isinstance(usage, dict) else (lambda k, d=0: getattr(usage, k, d))
        self.input += int(get("prompt_tokens", 0) or 0)
        self.output += int(get("completion_tokens", 0) or 0)

    def since(self, before: "TokenUsage") -> "TokenUsage":
        return TokenUsage(self.input - before.input, self.output - before.output)

    def copy(self) -> "TokenUsage":
        return TokenUsage(self.input, self.output)

    @property
    def total(self) -> int:
        return self.input + self.output


class TracksUsage:
    """Mezcla para motores de chat: acumula los tokens consumidos."""

    @property
    def usage(self) -> TokenUsage:
        if not hasattr(self, "_usage"):
            self._usage = TokenUsage()
        return self._usage


@dataclass(frozen=True)
class Prices:
    transcription_per_minute: float = DEFAULT_TRANSCRIPTION_PER_MINUTE
    chat_input_per_million: float = DEFAULT_CHAT_INPUT_PER_MILLION
    chat_output_per_million: float = DEFAULT_CHAT_OUTPUT_PER_MILLION

    def transcription(self, minutes: float) -> float:
        return minutes * self.transcription_per_minute

    def chat(self, usage: TokenUsage) -> float:
        return (usage.input * self.chat_input_per_million
                + usage.output * self.chat_output_per_million) / 1_000_000


@dataclass(frozen=True)
class CostLine:
    label: str
    detail: str
    amount: float


@dataclass
class CostReport:
    lines: list[CostLine] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(line.amount for line in self.lines)

    def as_text(self) -> str:
        rows = [f"  {l.label} ({l.detail}): {format_usd(l.amount)}" for l in self.lines]
        return "\n".join(["Costo estimado:", *rows, f"  Total: {format_usd(self.total)}"])


def format_usd(amount: float) -> str:
    """Más decimales para montos pequeños, que son lo normal aquí."""
    if amount < 1:
        return f"${amount:.4f}"
    return f"${amount:,.2f}"


def format_minutes(minutes: float) -> str:
    return f"{minutes:.1f} min"


def format_tokens(usage: TokenUsage) -> str:
    return f"{usage.total:,} tokens".replace(",", ".")
