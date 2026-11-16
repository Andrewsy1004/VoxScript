import tempfile
import unittest
from pathlib import Path

from app.media import SUPPORTED_EXTENSIONS
from app.ui.dnd import choose_dropped


class ChooseDroppedTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, name):
        p = self.dir / name
        p.write_bytes(b"x")
        return p

    def test_single_supported_file(self):
        video = self.make("reunión con espacios.mov")
        path, msg = choose_dropped([str(video)], SUPPORTED_EXTENSIONS)
        self.assertEqual(path, video)
        self.assertEqual(msg, "")

    def test_extension_is_case_insensitive(self):
        video = self.make("CLIP.MP4")
        path, _ = choose_dropped([str(video)], SUPPORTED_EXTENSIONS)
        self.assertEqual(path, video)

    def test_unsupported_file(self):
        doc = self.make("notas.pdf")
        path, msg = choose_dropped([str(doc)], SUPPORTED_EXTENSIONS)
        self.assertIsNone(path)
        self.assertIn("notas.pdf", msg)

    def test_folder(self):
        path, msg = choose_dropped([str(self.dir)], SUPPORTED_EXTENSIONS)
        self.assertIsNone(path)
        self.assertIn("carpeta", msg)

    def test_several_files_takes_first_supported(self):
        doc = self.make("notas.pdf")
        a, b = self.make("a.mov"), self.make("b.mp3")
        path, msg = choose_dropped([str(doc), str(a), str(b)], SUPPORTED_EXTENSIONS)
        self.assertEqual(path, a)
        self.assertIn("a.mov", msg)

    def test_empty(self):
        path, msg = choose_dropped([], SUPPORTED_EXTENSIONS)
        self.assertIsNone(path)
        self.assertTrue(msg)


if __name__ == "__main__":
    unittest.main()
