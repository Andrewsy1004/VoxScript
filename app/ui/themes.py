"""Temas de color de la interfaz.

El tema «Predeterminado» deja el aspecto nativo del sistema (el de siempre).
Los demás crean un tema ttk propio derivado de «clam» para poder cambiar
todos los colores, incluso en Windows, donde el tema nativo los ignora.
"""

from __future__ import annotations

import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Optional

# Colores del recuadro para soltar archivos: (borde, relleno, título, subtítulo).
# Relleno None = mismo fondo que la ventana.
ZonePalette = tuple[str, Optional[str], str, str]

DEFAULT_THEME = "default"


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    # Colores de texto destacados (se usan también en el tema predeterminado)
    muted: str
    accent: str
    warn: str
    border: str
    focus: str
    zone_idle: ZonePalette
    zone_hover: ZonePalette
    zone_drag: ZonePalette
    zone_done: ZonePalette
    zone_disabled: ZonePalette
    # None = color nativo del sistema (solo el tema predeterminado)
    bg: Optional[str] = None
    fg: Optional[str] = None
    accent_fg: Optional[str] = None
    field_bg: Optional[str] = None
    field_fg: Optional[str] = None
    select_bg: Optional[str] = None
    select_fg: Optional[str] = None
    button_bg: Optional[str] = None
    button_hover: Optional[str] = None
    button_pressed: Optional[str] = None

    @property
    def custom(self) -> bool:
        """True si el tema define sus propios colores de fondo y texto."""
        return self.bg is not None


THEMES: list[Theme] = [
    Theme(
        key=DEFAULT_THEME, label="Predeterminado (sistema)",
        muted="#6B7280", accent="#2563EB", warn="#B45309",
        border="#D1D5DB", focus="#2563EB",
        zone_idle=("#9CA3AF", None, "#374151", "#6B7280"),
        zone_hover=("#2563EB", "#F5F8FF", "#1F2937", "#6B7280"),
        zone_drag=("#2563EB", "#E0EBFF", "#1D4ED8", "#1D4ED8"),
        zone_done=("#16A34A", "#F0FDF4", "#166534", "#6B7280"),
        zone_disabled=("#D1D5DB", None, "#9CA3AF", "#9CA3AF"),
    ),
    Theme(
        key="light", label="Claro",
        bg="#F7F8FA", fg="#1F2937", muted="#6B7280", accent="#2563EB", accent_fg="#FFFFFF",
        field_bg="#FFFFFF", field_fg="#111827", border="#D1D5DB", focus="#2563EB",
        select_bg="#BFDBFE", select_fg="#111827", warn="#B45309",
        button_bg="#FFFFFF", button_hover="#EEF2FF", button_pressed="#E0E7FF",
        zone_idle=("#9CA3AF", None, "#374151", "#6B7280"),
        zone_hover=("#2563EB", "#EEF3FF", "#1F2937", "#6B7280"),
        zone_drag=("#2563EB", "#DCE8FF", "#1D4ED8", "#1D4ED8"),
        zone_done=("#16A34A", "#ECFDF3", "#166534", "#6B7280"),
        zone_disabled=("#D1D5DB", None, "#9CA3AF", "#9CA3AF"),
    ),
    Theme(
        key="dark", label="Oscuro",
        bg="#1E1F22", fg="#E5E7EB", muted="#9CA3AF", accent="#60A5FA", accent_fg="#0B1220",
        field_bg="#2B2D31", field_fg="#F3F4F6", border="#3F4248", focus="#60A5FA",
        select_bg="#1D4ED8", select_fg="#FFFFFF", warn="#FBBF24",
        button_bg="#2F3136", button_hover="#3A3D43", button_pressed="#45484F",
        zone_idle=("#6B7280", None, "#E5E7EB", "#9CA3AF"),
        zone_hover=("#60A5FA", "#24303F", "#F3F4F6", "#9CA3AF"),
        zone_drag=("#60A5FA", "#1E3A5F", "#BFDBFE", "#BFDBFE"),
        zone_done=("#22C55E", "#16291E", "#86EFAC", "#9CA3AF"),
        zone_disabled=("#3F4248", None, "#6B7280", "#6B7280"),
    ),
    Theme(
        key="midnight", label="Medianoche (azul oscuro)",
        bg="#0F172A", fg="#E2E8F0", muted="#94A3B8", accent="#38BDF8", accent_fg="#082F49",
        field_bg="#1E293B", field_fg="#F1F5F9", border="#334155", focus="#38BDF8",
        select_bg="#0369A1", select_fg="#FFFFFF", warn="#FBBF24",
        button_bg="#1E293B", button_hover="#273449", button_pressed="#334155",
        zone_idle=("#475569", None, "#E2E8F0", "#94A3B8"),
        zone_hover=("#38BDF8", "#13243A", "#F1F5F9", "#94A3B8"),
        zone_drag=("#38BDF8", "#0C3350", "#BAE6FD", "#BAE6FD"),
        zone_done=("#34D399", "#0F2A26", "#6EE7B7", "#94A3B8"),
        zone_disabled=("#334155", None, "#64748B", "#64748B"),
    ),
    Theme(
        key="sepia", label="Sepia (cálido)",
        bg="#F4ECD8", fg="#3B2F2A", muted="#7A6A58", accent="#9A5B1E", accent_fg="#FFFFFF",
        field_bg="#FBF6EA", field_fg="#2E241F", border="#D9CBAE", focus="#9A5B1E",
        select_bg="#E8D3A8", select_fg="#2E241F", warn="#A23B16",
        button_bg="#FBF6EA", button_hover="#EFE3C8", button_pressed="#E6D6B4",
        zone_idle=("#B8A684", None, "#4A3B32", "#7A6A58"),
        zone_hover=("#9A5B1E", "#F8EBD3", "#3B2F2A", "#7A6A58"),
        zone_drag=("#9A5B1E", "#F1DDB8", "#7A4416", "#7A4416"),
        zone_done=("#4D7C3A", "#EEF2DE", "#3D5F2E", "#7A6A58"),
        zone_disabled=("#D9CBAE", None, "#B0A08A", "#B0A08A"),
    ),
    Theme(
        key="contrast", label="Alto contraste",
        bg="#000000", fg="#FFFFFF", muted="#D1D5DB", accent="#FFD400", accent_fg="#000000",
        field_bg="#000000", field_fg="#FFFFFF", border="#FFFFFF", focus="#FFD400",
        select_bg="#FFD400", select_fg="#000000", warn="#FF9F1C",
        button_bg="#000000", button_hover="#262626", button_pressed="#404040",
        zone_idle=("#FFFFFF", None, "#FFFFFF", "#D1D5DB"),
        zone_hover=("#FFD400", "#1A1A00", "#FFFFFF", "#FFFFFF"),
        zone_drag=("#FFD400", "#333000", "#FFD400", "#FFD400"),
        zone_done=("#00E676", "#002A14", "#00E676", "#FFFFFF"),
        zone_disabled=("#6B6B6B", None, "#9E9E9E", "#9E9E9E"),
    ),
]

