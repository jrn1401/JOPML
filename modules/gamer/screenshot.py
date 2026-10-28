"""Screenshot-Werkzeug: Bereich auswählen und als PNG speichern."""
import datetime
from pathlib import Path


def default_folder() -> Path:
    for name in ("Pictures", "Bilder"):
        p = Path.home() / name
        if p.is_dir():
            return p / "JOPML"
    return Path.home() / "JOPML-Screenshots"


def file_name(now: datetime.datetime | None = None) -> str:
    return "JOPML-" + (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S") + ".png"


def normalize_box(x0, y0, x1, y1, scale: float = 1.0, size: tuple[int, int] | None = None):
    """Zieht eine Auswahl (beliebige Ecken) zu einem Rechteck in Bildpixeln; None, wenn zu klein."""
    l, r = sorted((x0, x1))
    t, b = sorted((y0, y1))
    box = [round(v * scale) for v in (l, t, r, b)]
    if size:
        box = [max(0, min(box[0], size[0])), max(0, min(box[1], size[1])), max(0, min(box[2], size[0])), max(0, min(box[3], size[1]))]
    return tuple(box) if box[2] - box[0] >= 5 and box[3] - box[1] >= 5 else None


def save(img, folder: Path | None = None, now=None) -> Path:
    folder = folder or default_folder()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / file_name(now)
    img.save(path, "PNG")
    return path


def grab_screen():
    from PIL import ImageGrab
    return ImageGrab.grab().convert("RGB")


class RegionSelector:
    """Vollbild-Fenster mit eingefrorenem Bildschirm; mit der Maus einen Bereich ziehen. Esc bricht ab."""

    def __init__(self, app, on_done):
        self.app, self.on_done = app, on_done

    def start(self):
        import tkinter as tk
        from PIL import ImageTk
        shot = grab_screen()
        w = tk.Toplevel(self.app)
        w.overrideredirect(True)
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        w.geometry(f"{sw}x{sh}+0+0")
        w.attributes("-topmost", True)
        scale = shot.width / sw
        view = shot.resize((sw, sh))
        photo = ImageTk.PhotoImage(view)
        c = tk.Canvas(w, width=sw, height=sh, highlightthickness=0, cursor="crosshair")
        c.pack()
        c.create_image(0, 0, image=photo, anchor="nw")
        c.image = photo
        c.create_text(sw // 2, 30, text="Drag to select an area · Esc cancels", fill="white", font=("Helvetica", 16, "bold"))
        st = {"x": 0, "y": 0, "r": None}

        def down(e):
            st["x"], st["y"] = e.x, e.y
            st["r"] = c.create_rectangle(e.x, e.y, e.x, e.y, outline="#22d3ee", width=2)

        def drag(e):
            if st["r"]:
                c.coords(st["r"], st["x"], st["y"], e.x, e.y)

        def up(e):
            box = normalize_box(st["x"], st["y"], e.x, e.y, scale, shot.size)
            w.destroy()
            if box:
                self.on_done(shot.crop(box))
        c.bind("<ButtonPress-1>", down)
        c.bind("<B1-Motion>", drag)
        c.bind("<ButtonRelease-1>", up)
        w.bind("<Escape>", lambda _e: w.destroy())
        w.focus_force()
