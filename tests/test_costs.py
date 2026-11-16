import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings, SettingsStore
from app.core.costs import CostLine, CostReport, Prices, TokenUsage, format_usd
from app.core.pipeline import TranscriptionPipeline
from app.correction.base import Corrector
from app.correction.openai_corrector import OpenAICorrector
from app.flashcards.base import Flashcard, FlashcardGenerator
from tests.helpers import FakeTranscriber, make_video

PRICES = Prices(transcription_per_minute=0.006, chat_input_per_million=1.0,
                chat_output_per_million=10.0)


class UsageCorrector(Corrector):
    model = "c"

    def correct_batch(self, lines, context):
        self.usage.add({"prompt_tokens": 1000, "completion_tokens": 200})
        return lines


class UsageCards(FlashcardGenerator):
    model = "f"

    def generate_chunk(self, text, context, max_cards, language, source_name="", outcomes=()):
        self.usage.add(SimpleNamespace(prompt_tokens=3000, completion_tokens=500))
        return [Flashcard("¿P?", "R")]


class CostUnitTests(unittest.TestCase):
    def test_prices(self):
        self.assertAlmostEqual(PRICES.transcription(10), 0.06)
        self.assertAlmostEqual(PRICES.chat(TokenUsage(1_000_000, 100_000)), 2.0)

    def test_usage_delta(self):
        u = TokenUsage()
        u.add({"prompt_tokens": 5, "completion_tokens": 1})
        before = u.copy()
        u.add({"prompt_tokens": 10, "completion_tokens": 2})
        self.assertEqual(u.since(before), TokenUsage(10, 2))
        u.add(None)  # respuestas sin usage no fallan
        self.assertEqual(u.total, 18)

    def test_report_total_and_format(self):
        r = CostReport([CostLine("A", "x", 0.01), CostLine("B", "y", 0.0025)])
        self.assertAlmostEqual(r.total, 0.0125)
        self.assertIn("Total: $0.0125", r.as_text())
        self.assertEqual(format_usd(12.3), "$12.30")

    def test_openai_corrector_counts_tokens(self):
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"lineas": {"1": "a"}})))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **k: resp)))
        c = OpenAICorrector("", client=client)
        c.correct_batch(["a"], "ctx")
        self.assertEqual(c.usage, TokenUsage(120, 30))

    def test_settings_prices_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "c.json")
            s = Settings(price_transcription_per_minute=0.01, total_spent=1.5)
            store.save(s)
            loaded = store.load()
        self.assertEqual(loaded.prices().transcription_per_minute, 0.01)
        self.assertEqual(loaded.total_spent, 1.5)


class PipelineCostTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_breakdown_per_step(self):
        video = make_video(self.tmp / "v.mp4", seconds=6)
        pipe = TranscriptionPipeline(FakeTranscriber(), UsageCorrector(), UsageCards(), PRICES)
        pipe.run(video, "txt", context="tema")
        labels = [l.label for l in pipe.cost.lines]
        self.assertEqual(labels, ["Transcripción", "Revisión con IA", "Flashcards"])
        trans, review, cards = pipe.cost.lines
        self.assertAlmostEqual(trans.amount, 0.006 * 6 / 60, places=4)
        self.assertAlmostEqual(review.amount, (1000 * 1 + 200 * 10) / 1e6)
        self.assertAlmostEqual(cards.amount, (3000 * 1 + 500 * 10) / 1e6)
        self.assertAlmostEqual(pipe.cost.total, sum(l.amount for l in pipe.cost.lines))

    def test_only_transcription_when_no_extras(self):
        video = make_video(self.tmp / "v.mp4", seconds=2)
        pipe = TranscriptionPipeline(FakeTranscriber(), prices=PRICES)
        pipe.run(video, "txt")
        self.assertEqual([l.label for l in pipe.cost.lines], ["Transcripción"])


if __name__ == "__main__":
    unittest.main()