_BY_KEY = {t.key: t for t in THEMES}


def get_theme(key: str) -> Theme:
    """Tema por su clave; si no existe (config vieja o dañada), el predeterminado."""
    return _BY_KEY.get(key, _BY_KEY[DEFAULT_THEME])


def theme_by_label(label: str) -> Theme:
    return next((t for t in THEMES if t.label == label), _BY_KEY[DEFAULT_THEME])


# ---------- aplicación ----------

_current: Theme = _BY_KEY[DEFAULT_THEME]
_native: dict[str, str] = {}  # colores y tema ttk originales del sistema


def current_theme() -> Theme:
    return _current


def _capture_native(root: tk.Misc, style: ttk.Style) -> None:
    if _native:
        return
    _native["ttk_theme"] = "clam" if sys.platform.startswith("linux") else style.theme_use()
    _native["root_bg"] = root.cget("background")
    probe = tk.Text(root)
    for opt in ("background", "foreground", "insertbackground",
                "selectbackground", "selectforeground"):
        _native[opt] = probe.cget(opt)
    probe.destroy()


def text_colors(theme: Theme) -> dict[str, str]:
    """Colores para widgets tk clásicos (Text, Listbox)."""
    return {
        "background": theme.field_bg or _native["background"],
        "foreground": theme.field_fg or _native["foreground"],
        "selectbackground": theme.select_bg or _native["selectbackground"],
        "selectforeground": theme.select_fg or _native["selectforeground"],
    }


def style_text(widget: tk.Text, theme: Theme) -> None:
    widget.configure(insertbackground=theme.field_fg or _native["insertbackground"],
                     highlightbackground=theme.border, highlightcolor=theme.focus,
                     **text_colors(theme))


def style_listbox(widget: tk.Listbox, theme: Theme) -> None:
    widget.configure(**text_colors(theme))


def window_background(root: tk.Misc) -> str:
    """Fondo de ventana del tema activo (para Canvas y Toplevel)."""
    return ttk.Style(root).lookup("TFrame", "background") or root.winfo_toplevel().cget("bg")


