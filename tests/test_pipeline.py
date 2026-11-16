import tempfile
import threading
import unittest
from pathlib import Path

from docx import Document

from app.core.chunk_cache import ChunkCache
from app.core.errors import CancelledError, MediaError, TranscriptionError
from app.core.models import Segment
from app.core.pipeline import TranscriptionPipeline, build_output_path
from app.transcription.base import ChunkTranscription
from tests.helpers import FakeTranscriber, make_video


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_end_to_end_docx(self):
        video = make_video(self.tmp / "clase.mov", seconds=4)
        progress = []
        out = TranscriptionPipeline(FakeTranscriber()).run(
            video, "docx", on_progress=lambda p, m: progress.append(p))
        self.assertEqual(out.name, "clase_transcripcion.docx")
        self.assertIn("parte 1", "\n".join(p.text for p in Document(str(out)).paragraphs))
        self.assertEqual(progress[-1], 100)
        self.assertEqual(progress, sorted(progress))

    def test_long_video_is_split_and_offsets_applied(self):
        video = make_video(self.tmp / "larga.mp4", seconds=60)
        fake = FakeTranscriber(max_file_bytes=60_000)  # fuerza varias partes
        out = TranscriptionPipeline(fake).run(video, "txt", language="es")
        self.assertGreater(len(fake.calls), 1)
        self.assertIsNone(fake.calls[0][2])            # la primera parte va sin contexto
        self.assertIn("parte 1", fake.calls[1][2])     # la segunda recibe el final de la primera
        content = out.read_text(encoding="utf-8")
        self.assertIn("[00:00:00]", content)
        self.assertNotIn("[00:00:00] Hola, esta es la parte 2", content)  # la parte 2 tiene offset

    def test_does_not_overwrite(self):
        video = make_video(self.tmp / "v.mp4", seconds=2)
        first = TranscriptionPipeline(FakeTranscriber()).run(video, "txt")
        second = TranscriptionPipeline(FakeTranscriber()).run(video, "txt")
        self.assertNotEqual(first, second)
        self.assertEqual(second.name, "v_transcripcion (2).txt")

    def test_rejects_video_without_audio(self):
        video = make_video(self.tmp / "mudo.mp4", audio=False)
        with self.assertRaises(MediaError):
            TranscriptionPipeline(FakeTranscriber()).run(video, "txt")

    def test_rejects_unsupported_extension(self):
        f = self.tmp / "doc.pdf"
        f.write_bytes(b"%PDF")
        with self.assertRaises(MediaError):
            TranscriptionPipeline(FakeTranscriber()).run(f, "txt")

    def test_cancel(self):
        video = make_video(self.tmp / "c.mp4", seconds=2)
        ev = threading.Event()
        ev.set()
        with self.assertRaises(CancelledError):
            TranscriptionPipeline(FakeTranscriber()).run(video, "txt", cancel_event=ev)

    def test_output_dir(self):
        video = make_video(self.tmp / "o.mp4", seconds=2)
        out = TranscriptionPipeline(FakeTranscriber()).run(video, "txt", output_dir=self.tmp / "salidas")
        self.assertEqual(out.parent, self.tmp / "salidas")


class FailingTranscriber(FakeTranscriber):
    """Falla en la llamada número `fail_at` (1 = primera), como si se cayera la red."""

    def __init__(self, fail_at: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fail_at = fail_at

    def transcribe(self, audio_path, language=None, prompt=None):
        if len(self.calls) + 1 == self.fail_at:
            self.calls.append((audio_path, language, prompt))
            raise TranscriptionError("No hay conexión con OpenAI.")
        return super().transcribe(audio_path, language, prompt)


class ChunkCacheResumeTests(unittest.TestCase):
    """Si falla a mitad, las partes ya pagadas se reutilizan al reintentar."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache = ChunkCache(self.tmp / "cache")
        self.video = make_video(self.tmp / "larga.mp4", seconds=60)

    def _parts(self):
        fake = FakeTranscriber(max_file_bytes=60_000)
        TranscriptionPipeline(fake).run(self.video, "txt")
        return len(fake.calls)

    def test_resume_skips_finished_parts(self):
        total = self._parts()
        self.assertGreaterEqual(total, 3)

        failing = FailingTranscriber(fail_at=3, max_file_bytes=60_000)
        with self.assertRaises(TranscriptionError) as ctx:
            TranscriptionPipeline(failing, cache=self.cache).run(
                self.video, "txt", output_dir=self.tmp / "out")
        self.assertIn("quedaron guardadas", str(ctx.exception))
        self.assertFalse((self.tmp / "out").exists() and any((self.tmp / "out").iterdir()))

        retry = FakeTranscriber(max_file_bytes=60_000)
        pipeline = TranscriptionPipeline(retry, cache=self.cache)
        out = pipeline.run(self.video, "txt", output_dir=self.tmp / "out")
        self.assertEqual(pipeline.reused_parts, 2)
        self.assertEqual(len(retry.calls), total - 2)        # solo se pagan las que faltaban
        self.assertIsNotNone(retry.calls[0][2])              # la parte 3 recibe el contexto de la 2
        self.assertTrue(any("reutilizaron 2" in w for w in pipeline.warnings))
        self.assertIn("parte 1", out.read_text(encoding="utf-8"))
        self.assertEqual(list((self.tmp / "cache").iterdir()), [])  # se limpia al terminar

    def test_different_context_does_not_reuse(self):
        failing = FailingTranscriber(fail_at=2, max_file_bytes=60_000)
        with self.assertRaises(TranscriptionError):
            TranscriptionPipeline(failing, cache=self.cache).run(self.video, "txt",
                                                                 context="tema A")
        retry = FakeTranscriber(max_file_bytes=60_000)
        pipeline = TranscriptionPipeline(retry, cache=self.cache)
        pipeline.run(self.video, "txt", context="tema B")
        self.assertEqual(pipeline.reused_parts, 0)

    def test_first_part_failure_message_unchanged(self):
        failing = FailingTranscriber(fail_at=1, max_file_bytes=60_000)
        with self.assertRaises(TranscriptionError) as ctx:
            TranscriptionPipeline(failing, cache=self.cache).run(self.video, "txt")
        self.assertNotIn("quedaron guardadas", str(ctx.exception))

    def test_corrupt_part_is_ignored(self):
        key = "k"
        self.cache.put(key, 0, ChunkTranscription("hola", [Segment(0.0, 1.0, "hola")]))
        self.assertEqual(self.cache.get(key, 0).segments[0].text, "hola")
        (self.tmp / "cache" / key / "part_0000.json").write_text("{roto", encoding="utf-8")
        self.assertIsNone(self.cache.get(key, 0))

    def test_prune_removes_old_jobs(self):
        cache = ChunkCache(self.tmp / "cache", max_age_seconds=-1)
        cache.put("viejo", 0, ChunkTranscription("x"))
        cache.prune()
        self.assertFalse((self.tmp / "cache" / "viejo").exists())


if __name__ == "__main__":
    unittest.main()
