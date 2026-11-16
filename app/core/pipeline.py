"""Orquesta el proceso completo: video → audio → partes → texto → archivo.

No depende de la interfaz: lo usan igual la ventana (ui) y la línea de comandos (cli).
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional, Sequence

from app import media
from app.core.costs import (CostLine, CostReport, Prices, TokenUsage, format_minutes,
                            format_tokens)
from app.core.errors import (CancelledError, ConfigError, DocumentError, MediaError,
                             TranscriptorError)
from app.core.models import ExportOptions, Segment, Transcript
from app.correction.base import Corrector
from app.documents import StudySource, to_markdown
from app.exporters import get_exporter
from app.flashcards.anki import export_anki
from app.flashcards.base import TRANSCRIPT_SOURCE, FlashcardGenerator
from app.transcription.base import Transcriber

log = logging.getLogger(__name__)

#: callback(porcentaje 0–100, mensaje para el usuario)
ProgressCallback = Callable[[float, str], None]

PROMPT_CONTEXT_CHARS = 200  # texto de la parte anterior que se pasa como contexto
USER_CONTEXT_CHARS = 600    # contexto del usuario que cabe en el prompt de transcripción


def build_prompt(context: str, previous_text: Optional[str]) -> Optional[str]:
    """Prompt para el motor: el contexto del tema y el final de la parte anterior.

    El motor usa el prompt como pista de vocabulario (nombres, siglas, términos).
    """
    parts = []
    context = " ".join(context.split())
    if context:
        parts.append(context[:USER_CONTEXT_CHARS])
    if previous_text:
        parts.append(previous_text[-PROMPT_CONTEXT_CHARS:])
    return "\n\n".join(parts) or None


def build_output_path(source: Path, output_dir: Optional[Path], extension: str,
                      suffix: str = "_transcripcion") -> Path:
    """`video_transcripcion.docx`, sin sobrescribir archivos existentes."""
    folder = output_dir or source.parent
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / f"{source.stem}{suffix}{extension}"
    n = 2
    while candidate.exists():
        candidate = folder / f"{source.stem}{suffix} ({n}){extension}"
        n += 1
    return candidate


class TranscriptionPipeline:
    def __init__(self, transcriber: Optional[Transcriber], corrector: Optional[Corrector] = None,
                 flashcards: Optional[FlashcardGenerator] = None,
                 prices: Prices = Prices()) -> None:
        self.transcriber = transcriber
        self.corrector = corrector
        self.flashcards = flashcards
        self.prices = prices
        #: costo estimado de la última ejecución, desglosado por paso
        self.cost = CostReport()
        #: avisos no fatales de la última ejecución (p. ej., la corrección falló)
        self.warnings: list[str] = []
        #: archivo de flashcards de la última ejecución y cuántas tarjetas tiene
        self.flashcards_path: Optional[Path] = None
        self.flashcards_count = 0

    def run(
        self,
        source: Path,
        output_format: str,
        output_dir: Optional[Path] = None,
        language: Optional[str] = "es",
        options: ExportOptions = ExportOptions(),
        on_progress: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
        context: str = "",
        documents: Sequence[Path] = (),
        learning_outcomes: str = "",
        flashcards_from_video: bool = True,
    ) -> Path:
        progress = on_progress or (lambda pct, msg: None)
        self._reset()
        context = context.strip()
        correct = self.corrector is not None and bool(context)
        cards = self.flashcards is not None
        # Reparto de la barra: transcripción, revisión (15 %) y flashcards (12 %) hasta el 95 %
        correct_end = 95 - (12 if cards else 0)
        transcribe_end = correct_end - (15 if correct else 0)
        exporter = get_exporter(output_format)  # falla antes de gastar en la API

        def check_cancel() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("Proceso cancelado.")

        source = Path(source)
        if source.suffix.lower() not in media.SUPPORTED_EXTENSIONS:
            raise MediaError(f"Formato no compatible: '{source.suffix or 'sin extensión'}'.")

        progress(2, "Leyendo el archivo…")
        info = media.probe(source)
        if not info.has_audio:
            raise MediaError(f"'{source.name}' no tiene pista de audio.")
        check_cancel()

        # Los documentos se leen antes de transcribir: un error aquí no cuesta nada.
        docs = self._load_documents(documents, progress, 2, 3, check_cancel) if cards else []

        work_dir = Path(tempfile.mkdtemp(prefix="transcriptor_"))
        try:
            progress(5, "Extrayendo el audio…")
            audio = media.extract_audio(source, work_dir / "audio.mp3")
            check_cancel()

            progress(20, "Preparando el audio…")
            chunks = media.split_audio(audio, info.duration, self.transcriber.max_file_bytes,
                                       work_dir / "partes")
            check_cancel()

            texts: list[str] = []
            segments: list[Segment] = []
            span = (transcribe_end - 25) / len(chunks)
            minutes = 0.0
            for i, chunk in enumerate(chunks):
                label = f" (parte {i + 1} de {len(chunks)})" if len(chunks) > 1 else ""
                progress(25 + span * i, f"Transcribiendo{label}… puede tardar unos minutos")
                prompt = build_prompt(context, texts[-1] if texts else None)
                result = self.transcriber.transcribe(chunk.path, language or None, prompt)
                minutes += (chunk.duration or (info.duration or 0) / len(chunks)) / 60
                if result.text:
                    texts.append(result.text)
                segments += [Segment(s.start + chunk.offset, s.end + chunk.offset, s.text)
                             for s in result.segments]
                check_cancel()

            self.cost.lines.append(CostLine("Transcripción", format_minutes(minutes),
                                            self.prices.transcription(minutes)))
            if not texts:
                raise MediaError("No se detectó voz en el audio.")

            transcript = Transcript(
                text=" ".join(texts),
                segments=segments,
                source_name=source.name,
                duration=info.duration,
                language=language or None,
                model=self.transcriber.model,
                context=context,
            )

            if correct:
                progress(transcribe_end, "Corrigiendo con el contexto…")
                before = self.corrector.usage.copy()
                try:
                    transcript = self.corrector.correct(
                        transcript, context,
                        on_progress=lambda f: progress(transcribe_end + 15 * f,
                                                       "Corrigiendo con el contexto…"),
                        check_cancel=check_cancel)
                except CancelledError:
                    raise
                except TranscriptorError as exc:
                    # Lo ya transcrito está pagado: se guarda sin corregir en vez de perderlo.
                    log.warning("Falló la corrección con contexto: %s", exc)
                    self.warnings.append(
                        f"No se pudo corregir con el contexto: {exc}\n"
                        "Se guardó la transcripción sin corregir.")
                finally:
                    self._add_chat_cost("Revisión con IA", self.corrector.usage.since(before))

            progress(correct_end, "Guardando el archivo…")
            out_path = build_output_path(source, output_dir, exporter.extension)
            exporter.export(transcript, out_path, options)

            if cards:
                # La transcripción ya está guardada: si esto falla, solo se avisa.
                video = [StudySource(TRANSCRIPT_SOURCE, transcript.text)] \
                    if flashcards_from_video else []
                sources = [*video, *docs]
                try:
                    if not sources:
                        raise DocumentError("no hay material: se excluyó el video y no hay "
                                            "documentos legibles.")
                    self._make_flashcards(sources, source, output_dir, context,
                                          learning_outcomes, transcript.language,
                                          progress, correct_end, 12, check_cancel)
                except CancelledError:
                    raise
                except TranscriptorError as exc:
                    log.warning("Fallaron las flashcards: %s", exc)
                    self.warnings.append(
                        f"No se pudieron crear las flashcards: {exc}\n"
                        "La transcripción sí se guardó.")

            progress(100, "Listo")
            return out_path
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def run_flashcards(
        self,
        documents: Sequence[Path],
        output_dir: Optional[Path] = None,
        language: Optional[str] = "es",
        on_progress: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
        context: str = "",
        learning_outcomes: str = "",
    ) -> Path:
        """Solo flashcards a partir de documentos, sin video. Devuelve el CSV para Anki."""
        progress = on_progress or (lambda pct, msg: None)
        self._reset()
        if self.flashcards is None:
            raise ConfigError("Activa «Crear flashcards» para usar documentos.")
        documents = [Path(d) for d in documents]
        if not documents:
            raise DocumentError("Agrega al menos un documento.")

        def check_cancel() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("Proceso cancelado.")

        docs = self._load_documents(documents, progress, 2, 15, check_cancel)
        if not docs:
            raise DocumentError("No se pudo leer ningún documento.\n\n" + "\n".join(self.warnings))
        self._make_flashcards(docs, documents[0], output_dir, context.strip(),
                              learning_outcomes, language or None, progress, 15, 80,
                              check_cancel)
        if self.flashcards_path is None:
            raise DocumentError("El contenido de los documentos no dio para crear flashcards.")
        progress(100, "Listo")
        return self.flashcards_path

    def _reset(self) -> None:
        self.warnings = []
        self.flashcards_path, self.flashcards_count = None, 0
        self.cost = CostReport()

    def _load_documents(self, documents: Sequence[Path], progress: ProgressCallback,
                        start: float, span: float,
                        check_cancel: Callable[[], None]) -> list[StudySource]:
        """Convierte los documentos a Markdown. Los que fallan se avisan y se omiten."""
        docs: list[StudySource] = []
        for i, path in enumerate(documents):
            path = Path(path)
            progress(start + span * i / len(documents), f"Leyendo «{path.name}»…")
            try:
                docs.append(to_markdown(path))
            except DocumentError as exc:
                log.warning("No se pudo leer el documento %s: %s", path, exc)
                self.warnings.append(f"Se omitió un documento: {exc}")
            check_cancel()
        return docs

    def _make_flashcards(self, sources: Sequence[StudySource], name_from: Path,
                         output_dir: Optional[Path], context: str, learning_outcomes: str,
                         language: Optional[str], progress: ProgressCallback, start: float,
                         span: float, check_cancel: Callable[[], None]) -> None:
        msg = "Creando flashcards para Anki…"
        progress(start, msg)
        before = self.flashcards.usage.copy()
        try:
            deck = self.flashcards.generate_from(
                sources, context, learning_outcomes, language,
                on_progress=lambda f: progress(start + span * f, msg),
                check_cancel=check_cancel)
        finally:
            self._add_chat_cost("Flashcards", self.flashcards.usage.since(before))
        if deck:
            path = build_output_path(name_from, output_dir, ".csv", "_flashcards_anki")
            self.flashcards_path = export_anki(deck, path)
            self.flashcards_count = len(deck)
        else:
            self.warnings.append("El contenido no dio para crear flashcards.")

    def _add_chat_cost(self, label: str, usage: TokenUsage) -> None:
        if usage.total:
            self.cost.lines.append(CostLine(label, format_tokens(usage), self.prices.chat(usage)))
