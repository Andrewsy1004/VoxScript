"""Contenedor con scroll vertical.

Sirve para que la ventana se pueda recorrer en pantallas pequeñas: el
contenido va dentro de ``inner`` y, si no cabe, aparece una barra de scroll.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

from app.ui.themes import window_background

# Espacio que se deja para la barra de tareas y el título de la ventana
SCREEN_MARGIN = 120


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0,
                                background=window_background(self))
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        root = self.winfo_toplevel()
        root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        root.bind_all("<Button-4>", self._on_mousewheel, add="+")
        root.bind_all("<Button-5>", self._on_mousewheel, add="+")

    def refresh_theme(self) -> None:
        self.canvas.configure(background=window_background(self))

    def _max_height(self) -> int:
        return max(200, self.winfo_screenheight() - SCREEN_MARGIN)

    def _on_inner_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # La ventana crece con el contenido, pero nunca más alta que la pantalla
        self.canvas.configure(width=self.inner.winfo_reqwidth(),
                              height=min(self.inner.winfo_reqheight(), self._max_height()))
        self._update_scrollbar()

    def _on_canvas_configure(self, event) -> None:
        # El contenido se estira a lo ancho, como antes del scroll
        self.canvas.itemconfigure(self._window, width=event.width)
        self._update_scrollbar()

    def _overflows(self) -> bool:
        return self.inner.winfo_reqheight() > self.canvas.winfo_height()

    def _update_scrollbar(self) -> None:
        if self._overflows():
            self.scrollbar.grid()
        else:
            self.scrollbar.grid_remove()
            self.canvas.yview_moveto(0)

    def _on_mousewheel(self, event) -> None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget is None or widget.winfo_toplevel() is not self.winfo_toplevel():
            return  # otra ventana (p. ej. Configuración)
        if isinstance(widget, (tk.Text, tk.Listbox)):
            return  # tienen su propio scroll
        if not self._overflows():
            return
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        elif sys.platform == "darwin":
            step = -event.delta
        else:
            step = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
        self.canvas.yview_scroll(step, "units")