def apply_theme(root: tk.Misc, theme: Theme) -> None:
    """Aplica el tema a todos los estilos ttk. Los widgets tk clásicos se
    actualizan aparte (style_text / style_listbox)."""
    global _current
    style = ttk.Style(root)
    _capture_native(root, style)

    if theme.custom:
        name = f"transcriptor-{theme.key}"
        if name not in style.theme_names():
            style.theme_create(name, parent="clam")
        style.theme_use(name)
        _configure_custom(style, theme)
    else:
        style.theme_use(_native["ttk_theme"])

    # Estilos propios de la app (se definen de nuevo en cada tema ttk)
    style.configure("Title.TLabel", font=("TkDefaultFont", 16, "bold"))
    style.configure("Muted.TLabel", foreground=theme.muted)
    style.configure("Link.TLabel", foreground=theme.accent)
    style.configure("Warn.TLabel", foreground=theme.warn)
    style.configure("Primary.TButton", font=("TkDefaultFont", 10, "bold"), padding=(14, 6))
    if theme.custom:
        style.configure("Primary.TButton", background=theme.accent, foreground=theme.accent_fg,
                        bordercolor=theme.accent)
        style.map("Primary.TButton",
                  background=[("disabled", theme.button_bg), ("pressed", theme.focus),
                              ("active", theme.focus)],
                  foreground=[("disabled", theme.muted)])

    root.configure(background=theme.bg or _native["root_bg"])
    # Lista desplegable del Combobox (es un Listbox clásico)
    colors = text_colors(theme)
    root.option_add("*TCombobox*Listbox.background", colors["background"])
    root.option_add("*TCombobox*Listbox.foreground", colors["foreground"])
    root.option_add("*TCombobox*Listbox.selectBackground", colors["selectbackground"])
    root.option_add("*TCombobox*Listbox.selectForeground", colors["selectforeground"])
    _current = theme


def _configure_custom(style: ttk.Style, t: Theme) -> None:
    style.configure(".", background=t.bg, foreground=t.fg, bordercolor=t.border,
                    darkcolor=t.bg, lightcolor=t.bg, troughcolor=t.field_bg,
                    fieldbackground=t.field_bg, insertcolor=t.field_fg,
                    selectbackground=t.select_bg, selectforeground=t.select_fg,
                    focuscolor=t.focus, arrowcolor=t.fg)
    style.map(".", foreground=[("disabled", t.muted)], background=[("disabled", t.bg)])
    style.configure("TFrame", background=t.bg)
    style.configure("TLabel", background=t.bg, foreground=t.fg)
    style.configure("TLabelframe", background=t.bg, bordercolor=t.border,
                    lightcolor=t.border, darkcolor=t.border)
    style.configure("TLabelframe.Label", background=t.bg, foreground=t.fg)
    style.configure("TSeparator", background=t.border)
    style.configure("TButton", background=t.button_bg, foreground=t.fg, bordercolor=t.border,
                    lightcolor=t.button_bg, darkcolor=t.button_bg, padding=(10, 4))
    style.map("TButton",
              background=[("disabled", t.bg), ("pressed", t.button_pressed),
                          ("active", t.button_hover)],
              foreground=[("disabled", t.muted)],
              bordercolor=[("focus", t.focus)])
    for widget in ("TCheckbutton", "TRadiobutton"):
        style.configure(widget, background=t.bg, foreground=t.fg,
                        indicatorbackground=t.field_bg, indicatorforeground=t.fg,
                        indicatorsize=15, indicatormargin=(0, 0, 8, 0), padding=(0, 2),
                        upperbordercolor=t.muted, lowerbordercolor=t.muted)
        style.map(widget, background=[("active", t.bg)],
                  indicatorbackground=[("selected", t.accent), ("pressed", t.button_pressed)],
                  indicatorforeground=[("selected", t.accent_fg)],
                  foreground=[("disabled", t.muted)])
    for widget in ("TEntry", "TCombobox"):
        style.configure(widget, fieldbackground=t.field_bg, foreground=t.field_fg,
                        bordercolor=t.border, lightcolor=t.field_bg, darkcolor=t.field_bg,
                        insertcolor=t.field_fg)
        style.map(widget,
                  fieldbackground=[("readonly", t.field_bg), ("disabled", t.bg)],
                  foreground=[("disabled", t.muted), ("readonly", t.field_fg)],
                  selectbackground=[("readonly", t.field_bg)],
                  selectforeground=[("readonly", t.field_fg)],
                  bordercolor=[("focus", t.focus)],
                  lightcolor=[("focus", t.focus)])
    style.configure("TCombobox", background=t.button_bg, arrowcolor=t.fg)
    style.map("TCombobox", background=[("active", t.button_hover), ("readonly", t.button_bg)])
    style.configure("TProgressbar", background=t.accent, troughcolor=t.field_bg,
                    bordercolor=t.border, lightcolor=t.accent, darkcolor=t.accent)
    style.configure("Vertical.TScrollbar", background=t.button_bg, troughcolor=t.bg,
                    bordercolor=t.border, arrowcolor=t.fg,
                    lightcolor=t.button_bg, darkcolor=t.button_bg)
    style.map("Vertical.TScrollbar", background=[("active", t.button_hover)])
