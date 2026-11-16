"""Genera el icono de la app en assets/ (icon.png e icon.ico).

Diseño: fondo azul redondeado con un documento blanco; en el documento,
un botón de "play" (el video) y líneas de texto (la transcripción).

    python tools/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
S = 1024           # tamaño final del PNG maestro
SS = 4             # sobremuestreo para bordes suaves
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]

TOP, BOTTOM = (59, 130, 246), (30, 64, 175)   # degradado azul
BLUE = (37, 99, 235)
LINE = (148, 163, 184)
FOLD = (219, 228, 240)


def render(size: int) -> Image.Image:
    n = size * SS

    def px(v: float) -> int:
        return round(v * n)

    # Fondo: degradado vertical recortado con un cuadrado redondeado
    grad = Image.new("RGB", (1, n))
    for y in range(n):
        t = y / (n - 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)))
    grad = grad.resize((n, n))
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle((px(.04), px(.04), px(.96), px(.96)),
                                           radius=px(.22), fill=255)
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # Documento con esquina doblada
    l, t, r, b, f = .25, .17, .75, .83, .13
    d.rounded_rectangle((px(l), px(t), px(r), px(b)), radius=px(.045), fill="white")
    d.polygon([(px(r - f), px(t)), (px(r), px(t)), (px(r), px(t + f))], fill=BOTTOM)
    d.polygon([(px(r - f), px(t)), (px(r), px(t + f)), (px(r - f), px(t + f))], fill=FOLD)

    # Botón de play
    cx, cy, rad = .43, .37, .095
    d.ellipse((px(cx - rad), px(cy - rad), px(cx + rad), px(cy + rad)), fill=BLUE)
    d.polygon([(px(cx - .03), px(cy - .045)), (px(cx - .03), px(cy + .045)),
               (px(cx + .05), px(cy))], fill="white")

    # Líneas de texto
    lw = .045
    for y, x_end, color in ((.54, .66, BLUE), (.635, .66, LINE), (.73, .56, LINE)):
        d.rounded_rectangle((px(.33), px(y), px(x_end), px(y + lw)), radius=px(lw / 2), fill=color)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    master = render(S)
    master.save(ASSETS / "icon.png")
    # Cada tamaño se dibuja aparte para que los pequeños queden nítidos
    frames = [render(s) for s in ICO_SIZES]
    frames[-1].save(ASSETS / "icon.ico", sizes=[(s, s) for s in ICO_SIZES],
                    append_images=frames[:-1])
    print(f"Iconos generados en {ASSETS}")


if __name__ == "__main__":
    main()
