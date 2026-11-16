"""Recuadro punteado para soltar (o hacer clic y elegir) un archivo."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable

# Colores: borde, relleno, título, subtítulo
_IDLE = ("#9CA3AF", None, "#374151", "#6B7280")
_HOVER = ("#2563EB", "#F5F8FF", "#1F2937", "#6B7280")
_DRAG = ("#2563EB", "#E0EBFF", "#1D4ED8", "#1D4ED8")
_DONE = ("#16A34A", "#F0FDF4", "#166534", "#6B7280")
_DISABLED = ("#D1D5DB", None, "#9CA3AF", "#9CA3AF")
_WARN = "#B45309"

DASH, GAP, LINE = 8, 5, 2


@dataclass(frozen=True)
class ZoneTexts:
    idle: str = "Arrastra aquí un video o audio"
    idle_hint: str = "o haz clic para elegirlo · también PDF/Word para las flashcards"
    no_dnd: str = "Haz clic para elegir un video o audio"
    drag_hint: str = "Video o audio, o documentos PDF/Word para flashcards"
    change_hint: str = "Arrastra otro archivo o haz clic para cambiarlo"
    change_hint_no_dnd: str = "Haz clic para cambiarlo"


DOCUMENT_TEXTS = ZoneTexts(
    idle="Arrastra aquí documentos PDF o Word",
    idle_hint="o haz clic para agregarlos",
    no_dnd="Haz clic para agregar documentos PDF o Word",
    drag_hint="PDF, Word (.docx), Markdown o texto",
    change_hint="Arrastra más documentos o haz clic para agregar",
    change_hint_no_dnd="Haz clic para agregar más",
)


class DropZone(tk.Canvas):
    def __init__(self, master: tk.Misc, on_click: Callable[[], None],
                 dnd_available: bool, height: int = 104,
                 texts: ZoneTexts = ZoneTexts()) -> None:
        bg = ttk.Style(master).lookup("TFrame", "background") or master.winfo_toplevel().cget("bg")
        super().__init__(master, height=height, bg=bg, bd=0, highlightthickness=0,
                         cursor="hand2")
        self._bg = bg
        self._t = texts
        self._on_click = on_click
        self._dnd = dnd_available
        self._file = ""
        self._hover = self._dragging = False
        self._enabled = True
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", lambda e: self._enabled and self._on_click())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))

    # ---------- API ----------

    def set_file(self, name: str) -> None:
        self._file = name
        self._draw()

    def set_dragging(self, active: bool) -> None:
        self._dragging = active
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    # ---------- dibujo ----------

    def _set_hover(self, value: bool) -> None:
        self._hover = value
        self._draw()

    def _texts(self) -> tuple[str, str, bool]:
        """(título, subtítulo, subtítulo_es_aviso)"""
        if not self._enabled:
            return "Transcripción en curso…", "Espera a que termine para elegir otro archivo.", False
        t = self._t
        if self._dragging:
            return "Suelta el archivo aquí", t.drag_hint, False
        if self._file:
            return f"✓  {self._file}", t.change_hint if self._dnd else t.change_hint_no_dnd, False
        if self._dnd:
            return t.idle, t.idle_hint, False
        return (t.no_dnd,
                "Arrastrar y soltar no disponible: ejecuta  pip install -r requirements.txt",
                True)

    def _palette(self) -> tuple:
        if not self._enabled:
            return _DISABLED
        if self._dragging:
            return _DRAG
        if self._hover:
            return _HOVER
        if self._file:
            return _DONE
        return _IDLE

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20:
            return
        outline, fill, title_fg, sub_fg = self._palette()
        m = LINE  # margen para que el borde no se corte
        x0, y0, x1, y1 = m, m, w - m, h - m
        if fill:
            self.create_rectangle(x0, y0, x1, y1, fill=fill, outline="")
        # Borde punteado dibujado a mano: el `dash` de Tk no es fiable en Windows.
        for ax, ay, bx, by in ((x0, y0, x1, y0), (x1, y0, x1, y1),
                               (x1, y1, x0, y1), (x0, y1, x0, y0)):
            self._dashed(ax, ay, bx, by, outline)

        title, subtitle, warn = self._texts()
        self.create_text(w / 2, h / 2 - 11, text=title, fill=title_fg,
                         font=("TkDefaultFont", 11, "bold"), width=w - 32)
        self.create_text(w / 2, h / 2 + 13, text=subtitle, fill=_WARN if warn else sub_fg,
                         font=("TkDefaultFont", 9), width=w - 32)

    def _dashed(self, ax: float, ay: float, bx: float, by: float, color: str) -> None:
        length = abs(bx - ax) + abs(by - ay)  # los lados son horizontales o verticales
        if not length:
            return
        dx, dy = (bx - ax) / length, (by - ay) / length
        pos = 0.0
        while pos < length:
            end = min(pos + DASH, length)
            self.create_line(ax + dx * pos, ay + dy * pos, ax + dx * end, ay + dy * end,
                             fill=color, width=LINE)
            pos = end + GAP
