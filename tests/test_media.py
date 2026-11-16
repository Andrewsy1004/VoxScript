import tempfile
import unittest
from pathlib import Path

from app.core.errors import MediaError
from app.media import extract_audio, probe, split_audio
from tests.helpers import make_video


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_probe_detects_audio_and_duration(self):
        for ext in (".mp4", ".mov", ".mkv", ".avi", ".webm"):
            with self.subTest(ext=ext):
                info = probe(make_video(self.tmp / f"v{ext}", seconds=3))
                self.assertTrue(info.has_audio)
                self.assertAlmostEqual(info.duration, 3, delta=0.5)

    def test_probe_video_without_audio(self):
        info = probe(make_video(self.tmp / "mudo.mp4", audio=False))
        self.assertFalse(info.has_audio)

    def test_probe_corrupt_file(self):
        bad = self.tmp / "roto.mp4"
        bad.write_bytes(b"esto no es un video" * 100)
        with self.assertRaises(MediaError):
            probe(bad)

    def test_extract_and_split(self):
        video = make_video(self.tmp / "largo.mov", seconds=60)
        audio = extract_audio(video, self.tmp / "audio.mp3")
        size = audio.stat().st_size
        chunks = split_audio(audio, 60.0, max_bytes=size // 3 + 1, work_dir=self.tmp / "partes")
        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(chunks[0].offset, 0.0)
        offsets = [c.offset for c in chunks]
        self.assertEqual(offsets, sorted(offsets))
        self.assertAlmostEqual(sum(c.duration for c in chunks), 60, delta=1.5)
        self.assertTrue(all(c.path.stat().st_size <= size // 3 + 1 for c in chunks))

    def test_small_audio_not_split(self):
        audio = extract_audio(make_video(self.tmp / "corto.mp4"), self.tmp / "a.mp3")
        chunks = split_audio(audio, 5.0, max_bytes=10**9, work_dir=self.tmp / "p")
        self.assertEqual(len(chunks), 1)


if __name__ == "__main__":
    unittest.main()
