"""Ventana principal.

La transcripción corre en un hilo aparte para que la ventana no se congele.
El hilo envía mensajes a una cola que la ventana revisa cada 100 ms.
"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from app import APP_NAME, __version__, resource_path
from app.config import LANGUAGES, Settings, SettingsStore, chunk_cache_dir, config_dir
from app.core.chunk_cache import ChunkCache
from app.core.costs import CostReport, format_usd
from app.core.errors import CancelledError, TranscriptorError
from app.core.models import ExportOptions
from app.core.pipeline import TranscriptionPipeline
from app.exporters import available_formats
from app.media import SUPPORTED_EXTENSIONS
from app.correction import create_corrector
from app.flashcards import create_flashcard_generator
from app.transcription import create_transcriber
from app.documents import SUPPORTED_DOC_EXTENSIONS
from app.ui.dnd import choose_dropped, create_root, enable_file_drop, split_documents
from app.ui.drop_zone import DOCUMENT_TEXTS, DropZone
from app.ui.scrollable import ScrollableFrame
from app.ui.themes import apply_theme, current_theme, get_theme, style_listbox, style_text
from app.ui.settings_dialog import SettingsDialog

log = logging.getLogger(__name__)
SAME_FOLDER = "Misma carpeta que el video"


def open_path(path: Path) -> None:
    """Abre un archivo o carpeta con la aplicación predeterminada del sistema."""
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class MainWindow:
    def __init__(self, root: tk.Tk, store: SettingsStore, dnd_available: bool = False) -> None:
        self.root, self.store = root, store
        self.dnd_available = dnd_available
        self._status_before_drag: Optional[str] = None
        self.settings: Settings = store.load()
        self.events: queue.Queue = queue.Queue()
        self.cancel_event: Optional[threading.Event] = None
        self.worker: Optional[threading.Thread] = None
        self.last_output: Optional[Path] = None

        root.title(f"{APP_NAME} {__version__}")
        root.minsize(600, 0)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self.root.after(100, self._poll_events)

    # ---------- construcción de la interfaz ----------

    def _build(self) -> None:
        # El tema se aplica antes de crear los widgets para que nazcan con sus colores
        apply_theme(self.root, get_theme(self.settings.theme))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        # Scroll para pantallas pequeñas donde no cabe todo el contenido
        self.scroller = ScrollableFrame(self.root)
        self.scroller.grid(row=0, column=0, sticky="nsew")
        self.scroller.inner.columnconfigure(0, weight=1)
        frm = ttk.Frame(self.scroller.inner, padding=24)
        frm.grid(sticky="nsew")
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Transcriptor de video", style="Title.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frm, style="Muted.TLabel",
                  text="Elige un video y obtén su transcripción en Word o en texto.").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(2, 14))

        # Zona para soltar o hacer clic
        self.drop_zone = DropZone(frm, self._choose_file, self.dnd_available)
        self.drop_zone.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        pad = {"pady": 6}
        # Video
        ttk.Label(frm, text="Video").grid(row=3, column=0, sticky="w", padx=(0, 12), **pad)
        self.file_var = tk.StringVar()
        file_entry = ttk.Entry(frm, textvariable=self.file_var, state="readonly")
        file_entry.grid(row=3, column=1, sticky="ew", **pad)
        file_btns = ttk.Frame(frm)
        file_btns.grid(row=3, column=2, padx=(8, 0), **pad)
        self.choose_btn = ttk.Button(file_btns, text="Elegir…", command=self._choose_file)
        self.choose_btn.pack(side="left")
        # Quitar el video permite crear flashcards solo con documentos
        self.clear_btn = ttk.Button(file_btns, text="✕", width=3, command=self._clear_source)
        self.clear_btn.pack(side="left", padx=(4, 0))

        # Formato
        ttk.Label(frm, text="Formato").grid(row=4, column=0, sticky="w", **pad)
        self.format_var = tk.StringVar(value=self.settings.output_format)
        fmt_frame = ttk.Frame(frm)
        fmt_frame.grid(row=4, column=1, columnspan=2, sticky="w", **pad)
        for key, label in available_formats():
            ttk.Radiobutton(fmt_frame, text=label, value=key, variable=self.format_var).pack(
                side="left", padx=(0, 16))

        # Idioma
        ttk.Label(frm, text="Idioma").grid(row=5, column=0, sticky="w", **pad)
        labels = [label for label, _ in LANGUAGES]
        current = next((l for l, c in LANGUAGES if c == self.settings.language), labels[0])
        self.lang_var = tk.StringVar(value=current)
        ttk.Combobox(frm, textvariable=self.lang_var, values=labels, state="readonly",
                     width=28).grid(row=5, column=1, sticky="w", **pad)

        # Contexto del tema
        ttk.Label(frm, text="Contexto\n(opcional)").grid(row=6, column=0, sticky="nw", pady=(8, 6))
        ctx_frame = ttk.Frame(frm)
        ctx_frame.grid(row=6, column=1, columnspan=2, sticky="ew", **pad)
        ctx_frame.columnconfigure(0, weight=1)
        self.context_text = tk.Text(ctx_frame, height=3, wrap="word", font="TkDefaultFont",
                                    relief="solid", borderwidth=1, padx=6, pady=4,
                                    highlightthickness=1, highlightcolor="#2563EB",
                                    highlightbackground="#D1D5DB")
        self.context_text.grid(row=0, column=0, sticky="ew")
        self.context_text.insert("1.0", self.settings.context)
        ttk.Label(ctx_frame, style="Muted.TLabel", wraplength=470,
                  text="¿De qué trata? Nombres, empresas, siglas o términos técnicos que se "
                       "mencionan. Ej.: «Reunión de producto sobre la app móvil; hablan Ana y "
                       "Raúl; temas: onboarding, KPI, Figma»."
                  ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ai_opts = ttk.Frame(frm)
        ai_opts.grid(row=7, column=1, columnspan=2, sticky="w", **pad)
        self.correct_var = tk.BooleanVar(value=self.settings.correct_with_context)
        ttk.Checkbutton(ai_opts, variable=self.correct_var,
                        text="Revisar el texto con IA usando el contexto (costo extra pequeño)"
                        ).pack(anchor="w")
        self.cards_var = tk.BooleanVar(value=self.settings.make_flashcards)
        ttk.Checkbutton(ai_opts, variable=self.cards_var, command=self._on_cards_toggled,
                        text="Crear flashcards para estudiar en Anki (costo extra pequeño)"
                        ).pack(anchor="w", pady=(6, 0))

        # Material para flashcards (documentos + resultados de aprendizaje)
        self.study_frame = self._build_study_frame(frm)
        self.study_frame.grid(row=8, column=1, columnspan=2, sticky="ew", pady=(2, 6))

        # Carpeta de salida
        ttk.Label(frm, text="Guardar en").grid(row=9, column=0, sticky="w", **pad)
        self.outdir_var = tk.StringVar(value=self.settings.output_dir or SAME_FOLDER)
        ttk.Label(frm, textvariable=self.outdir_var, style="Muted.TLabel").grid(
            row=9, column=1, sticky="w", **pad)
        out_btns = ttk.Frame(frm)
        out_btns.grid(row=9, column=2, padx=(8, 0), **pad)
        ttk.Button(out_btns, text="Cambiar…", command=self._choose_outdir).pack(side="left")

        # Opciones
        self.ts_var = tk.BooleanVar(value=self.settings.include_timestamps)
        ttk.Checkbutton(frm, text="Incluir marcas de tiempo (si el modelo las ofrece)",
                        variable=self.ts_var).grid(row=10, column=1, columnspan=2, sticky="w", **pad)

        ttk.Separator(frm).grid(row=11, column=0, columnspan=3, sticky="ew", pady=16)

        # Progreso
        self.progress = ttk.Progressbar(frm, mode="determinate", maximum=100)
        self.progress.grid(row=12, column=0, columnspan=3, sticky="ew")
        self.status_var = tk.StringVar(value="Listo para empezar.")
        ttk.Label(frm, textvariable=self.status_var, style="Muted.TLabel", wraplength=540).grid(
            row=13, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # Resultado
        self.result_frame = ttk.Frame(frm)
        self.result_frame.grid(row=14, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.result_frame.columnconfigure(0, weight=1)
        btns = ttk.Frame(self.result_frame)
        btns.grid(row=0, column=0, sticky="w")
        ttk.Button(btns, text="Abrir archivo",
                   command=lambda: self._open(self.last_output)).pack(side="left")
        ttk.Button(btns, text="Abrir carpeta",
                   command=lambda: self._open(self.last_output.parent if self.last_output else None)
                   ).pack(side="left", padx=(8, 0))
        self.anki_help_btn = ttk.Button(btns, text="Cómo importar en Anki",
                                        command=self._show_anki_help)
        # Desglose del costo estimado
        self.cost_frame = ttk.LabelFrame(self.result_frame, text="Costo estimado", padding=(12, 6))
        self.cost_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.cost_frame.columnconfigure(1, weight=1)
        self.result_frame.grid_remove()

        # Acciones
        actions = ttk.Frame(frm)
        actions.grid(row=15, column=0, columnspan=3, sticky="ew", pady=(20, 0))
        ttk.Button(actions, text="Configuración", command=self._open_settings).pack(side="left")
        self.start_btn = ttk.Button(actions, text="Transcribir", style="Primary.TButton",
                                    command=self._start)
        self.start_btn.pack(side="right")
        self.cancel_btn = ttk.Button(actions, text="Cancelar", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="right", padx=(0, 8))
        self._on_cards_toggled()
        self._style_classic_widgets()

        if self.dnd_available:
            try:
                enable_file_drop([self.root, self.scroller.canvas, self.scroller.inner, frm,
                                  file_entry, self.drop_zone], self._on_drop,
                                 self._on_drag_enter, self._on_drag_leave)
                # Zona propia para los documentos de las flashcards
                enable_file_drop([self.docs_zone, self.docs_list], self._on_docs_drop,
                                 self._on_docs_drag_enter, self._on_docs_drag_leave)
            except Exception:
                log.warning("No se pudo activar arrastrar y soltar", exc_info=True)
                self.dnd_available = False
                self.docs_zone.destroy()
                self.docs_zone = DropZone(self.study_frame, self._add_documents, False,
                                          height=72, texts=DOCUMENT_TEXTS)
                self.docs_zone.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
                self._refresh_documents()
                self.drop_zone.destroy()
                self.drop_zone = DropZone(frm, self._choose_file, False)
                self.drop_zone.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))

    def _build_study_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        box = ttk.LabelFrame(parent, text="Flashcards", padding=(10, 6))
        box.columnconfigure(0, weight=1)

        # 1. Resultados de aprendizaje: el punto de partida de las tarjetas
        ttk.Label(box, text="Resultados de aprendizaje").grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.outcomes_text = tk.Text(box, height=3, wrap="word", font="TkDefaultFont",
                                     relief="solid", borderwidth=1, padx=6, pady=4,
                                     highlightthickness=1, highlightcolor="#2563EB",
                                     highlightbackground="#D1D5DB")
        self.outcomes_text.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.outcomes_text.insert("1.0", self.settings.learning_outcomes)
        ttk.Label(box, style="Muted.TLabel", wraplength=440,
                  text="Las flashcards se crean a partir de estos resultados: cada tarjeta "
                       "ayuda a lograr alguno, con la información de los documentos (y del "
                       "video, si lo incluyes). Uno por línea. Ej.: «Explicar qué es la "
                       "fotosíntesis». Si lo dejas vacío, se cubren las ideas principales."
                  ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # 2. Material de donde sale la información
        ttk.Label(box, text="Documentos").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.docs_zone = DropZone(box, self._add_documents, self.dnd_available, height=72,
                                  texts=DOCUMENT_TEXTS)
        self.docs_zone.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        # La lista solo se muestra cuando hay documentos
        self.docs_list = tk.Listbox(box, height=3, activestyle="none", relief="solid",
                                    borderwidth=1, highlightthickness=0, selectmode="extended")
        self.docs_list.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        self.remove_doc_btn = ttk.Button(box, text="Quitar", command=self._remove_documents)
        self.remove_doc_btn.grid(row=5, column=1, sticky="n", padx=(8, 0), pady=(6, 0))
        self.docs_list.grid_remove()
        self.remove_doc_btn.grid_remove()
        self.documents: list[Path] = []

        self.include_video_var = tk.BooleanVar(value=self.settings.flashcards_include_video)
        self.include_video_chk = ttk.Checkbutton(
            box, variable=self.include_video_var, command=self._update_start_label,
            text="Usar también el contenido del video")
        self.include_video_chk.grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Label(box, style="Muted.TLabel", wraplength=440,
                  text="Desmárcalo para crear las tarjetas solo con los documentos. "
                       "Más material = más tarjetas.").grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(2, 0))
        return box

    # ---------- acciones ----------

    def _on_cards_toggled(self) -> None:
        if self.cards_var.get():
            self.study_frame.grid()
        else:
            self.study_frame.grid_remove()
        self._update_start_label()

    def _docs_only(self) -> bool:
        """Modo solo documentos: sin video, con documentos y flashcards activadas."""
        return not self.file_var.get() and bool(self.documents) and self.cards_var.get()

    def _update_start_label(self) -> None:
        self.start_btn.configure(text="Crear flashcards" if self._docs_only() else "Transcribir")

    def _refresh_documents(self) -> None:
        n = len(self.documents)
        self.docs_zone.set_file(f"{n} documento{'s' if n != 1 else ''}" if n else "")
        if n:
            self.docs_list.grid()
            self.remove_doc_btn.grid()
        else:
            self.docs_list.grid_remove()
            self.remove_doc_btn.grid_remove()
        self._update_start_label()

    def _on_docs_drag_enter(self) -> None:
        if not self._is_running():
            self.docs_zone.set_dragging(True)

    def _on_docs_drag_leave(self) -> None:
        self.docs_zone.set_dragging(False)

    def _on_docs_drop(self, paths: list[str]) -> None:
        self._on_docs_drag_leave()
        if self._is_running():
            return
        docs, rest = split_documents(paths, SUPPORTED_DOC_EXTENSIONS | {".doc"})
        added = self._append_documents(docs)
        if rest and not docs:
            self.status_var.set("Ahí solo se aceptan documentos PDF, Word, Markdown o texto. "
                                "El video va en el recuadro de arriba.")
        elif docs:
            self.status_var.set(f"Documentos agregados para las flashcards: {added}."
                                if added else "Esos documentos ya estaban en la lista.")

    def _add_documents(self) -> None:
        if self._is_running():
            return
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_DOC_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            title="Elige documentos para las flashcards",
            filetypes=[("PDF, Word, Markdown o texto", exts), ("Todos los archivos", "*.*")])
        self._append_documents([Path(p) for p in paths])

    def _append_documents(self, paths: list[Path]) -> int:
        added = 0
        for path in paths:
            if path.suffix.lower() not in SUPPORTED_DOC_EXTENSIONS and path.suffix.lower() != ".doc":
                continue
            if path not in self.documents:
                self.documents.append(path)
                self.docs_list.insert("end", path.name)
                added += 1
        if added:
            self.result_frame.grid_remove()
            self.progress["value"] = 0
        self._refresh_documents()
        return added

    def _remove_documents(self) -> None:
        if self._is_running():
            return
        for index in reversed(self.docs_list.curselection()):
            self.docs_list.delete(index)
            del self.documents[index]
        self._refresh_documents()

    def _choose_file(self) -> None:
        if self._is_running():
            return
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        path = filedialog.askopenfilename(
            title="Elige un video o audio",
            filetypes=[("Video y audio", exts), ("Todos los archivos", "*.*")])
        if path:
            self._set_source(path)

    def _set_source(self, path: str, message: str = "") -> None:
        self.file_var.set(path)
        self.drop_zone.set_file(Path(path).name)
        self.result_frame.grid_remove()
        self.progress["value"] = 0
        self.status_var.set(message or "Listo para empezar.")
        self._update_start_label()

    def _clear_source(self) -> None:
        if self._is_running() or not self.file_var.get():
            return
        self.file_var.set("")
        self.drop_zone.set_file("")
        self.result_frame.grid_remove()
        self.progress["value"] = 0
        self.status_var.set("Listo para empezar.")
        self._update_start_label()

    def _is_running(self) -> bool:
        return bool(self.worker and self.worker.is_alive())

    def _on_drag_enter(self) -> None:
        if self._is_running():
            return
        self.drop_zone.set_dragging(True)
        if self._status_before_drag is None:
            self._status_before_drag = self.status_var.get()
        self.status_var.set("Suelta el archivo para elegirlo.")

    def _on_drag_leave(self) -> None:
        self.drop_zone.set_dragging(False)
        if self._status_before_drag is not None:
            self.status_var.set(self._status_before_drag)
            self._status_before_drag = None

    def _on_drop(self, paths: list[str]) -> None:
        self._on_drag_leave()
        if self._is_running():
            return
        docs, paths = split_documents(paths, SUPPORTED_DOC_EXTENSIONS)
        if docs:
            if not self.cards_var.get():
                self.cards_var.set(True)
                self._on_cards_toggled()
            added = self._append_documents(docs)
            if not paths:
                self.status_var.set(f"Documentos agregados para las flashcards: {added}."
                                    if added else "Esos documentos ya estaban en la lista.")
                return
        path, message = choose_dropped(paths, SUPPORTED_EXTENSIONS)
        if path is None:
            self.status_var.set(message)
            return
        self._set_source(str(path), message)

    def _record_cost(self, report: CostReport) -> None:
        """Suma el costo al acumulado y muestra el desglose."""
        self.settings.total_spent = float(self.settings.total_spent) + report.total
        try:
            self.store.save(self.settings)
        except OSError:
            log.exception("No se pudo guardar el costo acumulado")
        self._render_cost(report)

    def _render_cost(self, report: CostReport) -> None:
        for child in self.cost_frame.winfo_children():
            child.destroy()
        row = 0
        for line in report.lines:
            ttk.Label(self.cost_frame, text=line.label).grid(row=row, column=0, sticky="w")
            ttk.Label(self.cost_frame, text=line.detail, style="Muted.TLabel").grid(
                row=row, column=1, sticky="w", padx=(10, 0))
            ttk.Label(self.cost_frame, text=format_usd(line.amount)).grid(
                row=row, column=2, sticky="e")
            row += 1
        ttk.Separator(self.cost_frame).grid(row=row, column=0, columnspan=3, sticky="ew", pady=4)
        row += 1
        ttk.Label(self.cost_frame, text="Total", font=("TkDefaultFont", 10, "bold")).grid(
            row=row, column=0, sticky="w")
        ttk.Label(self.cost_frame, text=format_usd(report.total),
                  font=("TkDefaultFont", 10, "bold")).grid(row=row, column=2, sticky="e")
        row += 1
        footer = ttk.Frame(self.cost_frame)
        footer.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, style="Muted.TLabel",
                  text=f"Acumulado en este equipo: {format_usd(self.settings.total_spent)}  ·  "
                       "Estimación; el cobro real está en platform.openai.com/usage"
                  ).grid(row=0, column=0, sticky="w")
        reset = ttk.Label(footer, text="Reiniciar", style="Link.TLabel", cursor="hand2")
        reset.grid(row=0, column=1, sticky="e", padx=(8, 0))
        reset.bind("<Button-1>", lambda _e: self._reset_total(report))

    def _reset_total(self, report: CostReport) -> None:
        if not messagebox.askyesno(APP_NAME, "¿Reiniciar el costo acumulado a $0?"):
            return
        self.settings.total_spent = 0.0
        try:
            self.store.save(self.settings)
        except OSError:
            log.exception("No se pudo guardar el costo acumulado")
        self._render_cost(report)

    def _show_anki_help(self) -> None:
        messagebox.showinfo(
            "Importar en Anki",
            "1. Abre Anki en tu computadora.\n"
            "2. Menú Archivo → Importar… y elige el archivo *_flashcards_anki.csv.\n"
            "3. Elige el mazo, revisa que el separador sea «Coma» y el tipo de nota "
            "«Básico», y pulsa Importar.")

    def _choose_outdir(self) -> None:
        folder = filedialog.askdirectory(title="Carpeta donde guardar la transcripción")
        self.outdir_var.set(folder or SAME_FOLDER)

    def _open_settings(self, message: str = "") -> None:
        SettingsDialog(self.root, self.settings, self.store, self._on_settings_saved, message)

    def _on_settings_saved(self, settings: Settings) -> None:
        self.settings = settings
        if settings.theme != current_theme().key:
            self._apply_theme(get_theme(settings.theme))
        self.status_var.set("Configuración guardada.")

    def _apply_theme(self, theme) -> None:
        """Cambia el tema en vivo, sin reiniciar la app."""
        apply_theme(self.root, theme)
        self._style_classic_widgets()
        self.scroller.refresh_theme()
        self.drop_zone.refresh_theme()
        self.docs_zone.refresh_theme()

    def _style_classic_widgets(self) -> None:
        """Los widgets tk clásicos no siguen el tema ttk: se colorean a mano."""
        theme = current_theme()
        style_text(self.context_text, theme)
        style_text(self.outcomes_text, theme)
        style_listbox(self.docs_list, theme)

    def _open(self, path: Optional[Path]) -> None:
        if path and path.exists():
            try:
                open_path(path)
            except OSError as exc:
                messagebox.showerror(APP_NAME, f"No se pudo abrir: {exc}")

    def _save_preferences(self) -> None:
        self.settings.output_format = self.format_var.get()
        self.settings.language = dict(LANGUAGES).get(self.lang_var.get(), "es")
        self.settings.include_timestamps = self.ts_var.get()
        outdir = self.outdir_var.get()
        self.settings.output_dir = "" if outdir == SAME_FOLDER else outdir
        self.settings.context = self.context_text.get("1.0", "end").strip()
        self.settings.correct_with_context = self.correct_var.get()
        self.settings.make_flashcards = self.cards_var.get()
        self.settings.flashcards_include_video = self.include_video_var.get()
        self.settings.learning_outcomes = self.outcomes_text.get("1.0", "end").strip()
        try:
            self.store.save(self.settings)
        except OSError:
            log.exception("No se pudieron guardar las preferencias")

    def _start(self) -> None:
        source = self.file_var.get()
        docs_only = self._docs_only()
        if not source and not docs_only:
            messagebox.showinfo(APP_NAME, "Primero elige un video, o marca «Crear flashcards» "
                                          "y agrega documentos.")
            return
        if not self.settings.effective_api_key():
            self._open_settings("Para usar la IA necesitas una API key de OpenAI.")
            return
        self._save_preferences()
        include_video = docs_only or self.settings.flashcards_include_video
        if self.settings.make_flashcards and not docs_only and not include_video \
                and not self.documents:
            messagebox.showinfo(APP_NAME, "Desmarcaste «Usar también el contenido del video» pero no "
                                          "hay documentos: las flashcards no tendrían material.\n\n"
                                          "Agrega documentos o vuelve a marcar la opción.")
            return
        context = self.settings.context
        if self.settings.correct_with_context and not context and not docs_only:
            if not messagebox.askyesno(
                    APP_NAME, "Marcaste «Revisar el texto con IA» pero el contexto está vacío, "
                              "así que no se hará la revisión.\n\n¿Continuar sin revisión?"):
                self.context_text.focus_set()
                return

        try:
            if docs_only:
                pipeline = TranscriptionPipeline(None,
                                                 flashcards=create_flashcard_generator(self.settings),
                                                 prices=self.settings.prices())
            else:
                pipeline = TranscriptionPipeline(create_transcriber(self.settings),
                                                 create_corrector(self.settings),
                                                 create_flashcard_generator(self.settings),
                                                 self.settings.prices(),
                                                 cache=ChunkCache(chunk_cache_dir()))
        except TranscriptorError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return

        self.cancel_event = threading.Event()
        options = ExportOptions(include_timestamps=self.settings.include_timestamps)
        output_dir = Path(self.settings.output_dir) if self.settings.output_dir else None
        documents = list(self.documents) if self.settings.make_flashcards else []
        self.worker = threading.Thread(
            target=self._work, daemon=True,
            args=(pipeline, Path(source) if source else None, self.settings.output_format,
                  output_dir, self.settings.language, options, self.cancel_event, context,
                  documents, self.settings.learning_outcomes, include_video))
        self._set_running(True)
        self.worker.start()

    def _work(self, pipeline, source, fmt, output_dir, language, options, cancel_event,
              context, documents, outcomes, include_video) -> None:
        """Se ejecuta en el hilo secundario: nunca toca widgets directamente."""
        on_progress = lambda pct, msg: self.events.put(("progress", pct, msg))  # noqa: E731
        try:
            if source is None:
                out = pipeline.run_flashcards(documents, output_dir, language, on_progress,
                                              cancel_event, context, outcomes)
            else:
                out = pipeline.run(source, fmt, output_dir, language, options,
                                   on_progress=on_progress, cancel_event=cancel_event,
                                   context=context, documents=documents,
                                   learning_outcomes=outcomes,
                                   flashcards_from_video=include_video)
            self.events.put(("done", out, list(pipeline.warnings),
                             pipeline.flashcards_path, pipeline.flashcards_count, pipeline.cost))
        except CancelledError:
            self.events.put(("cancelled",))
        except TranscriptorError as exc:
            self.events.put(("error", str(exc)))
        except Exception as exc:  # error inesperado: se registra para soporte
            log.exception("Error inesperado al procesar %s", source or documents)
            self.events.put(("error", f"Error inesperado: {exc}\n\nDetalles en: {log_path()}"))

    def _cancel(self) -> None:
        if self.cancel_event:
            self.cancel_event.set()
            self.cancel_btn.configure(state="disabled")
            self.status_var.set("Cancelando… se detendrá al terminar el paso actual.")

    def _set_running(self, running: bool) -> None:
        self.start_btn.configure(state="disabled" if running else "normal")
        self.choose_btn.configure(state="disabled" if running else "normal")
        self.clear_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")
        self.drop_zone.set_enabled(not running)
        self.docs_zone.set_enabled(not running)
        self.remove_doc_btn.configure(state="disabled" if running else "normal")
        self.include_video_chk.configure(state="disabled" if running else "normal")
        if running:
            self.result_frame.grid_remove()
            self.progress["value"] = 0

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    self.progress["value"] = event[1]
                    self.status_var.set(event[2])
                elif kind == "done":
                    self.last_output = event[1]
                    self._set_running(False)
                    self.progress["value"] = 100
                    cards_path, cards_count = event[3], event[4]
                    if cards_path and cards_path == self.last_output:  # solo documentos
                        status = f"Listo. {cards_count} flashcards para Anki en: {cards_path}"
                    else:
                        status = f"Listo. Guardado en: {self.last_output}"
                        if cards_path:
                            status += f"\n{cards_count} flashcards para Anki en: {cards_path.name}"
                    if cards_path:
                        self.anki_help_btn.pack(side="left", padx=(8, 0))
                    else:
                        self.anki_help_btn.pack_forget()
                    self.status_var.set(status)
                    self._record_cost(event[5])
                    self.result_frame.grid()
                    if event[2]:
                        messagebox.showwarning(APP_NAME, "\n\n".join(event[2]))
                elif kind == "cancelled":
                    self._set_running(False)
                    self.progress["value"] = 0
                    self.status_var.set("Proceso cancelado.")
                elif kind == "error":
                    self._set_running(False)
                    self.status_var.set("Ocurrió un error.")
                    messagebox.showerror(APP_NAME, event[1])
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_NAME, "Hay una transcripción en curso. ¿Salir de todos modos?"):
                return
            if self.cancel_event:
                self.cancel_event.set()
        self.root.destroy()


def set_window_icon(root: tk.Tk) -> None:
    """Icono de la ventana y de la barra de tareas."""
    try:
        if sys.platform == "win32":
            root.iconbitmap(default=str(resource_path("assets/icon.ico")))
        else:
            root._icon_img = tk.PhotoImage(file=str(resource_path("assets/icon.png")))  # type: ignore[attr-defined]
            root.iconphoto(True, root._icon_img)  # type: ignore[attr-defined]
    except (tk.TclError, OSError):
        log.warning("No se pudo cargar el icono", exc_info=True)


def log_path() -> Path:
    return config_dir() / "transcriptor.log"


def run() -> int:
    log_file = log_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_file, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if sys.platform == "win32":
        try:  # texto nítido en pantallas con escalado
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            # Que la barra de tareas muestre el icono de la app y no el de Python
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_NAME}.App")
        except Exception:
            pass
    root, dnd_available = create_root()
    set_window_icon(root)
    MainWindow(root, SettingsStore(), dnd_available)
    root.mainloop()
    return 0
