import tkinter as tk
from PIL import Image, ImageTk
import config

# Animated spinner frames
SPINNER_FRAMES = [
    "Creating your monster     ",
    "Creating your monster .   ",
    "Creating your monster ..  ",
    "Creating your monster ... ",
]


class CardPreviewPanel:
    """Displays the current card image at preview resolution."""

    def __init__(self, parent: tk.Widget):
        self.frame = tk.Frame(
            parent, bg="#1e1e3f",
            width=config.PREVIEW_WIDTH + 20,
        )
        self.frame.pack_propagate(False)  # Keep fixed width
        self._photo_ref = None
        self._spinner_active = False
        self._spinner_idx = 0
        self._elapsed = 0

        self.on_click = None  # Callback set by app_window for flip-on-click

        self.label = tk.Label(
            self.frame, bg="#1e1e3f",
            text="Your card will\nappear here!",
            font=("Helvetica", 13), fg="#666",
            cursor="hand2",
        )
        self.label.pack(padx=10, pady=10, expand=True)
        self.label.bind("<Button-1>", self._handle_click)

        self.hint_label = tk.Label(
            self.frame, text="", font=("Helvetica", 9),
            fg="#888", bg="#1e1e3f"
        )
        self.hint_label.pack(pady=(0, 5))

    def _handle_click(self, event=None):
        if self.on_click and self._photo_ref:
            self.on_click()

    def show_image(self, pil_image: Image.Image, side: str = "front"):
        """Display a PIL image scaled to preview size."""
        self._stop_spinner()
        # Scale to fit preview width, maintain aspect ratio
        ratio = config.PREVIEW_WIDTH / pil_image.width
        new_h = int(pil_image.height * ratio)
        preview = pil_image.resize((config.PREVIEW_WIDTH, new_h), Image.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(preview)
        self.label.configure(image=self._photo_ref, text="")
        if side == "front":
            self.hint_label.configure(text="Click card to see back")
        else:
            self.hint_label.configure(text="Click card to see front")

    def show_loading(self):
        self._photo_ref = None
        self._elapsed = 0
        self._spinner_idx = 0
        self._spinner_active = True
        self._animate_spinner()

    def _animate_spinner(self):
        if not self._spinner_active:
            return
        frame = SPINNER_FRAMES[self._spinner_idx % len(SPINNER_FRAMES)]
        elapsed_text = f"\n\n{self._elapsed}s elapsed"
        self.label.configure(
            image="", text=frame + elapsed_text,
            font=("Helvetica", 13), fg="#ff6b35",
        )
        self._spinner_idx += 1
        # Update elapsed time every 4th frame (every 2 seconds)
        if self._spinner_idx % 4 == 0:
            self._elapsed += 2
        self.label.after(500, self._animate_spinner)

    def _stop_spinner(self):
        self._spinner_active = False

    def show_error(self, message: str):
        self._stop_spinner()
        self._photo_ref = None
        self.label.configure(
            image="", text=message,
            font=("Helvetica", 11), fg="#ff4444"
        )
