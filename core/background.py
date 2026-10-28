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


_CACHE: dict = {}          # (Pfad, Änderungszeit, Breite, Höhe) -> zugeschnittenes Bild (ohne Abdunkeln)


def render(path: str, width: int, height: int, dim: int = 40) -> Image.Image:
    """Bild so skalieren, dass es die Fläche füllt (mittig zugeschnitten), und um `dim` Prozent abdunkeln.
    Das aufwendige Skalieren wird zwischengespeichert: ein Neuaufbau der Oberfläche liest und skaliert das Bild nicht jedes Mal neu."""
    check(path)
    key = (path, os.path.getmtime(path), width, height)
    base = _CACHE.get(key)
    if base is None:
        with Image.open(path) as im:
            im = im.convert("RGB")
        scale = max(width / im.width, height / im.height)
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
        left, top = (im.width - width) // 2, (im.height - height) // 2
        base = im.crop((left, top, left + width, top + height))
        if len(_CACHE) >= 3:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = base
    dim = max(0, min(80, int(dim)))
    return ImageEnhance.Brightness(base).enhance(1 - dim / 100) if dim else base.copy()
