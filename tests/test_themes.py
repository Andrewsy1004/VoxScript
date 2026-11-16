import re
import tempfile
import tkinter as tk
import unittest
from dataclasses import fields
from pathlib import Path

from app.config import Settings, SettingsStore
from app.ui.themes import (DEFAULT_THEME, THEMES, Theme, apply_theme, current_theme, get_theme,
                           theme_by_label)

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ThemeCatalogTests(unittest.TestCase):
    def test_default_theme_is_first_and_native(self):
        self.assertEqual(THEMES[0].key, DEFAULT_THEME)
        self.assertFalse(THEMES[0].custom)

    def test_keys_and_labels_are_unique(self):
        self.assertEqual(len({t.key for t in THEMES}), len(THEMES))
        self.assertEqual(len({t.label for t in THEMES}), len(THEMES))

    def test_custom_themes_define_every_color(self):
        for theme in THEMES:
            for f in fields(Theme):
                value = getattr(theme, f.name)
                if f.name in ("key", "label"):
                    continue
                if f.name.startswith("zone_"):
                    for i, color in enumerate(value):
                        if color is None and i == 1:  # relleno opcional
                            continue
                        self.assertRegex(color, HEX, f"{theme.key}.{f.name}")
                elif value is not None:
                    self.assertRegex(value, HEX, f"{theme.key}.{f.name}")
                else:
                    self.assertFalse(theme.custom, f"{theme.key}.{f.name} falta")

    def test_unknown_key_falls_back_to_default(self):
        self.assertEqual(get_theme("no-existe").key, DEFAULT_THEME)
        self.assertEqual(theme_by_label("no-existe").key, DEFAULT_THEME)
        self.assertEqual(theme_by_label("Oscuro").key, "dark")


class ThemeSettingsTests(unittest.TestCase):
    def test_default_setting_and_roundtrip(self):
        self.assertEqual(Settings().theme, DEFAULT_THEME)
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "config.json")
            settings = Settings(theme="dark")
            store.save(settings)
            self.assertEqual(store.load().theme, "dark")


class ApplyThemeTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin pantalla disponible")
        self.root.withdraw()

    def tearDown(self):
        apply_theme(self.root, get_theme(DEFAULT_THEME))
        self.root.destroy()

    def test_every_theme_applies_and_can_switch_back(self):
        from tkinter import ttk
        native = ttk.Style(self.root).theme_use()
        for theme in THEMES:
            apply_theme(self.root, theme)
            self.assertIs(current_theme(), theme)
            if theme.custom:
                self.assertEqual(ttk.Style(self.root).lookup("TFrame", "background").upper(),
                                 theme.bg.upper())
        apply_theme(self.root, get_theme(DEFAULT_THEME))
        self.assertEqual(ttk.Style(self.root).theme_use(), native)


if __name__ == "__main__":
    unittest.main()
