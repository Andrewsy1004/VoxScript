"""Uso por línea de comandos (útil para pruebas y automatización).

    python -m app.cli video.mov --formato txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import SettingsStore, load_env
from app.core.errors import TranscriptorError
from app.core.models import ExportOptions
from app.core.pipeline import TranscriptionPipeline
from app.correction import create_corrector
from app.flashcards import create_flashcard_generator
from app.exporters import EXPORTERS
from app.transcription import create_transcriber


def main(argv: list[str] | None = None) -> int:
    load_env()
    settings = SettingsStore().load()
    parser = argparse.ArgumentParser(description="Transcribe un video a TXT o Word.")
    parser.add_argument("archivo", type=Path, nargs="?",
                        help="video o audio (opcional si se pasan documentos)")
    parser.add_argument("--formato", choices=sorted(EXPORTERS), default=settings.output_format)
    parser.add_argument("--salida", type=Path, help="carpeta de destino (por defecto, la del video)")
    parser.add_argument("--idioma", default=settings.language,
                        help="código ISO (es, en…); vacío para detectar automáticamente")
    parser.add_argument("--sin-tiempos", action="store_true", help="no incluir marcas de tiempo")
    parser.add_argument("--api-key", help="API key de OpenAI (si no está en la configuración)")
    parser.add_argument("--modelo", default=settings.model)
    parser.add_argument("--contexto", default="",
                        help="de qué trata el audio: nombres, siglas, términos (mejora la precisión)")
    parser.add_argument("--revisar", action="store_true",
                        help="revisar el texto con IA usando el contexto (costo extra)")
    parser.add_argument("--flashcards", action="store_true",
                        help="crear también flashcards para Anki (costo extra)")
    parser.add_argument("--documento", type=Path, action="append", default=[],
                        help="PDF, Word (.docx), .md o .txt para las flashcards (se puede repetir; "
                             "activa --flashcards)")
    parser.add_argument("--resultados", default="",
                        help="resultados de aprendizaje para las flashcards (uno por línea)")
    args = parser.parse_args(argv)
    if args.archivo is None and not args.documento:
        parser.error("indica un video o al menos un --documento")

    if args.api_key:
        settings.api_key = args.api_key
    settings.model = args.modelo
    settings.correct_with_context = args.revisar
    settings.make_flashcards = args.flashcards or bool(args.documento)

    def show(pct: float, msg: str) -> None:
        print(f"[{pct:5.1f}%] {msg}", file=sys.stderr)

    try:
        cards = create_flashcard_generator(settings)
        if args.archivo is None:
            pipeline = TranscriptionPipeline(None, flashcards=cards, prices=settings.prices())
            out = pipeline.run_flashcards(args.documento, args.salida, args.idioma, show,
                                          context=args.contexto,
                                          learning_outcomes=args.resultados)
        else:
            pipeline = TranscriptionPipeline(create_transcriber(settings),
                                             create_corrector(settings), cards, settings.prices())
            out = pipeline.run(args.archivo, args.formato, args.salida, args.idioma,
                               ExportOptions(include_timestamps=not args.sin_tiempos), show,
                               context=args.contexto, documents=args.documento,
                               learning_outcomes=args.resultados)
    except TranscriptorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for warning in pipeline.warnings:
        print(f"Aviso: {warning}", file=sys.stderr)
    print(pipeline.cost.as_text(), file=sys.stderr)
    print(out)
    if pipeline.flashcards_path and pipeline.flashcards_path != out:
        print(pipeline.flashcards_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
