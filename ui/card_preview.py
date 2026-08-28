from __future__ import annotations
import tkinter as tk
from PIL import Image, ImageTk
import config
from ui import theme

# Generation takes about a minute. Rather than a spinner that says nothing,
# walk through what is actually happening so the wait feels like progress.
# (seconds elapsed, message)
STAGES = [
    (0, "Thinking up your monster..."),
    (8, "Designing its attacks..."),
    (20, "Drawing the picture..."),
    (38, "Adding the colors..."),
    (52, "Putting it on a card..."),
    (70, "Almost there..."),
    (100, "Any second now..."),
]

# Used to pace the bar. It creeps toward the end rather than pretending to
# finish, so it never sits at 100% while still working.
EXPECTED_SECONDS = 62.0

BAR_H = 14


class CardPreviewPanel:
    """Displays the current card image at preview resolution."""

    def __init__(self, parent: tk.Widget):
        self.frame = tk.Frame(
            parent, bg=theme.PANEL_ALT,
            width=config.PREVIEW_WIDTH + 24,
        )
        self.frame.pack_propagate(False)
        self._photo_ref = None
        self._busy = False
        self._elapsed = 0.0
        self._after_id = None

        self.on_click = None  # set by app_window for flip-on-click

        self.label = tk.Label(
            self.frame, bg=theme.PANEL_ALT,
            text="Your card will\nappear here!",
            font=theme.font(theme.HEADING), fg=theme.MUTED,
            cursor="hand2",
        )
        self.label.pack(padx=12, pady=(12, 6), expand=True)
        self.label.bind("<Button-1>", self._handle_click)

        # Progress bar, drawn rather than ttk so it matches the rest.
        self.bar = tk.Canvas(
            self.frame, height=BAR_H, bg=theme.FIELD,
            highlightthickness=0, bd=0,
        )
        self._bar_fill = self.bar.create_rectangle(
            0, 0, 0, BAR_H, fill=theme.ACCENT, width=0,
        )

        self.hint_label = tk.Label(
            self.frame, text="", font=theme.font(theme.SMALL),
            fg=theme.MUTED, bg=theme.PANEL_ALT,
        )
        self.hint_label.pack(pady=(0, 10))

    def _handle_click(self, event=None):
        if self.on_click and self._photo_ref:
            self.on_click()

    # --- states ----------------------------------------------------------

    def show_image(self, pil_image: Image.Image, side: str = "front"):
        """Display a PIL image scaled to preview size."""
        self._stop()
        ratio = config.PREVIEW_WIDTH / pil_image.width
        new_h = int(pil_image.height * ratio)
        preview = pil_image.resize((config.PREVIEW_WIDTH, new_h), Image.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(preview)
        self.label.configure(image=self._photo_ref, text="")
        self.hint_label.configure(
            text="Click the card to see the back" if side == "front"
            else "Click the card to see the front"
        )

    def show_loading(self):
        self._photo_ref = None
        self._elapsed = 0.0
        self._busy = True
        self.bar.pack(fill=tk.X, padx=12, pady=(0, 6), before=self.hint_label)
        self._tick()

    def _tick(self):
        if not self._busy:
            return
        message = STAGES[0][1]
        for at, text in STAGES:
            if self._elapsed >= at:
                message = text

        self.label.configure(
            image="", text=message,
            font=theme.font(theme.HEADING, bold=True), fg=theme.ACCENT,
        )
        self.hint_label.configure(text=f"{int(self._elapsed)}s")

        # Asymptotic: covers 90% over the expected duration and keeps
        # creeping after, so a slow run never looks stalled or finished.
        frac = 1.0 - 0.10 ** (self._elapsed / EXPECTED_SECONDS)
        width = max(self.bar.winfo_width(), 1)
        self.bar.coords(self._bar_fill, 0, 0, width * min(frac, 0.99), BAR_H)

        self._elapsed += 0.25
        self._after_id = self.label.after(250, self._tick)

    def _stop(self):
        self._busy = False
        if self._after_id is not None:
            try:
                self.label.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.bar.pack_forget()

    def show_error(self, message: str):
        self._stop()
        self._photo_ref = None
        self.label.configure(
            image="", text=message,
            font=theme.font(theme.LABEL), fg=theme.ERROR,
        )
        self.hint_label.configure(text="")
