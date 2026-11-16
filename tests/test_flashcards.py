import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.core.errors import DocumentError, TranscriptionError
from app.core.models import Transcript
from app.core.pipeline import TranscriptionPipeline
from app.documents import StudySource
from app.flashcards.anki import export_anki
from app.flashcards.base import (Flashcard, FlashcardGenerator, parse_outcomes, split_markdown,
                                 split_text, target_cards)
from app.flashcards.openai_flashcards import OpenAIFlashcardGenerator
from tests.helpers import FakeTranscriber, make_video


class FakeGenerator(FlashcardGenerator):
    model = "tarjetas-de-prueba"

    def __init__(self, cards=None, fail=False):
        self.cards = cards if cards is not None else [
            Flashcard("¿Qué es la fotosíntesis?", "Proceso que convierte luz en energía química."),
            Flashcard("¿Qué es la FOTOSÍNTESIS?", "Duplicada: debe descartarse."),
            Flashcard("", "Sin pregunta: se descarta."),
        ]
        self.fail = fail
        self.calls = []
        self.sources, self.outcomes = [], []

    def generate_chunk(self, text, context, max_cards, language, source_name="", outcomes=()):
        self.calls.append((text, context, max_cards))
        self.sources.append(source_name)
        self.outcomes.append(list(outcomes))
        if self.fail:
            raise TranscriptionError("servicio caído")
        return self.cards


class BaseTests(unittest.TestCase):
    def test_target_cards_scales_with_words(self):
        self.assertEqual(target_cards(0), 5)              # mínimo
        self.assertEqual(target_cards(5000), 20)
        self.assertEqual(target_cards(10000), 40)         # más material, más tarjetas
        self.assertEqual(target_cards(1_000_000), 80)     # máximo

    def test_target_cards_floor_per_outcome(self):
        self.assertEqual(target_cards(250, outcomes=6), 12)
        self.assertEqual(target_cards(250, outcomes=100), 80)

    def test_parse_outcomes(self):
        self.assertEqual(parse_outcomes("- Uno\n\n2) Dos\n• Tres\n  Cuatro  "),
                         ["Uno", "Dos", "Tres", "Cuatro"])

    def test_split_markdown_keeps_structure_and_words(self):
        md = "\n\n".join(f"## Tema {i}\n\n" + "Frase de relleno. " * 60 for i in range(20))
        chunks = split_markdown(md, max_chars=2000)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks).split(), md.split())
        self.assertTrue(all(c.startswith("## Tema") for c in chunks))

    def test_cards_split_proportionally(self):
        gen = FakeGenerator(cards=[])
        big = StudySource("grande.pdf", "Palabra. " * 9000)
        small = StudySource("chico.docx", "Palabra. " * 1000)
        gen.generate_from([big, small])
        per_source = {}
        for name, (_, _, n) in zip(gen.sources, gen.calls):
            per_source[name] = per_source.get(name, 0) + n
        self.assertGreater(per_source["grande.pdf"], 5 * per_source["chico.docx"])

    def test_outcomes_reach_generator(self):
        gen = FakeGenerator()
        gen.generate_from([StudySource("a.md", "Texto.")], outcomes="Explicar X\nComparar Y")
        self.assertEqual(gen.outcomes[0], ["Explicar X", "Comparar Y"])
        self.assertEqual(gen.sources[0], "a.md")

    def test_split_text_keeps_all_words(self):
        text = " ".join(f"Frase número {i}." for i in range(3000))
        chunks = split_text(text, max_chars=2000)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks).split(), text.split())

    def test_dedupes_and_drops_empty(self):
        cards = FakeGenerator().generate(Transcript("Texto corto."), "ctx")
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].front, "¿Qué es la fotosíntesis?")


class AnkiExportTests(unittest.TestCase):
    def test_file_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = export_anki([Flashcard("¿Pre\tgunta?", "Resp\nuesta, con coma")],
                               Path(tmp) / "f.csv")
            raw = path.read_bytes()
            lines = raw.decode("utf-8-sig").splitlines()
        # BOM para que Excel lea UTF-8 (acentos, ñ)
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        # Sin metadatos: solo la fila de la tarjeta
        self.assertEqual(lines, ['¿Pre gunta?,"Resp uesta, con coma"'])


class FakeChat:
    def __init__(self, content):
        self.content = content
        self.kwargs = None
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


class OpenAIGeneratorTests(unittest.TestCase):
    def test_parses_cards(self):
        client = FakeChat(json.dumps({"tarjetas": [{"pregunta": "¿Q?", "respuesta": "R"}]}))
        cards = OpenAIFlashcardGenerator("", model="m", client=client).generate_chunk(
            "texto", "Biología", 5, "es")
        self.assertEqual(cards, [Flashcard("¿Q?", "R")])
        user = client.kwargs["messages"][1]["content"]
        self.assertIn("como máximo 5", user)
        self.assertIn("Biología", user)

    def test_prompt_includes_outcomes_and_source(self):
        client = FakeChat(json.dumps({"tarjetas": []}))
        OpenAIFlashcardGenerator("", client=client).generate_chunk(
            "texto", "", 5, "es", "apuntes.pdf", ["Explicar la fotosíntesis"])
        user = client.kwargs["messages"][1]["content"]
        self.assertIn("Resultados de aprendizaje", user)
        self.assertIn("- Explicar la fotosíntesis", user)
        self.assertIn("Fuente: apuntes.pdf", user)

    def test_malformed_response(self):
        gen = OpenAIFlashcardGenerator("", client=FakeChat("nada"))
        self.assertEqual(gen.generate_chunk("t", "", 5, None), [])


class PipelineFlashcardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_creates_anki_file_next_to_transcript(self):
        video = make_video(self.tmp / "clase.mp4", seconds=2)
        progress = []
        pipe = TranscriptionPipeline(FakeTranscriber(), flashcards=FakeGenerator())
        out = pipe.run(video, "txt", context="Biología",
                       on_progress=lambda p, m: progress.append(p))
        self.assertEqual(pipe.flashcards_path.name, "clase_flashcards_anki.csv")
        self.assertEqual(pipe.flashcards_path.parent, out.parent)
        self.assertEqual(pipe.flashcards_count, 1)
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[-1], 100)

    def test_failure_keeps_transcript_and_warns(self):
        video = make_video(self.tmp / "v.mp4", seconds=2)
        pipe = TranscriptionPipeline(FakeTranscriber(), flashcards=FakeGenerator(fail=True))
        out = pipe.run(video, "txt")
        self.assertTrue(out.exists())
        self.assertIsNone(pipe.flashcards_path)
        self.assertEqual(len(pipe.warnings), 1)

    def test_video_plus_documents_sends_both_sources(self):
        video = make_video(self.tmp / "clase.mp4", seconds=2)
        doc = self.tmp / "apuntes.md"
        doc.write_text("# Fotosíntesis\n\nConvierte luz en energía.", encoding="utf-8")
        gen = FakeGenerator()
        pipe = TranscriptionPipeline(FakeTranscriber(), flashcards=gen)
        pipe.run(video, "txt", documents=[doc], learning_outcomes="Explicar la fotosíntesis")
        self.assertEqual(gen.sources, ["Transcripción del video", "apuntes.md"])
        self.assertEqual(gen.outcomes[0], ["Explicar la fotosíntesis"])

    def test_video_excluded_uses_only_documents(self):
        video = make_video(self.tmp / "clase.mp4", seconds=2)
        doc = self.tmp / "apuntes.md"
        doc.write_text("Contenido de estudio.", encoding="utf-8")
        gen = FakeGenerator()
        pipe = TranscriptionPipeline(FakeTranscriber(), flashcards=gen)
        out = pipe.run(video, "txt", documents=[doc], flashcards_from_video=False)
        self.assertTrue(out.exists())  # la transcripción se guarda igual
        self.assertEqual(gen.sources, ["apuntes.md"])
        self.assertEqual(pipe.flashcards_path.name, "clase_flashcards_anki.csv")

    def test_video_excluded_without_documents_warns(self):
        video = make_video(self.tmp / "clase.mp4", seconds=2)
        gen = FakeGenerator()
        pipe = TranscriptionPipeline(FakeTranscriber(), flashcards=gen)
        out = pipe.run(video, "txt", flashcards_from_video=False)
        self.assertTrue(out.exists())
        self.assertEqual(gen.calls, [])
        self.assertIsNone(pipe.flashcards_path)
        self.assertIn("no hay material", pipe.warnings[0])

    def test_documents_only(self):
        doc = self.tmp / "apuntes.md"
        doc.write_text("# Tema\n\nContenido de estudio.", encoding="utf-8")
        progress = []
        pipe = TranscriptionPipeline(None, flashcards=FakeGenerator())
        out = pipe.run_flashcards([doc], on_progress=lambda p, m: progress.append(p))
        self.assertEqual(out.name, "apuntes_flashcards_anki.csv")
        self.assertTrue(out.exists())
        self.assertEqual(pipe.flashcards_count, 1)
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[-1], 100)

    def test_broken_document_warns_and_continues(self):
        good = self.tmp / "bien.txt"
        good.write_text("Contenido útil.", encoding="utf-8")
        bad = self.tmp / "viejo.doc"
        bad.write_bytes(b"x")
        pipe = TranscriptionPipeline(None, flashcards=FakeGenerator())
        out = pipe.run_flashcards([bad, good])
        self.assertTrue(out.exists())
        self.assertEqual(len(pipe.warnings), 1)
        self.assertIn("viejo.doc", pipe.warnings[0])

    def test_all_documents_broken_raises(self):
        bad = self.tmp / "viejo.doc"
        bad.write_bytes(b"x")
        pipe = TranscriptionPipeline(None, flashcards=FakeGenerator())
        with self.assertRaises(DocumentError):
            pipe.run_flashcards([bad])

    def test_no_cards_warns(self):
        video = make_video(self.tmp / "v.mp4", seconds=2)
        pipe = TranscriptionPipeline(FakeTranscriber(), flashcards=FakeGenerator(cards=[]))
        pipe.run(video, "txt")
        self.assertIsNone(pipe.flashcards_path)
        self.assertIn("flashcards", pipe.warnings[0])


if __name__ == "__main__":
    unittest.main()
