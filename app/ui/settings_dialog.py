"""Ventana de configuración: API key y modelo."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from typing import Callable

from app.config import DEFAULT_CORRECTION_MODEL, DEFAULT_MODEL, Settings, SettingsStore
from app.ui.themes import THEMES, get_theme, theme_by_label, window_background

API_KEYS_URL = "https://platform.openai.com/api-keys"
PRICING_URL = "https://openai.com/api/pricing"


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, settings: Settings, store: SettingsStore,
                 on_saved: Callable[[Settings], None], message: str = "") -> None:
        super().__init__(parent)
        self.settings, self.store, self.on_saved = settings, store, on_saved
        self.title("Configuración")
        self.resizable(False, False)
        self.transient(parent)
        self.configure(background=window_background(parent))

        frm = ttk.Frame(self, padding=20)
        frm.grid(sticky="nsew")
        frm.columnconfigure(1, weight=1)

        row = 0
        if message:
            ttk.Label(frm, text=message, style="Warn.TLabel", wraplength=420).grid(
                row=row, column=0, columnspan=3, sticky="w", pady=(0, 12))
            row += 1

        ttk.Label(frm, text="API key de OpenAI").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.key_var = tk.StringVar(value=settings.api_key)
        self.key_entry = ttk.Entry(frm, textvariable=self.key_var, show="•", width=44)
        self.key_entry.grid(row=row, column=1, sticky="ew")
        self.show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Mostrar", variable=self.show_var,
                        command=self._toggle_show).grid(row=row, column=2, padx=(8, 0))
        row += 1

        link = ttk.Label(frm, text="¿No tienes una? Créala aquí", style="Link.TLabel",
                         cursor="hand2")
        link.grid(row=row, column=1, sticky="w", pady=(4, 12))
        link.bind("<Button-1>", lambda _e: webbrowser.open(API_KEYS_URL))
        row += 1

        ttk.Label(frm, text="Modelo").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.model_var = tk.StringVar(value=settings.model or DEFAULT_MODEL)
        ttk.Entry(frm, textvariable=self.model_var, width=44).grid(row=row, column=1, sticky="ew")
        row += 1

        ttk.Label(frm, text="Modelo de IA").grid(row=row, column=0, sticky="w",
                                                       padx=(0, 10), pady=(8, 0))
        self.correction_var = tk.StringVar(
            value=settings.correction_model or DEFAULT_CORRECTION_MODEL)
        ttk.Entry(frm, textvariable=self.correction_var, width=44).grid(
            row=row, column=1, sticky="ew", pady=(8, 0))
        row += 1
        ttk.Label(frm, style="Muted.TLabel", wraplength=420,
                  text="Se usa para «Revisar el texto con IA» y para crear flashcards.").grid(
            row=row, column=1, columnspan=2, sticky="w", pady=(2, 0))
        row += 1

        # Precios para estimar el costo
        ttk.Label(frm, text="Precios (USD)", font=("TkDefaultFont", 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(16, 4))
        row += 1
        self.price_vars: dict[str, tk.StringVar] = {}
        for attr, label in (
            ("price_transcription_per_minute", "Transcripción, por minuto"),
            ("price_chat_input_per_million", "Modelo de IA, 1M tokens de entrada"),
            ("price_chat_output_per_million", "Modelo de IA, 1M tokens de salida"),
        ):
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
            var = tk.StringVar(value=f"{float(getattr(settings, attr)):g}")
            ttk.Entry(frm, textvariable=var, width=12).grid(row=row, column=1, sticky="w", pady=2)
            self.price_vars[attr] = var
            row += 1
        price_link = ttk.Label(frm, style="Link.TLabel", cursor="hand2", wraplength=420,
                               text="Son estimaciones. Verifica los precios vigentes en "
                                    "openai.com/api/pricing")
        price_link.grid(row=row, column=1, columnspan=2, sticky="w", pady=(2, 0))
        price_link.bind("<Button-1>", lambda _e: webbrowser.open(PRICING_URL))
        row += 1

        # Apariencia
        ttk.Label(frm, text="Tema").grid(row=row, column=0, sticky="w", padx=(0, 10),
                                         pady=(16, 0))
        self.theme_var = tk.StringVar(value=get_theme(settings.theme).label)
        ttk.Combobox(frm, textvariable=self.theme_var, values=[t.label for t in THEMES],
                     state="readonly", width=28).grid(row=row, column=1, sticky="w",
                                                      pady=(16, 0))
        row += 1
        ttk.Label(frm, style="Muted.TLabel", wraplength=420,
                  text="Colores de la ventana. «Predeterminado» usa el aspecto del sistema."
                  ).grid(row=row, column=1, columnspan=2, sticky="w", pady=(2, 0))
        row += 1

        ttk.Label(
            frm, style="Muted.TLabel", wraplength=420,
            text=f"La key se guarda solo en este equipo, en:\n{store.path}",
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(14, 0))
        row += 1

        buttons = ttk.Frame(frm)
        buttons.grid(row=row, column=0, columnspan=3, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Guardar", command=self._save).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.key_entry.focus_set()
        self.grab_set()

    def _toggle_show(self) -> None:
        self.key_entry.configure(show="" if self.show_var.get() else "•")

    def _save(self) -> None:
        prices = {}
        for attr, var in self.price_vars.items():
            try:
                value = float(var.get().strip().replace(",", "."))
                if value < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Configuración",
                                     f"Precio no válido: «{var.get()}». Usa un número, p. ej. 0.0045.",
                                     parent=self)
                return
            prices[attr] = value
        for attr, value in prices.items():
            setattr(self.settings, attr, value)
        self.settings.api_key = self.key_var.get().strip()
        self.settings.model = self.model_var.get().strip() or DEFAULT_MODEL
        self.settings.correction_model = (self.correction_var.get().strip()
                                          or DEFAULT_CORRECTION_MODEL)
        self.settings.theme = theme_by_label(self.theme_var.get()).key
        self.store.save(self.settings)
        self.on_saved(self.settings)
        self.destroy()
