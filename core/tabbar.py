"""Reiterleiste, die bei schmalem Fenster in mehrere Zeilen umbricht (statt zusammengequetscht zu werden)."""
import customtkinter as ctk

from core import theme


class WrapTabs(ctk.CTkFrame):
    """Gleiche Bedienung wie CTkSegmentedButton: values, command, set(), get()."""

    def __init__(self, parent, values, command=None):
        super().__init__(parent, fg_color="transparent")
        self._values, self._command, self._value = list(values), command, None
        self._btns = {}
        self._cols = 0
        self._job = None
        for v in self._values:
            self._btns[v] = ctk.CTkButton(self, text=v, height=30, corner_radius=8, border_width=0,
                                          command=lambda v=v: self._pick(v))
        self.bind("<Configure>", self._on_configure)
        self._layout(max(1, len(self._values)))

    def _pick(self, v):
        self.set(v)
        if self._command:
            self._command(v)

    def set(self, v):
        self._value = v
        for k, b in self._btns.items():
            on = k == v
            b.configure(fg_color=theme.accent() if on else theme.c("card"),
                        text_color=theme.contrast_text(theme.accent()) if on else theme.TEXT,
                        hover_color=theme.c("hover"))

    def get(self):
        return self._value

    @staticmethod
    def columns_for(width: int, widths: list[int]) -> int:
        """Wie viele Knöpfe passen (bei gleichmäßigem Raster) in eine Zeile."""
        if not widths:
            return 1
        cell = max(widths) + 8
        return max(1, min(len(widths), width // cell))

    def _on_configure(self, e):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(80, lambda w=e.width: self._relayout(w))

    def _relayout(self, width):
        self._job = None
        try:
            widths = [b.winfo_reqwidth() for b in self._btns.values()]
            cols = self.columns_for(width, widths)
            if cols != self._cols:
                self._layout(cols)
        except Exception:
            pass

    def _layout(self, cols):
        self._cols = cols
        for i, v in enumerate(self._values):
            self._btns[v].grid(row=i // cols, column=i % cols, padx=(0, 6), pady=(0, 6), sticky="w")
        if self._value is not None:
            self.set(self._value)
