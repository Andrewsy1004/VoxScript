import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.config import DEFAULT_MODEL, Settings, SettingsStore, load_env

ENV_KEYS = ["OPENAI_API_KEY", "TRANSCRIPTOR_MODEL", "TRANSCRIPTOR_LANGUAGE",
            "TRANSCRIPTOR_OUTPUT_FORMAT", "TRANSCRIPTOR_OUTPUT_DIR"]


def clean_env(**values):
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    env.update(values)
    return mock.patch.dict(os.environ, env, clear=True)


class SettingsEnvTests(unittest.TestCase):
    def test_builtin_defaults_without_env(self):
        with clean_env():
            s = Settings()
        self.assertEqual((s.model, s.language, s.output_format, s.output_dir),
                         (DEFAULT_MODEL, "es", "docx", ""))

    def test_env_defaults(self):
        with clean_env(TRANSCRIPTOR_MODEL="whisper-1", TRANSCRIPTOR_LANGUAGE="en",
                       TRANSCRIPTOR_OUTPUT_FORMAT="txt", TRANSCRIPTOR_OUTPUT_DIR="/tmp/out"):
            s = Settings()
        self.assertEqual((s.model, s.language, s.output_format, s.output_dir),
                         ("whisper-1", "en", "txt", "/tmp/out"))

    def test_saved_config_overrides_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"model": "saved-model"}), encoding="utf-8")
            with clean_env(TRANSCRIPTOR_MODEL="env-model", TRANSCRIPTOR_LANGUAGE="fr"):
                s = SettingsStore(path).load()
        self.assertEqual(s.model, "saved-model")
        self.assertEqual(s.language, "fr")  # no guardado: viene del entorno

    def test_api_key_precedence(self):
        with clean_env(OPENAI_API_KEY="env-key"):
            self.assertEqual(Settings().effective_api_key(), "env-key")
            self.assertEqual(Settings(api_key="saved-key").effective_api_key(), "saved-key")


class LoadEnvTests(unittest.TestCase):
    def test_loads_first_existing_file_without_overriding_real_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("OPENAI_API_KEY=from-file\nTRANSCRIPTOR_MODEL=file-model\n",
                                encoding="utf-8")
            with clean_env(TRANSCRIPTOR_MODEL="real-model"):
                loaded = load_env([Path(tmp) / "missing.env", env_file])
                self.assertEqual(loaded, env_file)
                self.assertEqual(os.environ["OPENAI_API_KEY"], "from-file")
                self.assertEqual(os.environ["TRANSCRIPTOR_MODEL"], "real-model")

    def test_no_file_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_env([Path(tmp) / ".env"]))


if __name__ == "__main__":
    unittest.main()
