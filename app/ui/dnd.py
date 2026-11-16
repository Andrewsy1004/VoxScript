"""Arrastrar y soltar archivos sobre la ventana.

Usa `tkinterdnd2` (envoltorio de la extensión tkDnD). Si no está instalado o
no carga en este sistema, la app funciona igual, solo que sin arrastrar y soltar.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from typing import Callable, Iterable, Optional

log = logging.getLogger(__name__)


def create_root() -> tuple[tk.Tk, bool]:
    """Crea la ventana raíz. Devuelve (root, arrastrar_y_soltar_disponible)."""
    try:
        from tkinterdnd2 import TkinterDnD

        return TkinterDnD.Tk(), True
    except Exception:  # paquete ausente o binario tkDnD sin soporte en este sistema
        log.warning("Arrastrar y soltar no disponible", exc_info=True)
        return tk.Tk(), False


def choose_dropped(paths: Iterable[str], supported: set[str]) -> tuple[Optional[Path], str]:
    """Elige el archivo a transcribir entre los soltados.

    Devuelve (ruta o None, mensaje para el usuario; vacío si no hay nada que avisar).
    """
    items = [Path(p) for p in paths if p]
    files = [p for p in items if p.is_file()]
    valid = [p for p in files if p.suffix.lower() in supported]
    if not valid:
        if items and not files:
            return None, "Suelta un archivo de video o audio, no una carpeta."
        name = files[0].name if files else ""
        return None, f"Formato no compatible: '{name}'." if name else "No se recibió ningún archivo."
    if len(valid) > 1:
        return valid[0], (f"Se eligió '{valid[0].name}'. "
                          "Por ahora se transcribe un archivo a la vez.")
    return valid[0], ""


def split_documents(paths: Iterable[str], doc_exts: set[str]) -> tuple[list[Path], list[str]]:
    """Separa los documentos de estudio del resto de archivos soltados.

    Devuelve (documentos, demás rutas tal como llegaron).
    """
    docs, rest = [], []
    for p in paths:
        if not p:
            continue
        path = Path(p)
        if path.is_file() and path.suffix.lower() in doc_exts:
            docs.append(path)
        else:
            rest.append(p)
    return docs, rest


def enable_file_drop(
    widgets: Iterable[tk.Misc],
    on_drop: Callable[[list[str]], None],
    on_enter: Optional[Callable[[], None]] = None,
    on_leave: Optional[Callable[[], None]] = None,
) -> None:
    """Registra los widgets como destino de archivos soltados."""
    from tkinterdnd2 import COPY, DND_FILES

    def handle_drop(event):
        on_drop(list(event.widget.tk.splitlist(event.data)))
        return COPY

    def handle_enter(event):
        if on_enter:
            on_enter()
        return COPY

    def handle_leave(event):
        if on_leave:
            on_leave()
        return event.action

    for w in widgets:
        w.drop_target_register(DND_FILES)
        w.dnd_bind("<<Drop>>", handle_drop)
        w.dnd_bind("<<DropEnter>>", handle_enter)
        w.dnd_bind("<<DropPosition>>", lambda e: COPY)
        w.dnd_bind("<<DropLeave>>", handle_leave)
