import tempfile
import threading
import unittest
from pathlib import Path

from docx import Document

from app.core.errors import CancelledError, MediaError
from app.core.pipeline import TranscriptionPipeline, build_output_path
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


if __name__ == "__main__":
    unittest.main()
