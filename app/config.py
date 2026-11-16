"""Configuración persistente del usuario (API key, modelo, preferencias).

Se guarda como JSON en la carpeta de configuración estándar de cada sistema:
  Windows: %APPDATA%\\Transcriptor\\config.json
  macOS:   ~/Library/Application Support/Transcriptor/config.json
  Linux:   ~/.config/Transcriptor/config.json
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Callable, Optional

from app import APP_NAME
from app.core.costs import (DEFAULT_CHAT_INPUT_PER_MILLION, DEFAULT_CHAT_OUTPUT_PER_MILLION,
                            DEFAULT_TRANSCRIPTION_PER_MINUTE, Prices)

DEFAULT_MODEL = "gpt-transcribe"
DEFAULT_CORRECTION_MODEL = "gpt-5.4-mini"

# (etiqueta visible, código ISO-639-1). Código vacío = detección automática.
LANGUAGES: list[tuple[str, str]] = [
    ("Español", "es"),
    ("Inglés", "en"),
    ("Portugués", "pt"),
    ("Francés", "fr"),
    ("Detectar automáticamente", ""),
]


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME


def app_base_dir() -> Path:
    """Carpeta del ejecutable (si está empaquetado) o raíz del proyecto."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def load_env(candidates: Optional[list[Path]] = None) -> Optional[Path]:
    """Carga el primer .env encontrado (directorio actual, luego carpeta de la app).

    Las variables de entorno reales tienen prioridad sobre el .env.
    Devuelve la ruta cargada, o None si no hay ningún .env.
    """
    from dotenv import load_dotenv

    if candidates is None:
        candidates = [Path.cwd() / ".env", app_base_dir() / ".env"]
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            return path
    return None


def _env_default(name: str, fallback: str) -> Callable[[], str]:
    return lambda: os.environ.get(name, "").strip() or fallback


@dataclass
class Settings:
    provider: str = "openai"
    api_key: str = ""
    model: str = field(default_factory=_env_default("TRANSCRIPTOR_MODEL", DEFAULT_MODEL))
    language: str = field(default_factory=_env_default("TRANSCRIPTOR_LANGUAGE", "es"))
    output_format: str = field(default_factory=_env_default("TRANSCRIPTOR_OUTPUT_FORMAT", "docx"))
    include_timestamps: bool = True
    # vacío = misma carpeta que el video
    output_dir: str = field(default_factory=_env_default("TRANSCRIPTOR_OUTPUT_DIR", ""))
    context: str = ""                  # último contexto escrito (se recuerda entre usos)
    correct_with_context: bool = False  # revisar el texto con IA usando el contexto
    make_flashcards: bool = False       # generar flashcards para Anki
    learning_outcomes: str = ""         # resultados de aprendizaje para las flashcards
    flashcards_include_video: bool = True  # usar la transcripción como material de las flashcards
    # Modelo de chat para la revisión y las flashcards
    correction_model: str = field(
        default_factory=_env_default("TRANSCRIPTOR_CORRECTION_MODEL", DEFAULT_CORRECTION_MODEL))

    # Precios en USD para estimar el costo (editables en Configuración)
    price_transcription_per_minute: float = DEFAULT_TRANSCRIPTION_PER_MINUTE
    price_chat_input_per_million: float = DEFAULT_CHAT_INPUT_PER_MILLION
    price_chat_output_per_million: float = DEFAULT_CHAT_OUTPUT_PER_MILLION
    total_spent: float = 0.0  # costo estimado acumulado en este equipo

    def prices(self) -> Prices:
        return Prices(float(self.price_transcription_per_minute),
                      float(self.price_chat_input_per_million),
                      float(self.price_chat_output_per_million))

    def effective_api_key(self) -> str:
        """La key guardada tiene prioridad; si no hay, se usa OPENAI_API_KEY."""
        return self.api_key.strip() or os.environ.get("OPENAI_API_KEY", "").strip()


class SettingsStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or (config_dir() / "config.json")

    def load(self) -> Settings:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Settings()  # primera ejecución o archivo dañado
        known = {f.name for f in fields(Settings)}
        return Settings(**{k: v for k, v in raw.items() if k in known})

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
        if os.name == "posix":
            os.chmod(tmp, 0o600)  # la API key solo la lee el propio usuario
        os.replace(tmp, self.path)
