import tempfile
import unittest
from pathlib import Path

from docx import Document

from app.core.models import ExportOptions, Segment, Transcript
from app.exporters import available_formats, get_exporter
from app.exporters.formatting import format_duration, format_timestamp


def sample(with_segments=True):
    segs = [Segment(0, 3, "Buenos días a todos."), Segment(3.5, 6, "Hoy hablamos del proyecto."),
            Segment(12, 15, "Después de una pausa larga, seguimos.")]
    return Transcript(text=" ".join(s.text for s in segs), segments=segs if with_segments else [],
                      source_name="reunión.mov", duration=3725, language="es", model="gpt-transcribe")


class FormattingTests(unittest.TestCase):
    def test_timestamps(self):
        self.assertEqual(format_timestamp(3725.9), "01:02:05")
        self.assertEqual(format_duration(3725), "1 h 02 min 05 s")
        self.assertEqual(format_duration(65), "1 min 05 s")
        self.assertEqual(format_duration(None), "desconocida")


class ExporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_registry(self):
        self.assertEqual([k for k, _ in available_formats()], ["docx", "txt"])

    def test_txt_with_timestamps_and_pause_split(self):
        out = get_exporter("txt").export(sample(), self.tmp / "a.txt", ExportOptions())
        content = out.read_text(encoding="utf-8")
        self.assertIn("Archivo: reunión.mov", content)
        self.assertIn("[00:00:00] Buenos días a todos. Hoy hablamos del proyecto.", content)
        self.assertIn("[00:00:12] Después de una pausa larga", content)  # pausa > 2 s = párrafo nuevo

    def test_txt_without_segments(self):
        out = get_exporter("txt").export(sample(False), self.tmp / "b.txt",
                                         ExportOptions(include_header=False))
        content = out.read_text(encoding="utf-8")
        self.assertNotIn("[", content)
        self.assertTrue(content.startswith("Buenos días"))

    def test_docx(self):
        out = get_exporter("docx").export(sample(), self.tmp / "c.docx", ExportOptions())
        text = "\n".join(p.text for p in Document(str(out)).paragraphs)
        self.assertIn("Transcripción", text)
        self.assertIn("[00:00:12]", text)
        self.assertIn("Idioma: Español", text)


if __name__ == "__main__":
    unittest.main()
