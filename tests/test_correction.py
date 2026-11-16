import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.core.errors import TranscriptionError
from app.core.models import Segment, Transcript
from app.core.pipeline import TranscriptionPipeline, build_prompt
from app.correction.base import Corrector
from app.correction.openai_corrector import OpenAICorrector
from tests.helpers import FakeTranscriber, make_video


class FakeCorrector(Corrector):
    model = "corrector-de-prueba"

    def __init__(self, fn=None, fail=False):
        self.fn = fn or (lambda line: line.replace("parte", "PARTE"))
        self.fail = fail
        self.calls = []

    def correct_batch(self, lines, context):
        self.calls.append((list(lines), context))
        if self.fail:
            raise TranscriptionError("servicio caído")
        return [self.fn(line) for line in lines]


class BuildPromptTests(unittest.TestCase):
    def test_none_without_context_or_previous(self):
        self.assertIsNone(build_prompt("", None))

    def test_combines_context_and_previous(self):
        prompt = build_prompt("  Reunión sobre   Figma ", "texto anterior")
        self.assertEqual(prompt, "Reunión sobre Figma\n\ntexto anterior")

    def test_context_is_truncated(self):
        self.assertLessEqual(len(build_prompt("x" * 5000, None)), 600)


class CorrectorBaseTests(unittest.TestCase):
    def test_keeps_timestamps_and_marks_transcript(self):
        t = Transcript("Hola parte uno. Adiós parte dos.",
                       [Segment(0, 2, "Hola parte uno."), Segment(5, 7, "Adiós parte dos.")])
        out = FakeCorrector().correct(t, "ctx")
        self.assertEqual([(s.start, s.end) for s in out.segments], [(0, 2), (5, 7)])
        self.assertEqual(out.segments[1].text, "Adiós PARTE dos.")
        self.assertEqual(out.corrected_by, "corrector-de-prueba")

    def test_without_segments_splits_sentences(self):
        out = FakeCorrector().correct(Transcript("Una parte. Otra parte."), "ctx")
        self.assertEqual(out.text, "Una PARTE. Otra PARTE.")

    def test_rejects_invented_or_empty_lines(self):
        t = Transcript("a", [Segment(0, 1, "Hola."), Segment(1, 2, "Adiós.")])
        fn = lambda line: "" if line == "Hola." else line + " Y aquí una frase larga inventada por el modelo."
        out = FakeCorrector(fn=fn).correct(t, "ctx")
        self.assertEqual([s.text for s in out.segments], ["Hola.", "Adiós."])

    def test_wrong_line_count_keeps_batch(self):
        class Short(FakeCorrector):
            def correct_batch(self, lines, context):
                return lines[:-1]
        t = Transcript("a", [Segment(0, 1, "uno"), Segment(1, 2, "dos")])
        self.assertEqual([s.text for s in Short().correct(t, "c").segments], ["uno", "dos"])


class FakeChat:
    def __init__(self, content):
        self.content = content
        self.kwargs = None
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


class OpenAICorrectorTests(unittest.TestCase):
    def test_parses_json_and_sends_context(self):
        client = FakeChat(json.dumps({"lineas": {"1": "Usamos Figma.", "2": "El KPI subió."}}))
        out = OpenAICorrector("", model="m", client=client).correct_batch(
            ["Usamos figma.", "El que pe i subió."], "Diseño en Figma, KPI")
        self.assertEqual(out, ["Usamos Figma.", "El KPI subió."])
        self.assertIn("Diseño en Figma, KPI", client.kwargs["messages"][1]["content"])
        self.assertEqual(client.kwargs["model"], "m")

    def test_malformed_response_keeps_original(self):
        out = OpenAICorrector("", client=FakeChat("no es json")).correct_batch(["uno"], "c")
        self.assertEqual(out, ["uno"])


class PipelineCorrectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_context_goes_to_transcriber_and_corrector(self):
        video = make_video(self.tmp / "v.mp4", seconds=2)
        fake, corrector = FakeTranscriber(), FakeCorrector()
        pipe = TranscriptionPipeline(fake, corrector)
        out = pipe.run(video, "txt", context="Clase de biología")
        self.assertIn("Clase de biología", fake.calls[0][2])
        self.assertEqual(corrector.calls[0][1], "Clase de biología")
        content = out.read_text(encoding="utf-8")
        self.assertIn("PARTE 1", content)
        self.assertIn("Contexto: Clase de biología", content)
        self.assertEqual(pipe.warnings, [])

    def test_no_correction_without_context(self):
        video = make_video(self.tmp / "v.mp4", seconds=2)
        corrector = FakeCorrector()
        TranscriptionPipeline(FakeTranscriber(), corrector).run(video, "txt")
        self.assertEqual(corrector.calls, [])

    def test_correction_failure_saves_uncorrected_with_warning(self):
        video = make_video(self.tmp / "v.mp4", seconds=2)
        pipe = TranscriptionPipeline(FakeTranscriber(), FakeCorrector(fail=True))
        out = pipe.run(video, "txt", context="tema")
        self.assertIn("parte 1", out.read_text(encoding="utf-8"))
        self.assertEqual(len(pipe.warnings), 1)


if __name__ == "__main__":
    unittest.main()
