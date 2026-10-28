"""Eigenes Hintergrundbild für den Launcher: einlesen, zuschneiden (cover), abdunkeln.

Hinweis: Tk/CustomTkinter kennt keine halbtransparenten Widgets. Das Bild erscheint deshalb als Banner über
dem Seiteninhalt und nicht hinter den Karten.
"""
import os

from PIL import Image, ImageEnhance

MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 60_000_000


class BackgroundError(Exception):
    """Fehlertext darf dem Nutzer angezeigt werden."""


def check(path: str) -> None:
    if not path or not os.path.isfile(path):
        raise BackgroundError("The image file was not found.")
    if os.path.getsize(path) > MAX_BYTES:
        raise BackgroundError("The image is larger than 25 MB.")
    try:
        with Image.open(path) as im:
            w, h = im.size
            if w * h > MAX_PIXELS:
                raise BackgroundError("The image has too many pixels (maximum 60 megapixels).")
            im.verify()
    except BackgroundError:
        raise
    except Exception:
        raise BackgroundError("This file is not a readable image.") from None


def render(path: str, width: int, height: int, dim: int = 40) -> Image.Image:
    """Bild so skalieren, dass es die Fläche füllt (mittig zugeschnitten), und um `dim` Prozent abdunkeln."""
    check(path)
    with Image.open(path) as im:
        im = im.convert("RGB")
    scale = max(width / im.width, height / im.height)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    left, top = (im.width - width) // 2, (im.height - height) // 2
    im = im.crop((left, top, left + width, top + height))
    dim = max(0, min(80, int(dim)))
    if dim:
        im = ImageEnhance.Brightness(im).enhance(1 - dim / 100)
    return im
