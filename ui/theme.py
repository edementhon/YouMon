"""One place for colours, fonts and sizes.

Tk looks dated mostly by default rather than by necessity: the stock widgets
draw 3D bevels, and "Helvetica" is an alias that quietly resolves to whatever
the system has lying around (Bitstream Vera on the Pi). Picking a real font and
drawing everything flat gets most of the way to looking deliberate.

Sizes are deliberately large. The user is six.
"""
from __future__ import annotations
import tkinter.font as tkfont

# Deep blue-purple, kept from the original so his existing cards still look at
# home in it.
BG = "#171a3a"          # window background
PANEL = "#232755"       # the form panel
PANEL_ALT = "#1b1e46"   # drawer and preview
FIELD = "#323875"       # text input background
FIELD_FOCUS = "#434a95" # text input while focused
BORDER = "#3d4488"

TEXT = "#ffffff"
TEXT_DIM = "#c2c6e8"
MUTED = "#7b81b0"

ACCENT = "#ff6b35"        # Generate button
ACCENT_HOVER = "#ff8355"
ACCENT_DISABLED = "#6b6f95"
SECONDARY = "#9b59b6"     # Remix button
SECONDARY_HOVER = "#b06fcb"
GOLD = "#ffd700"          # selection highlight
ERROR = "#ff5a5a"

# Preference order. DejaVu Sans is present on the Pi, on Debian generally, and
# has a sane fallback everywhere else.
_FAMILY_PREFERENCE = (
    "DejaVu Sans", "Liberation Sans", "Nimbus Sans", "FreeSans",
    "Helvetica Neue", "Arial",
)

_family: str | None = None


def family() -> str:
    """Best available font family. Call only after a Tk root exists."""
    global _family
    if _family is None:
        try:
            available = set(tkfont.families())
        except Exception:
            available = set()
        _family = next(
            (f for f in _FAMILY_PREFERENCE if f in available), "TkDefaultFont"
        )
    return _family


def font(size: int, bold: bool = False, italic: bool = False):
    style = []
    if bold:
        style.append("bold")
    if italic:
        style.append("italic")
    return (family(), size, " ".join(style)) if style else (family(), size)


# Named sizes, so a tweak lands everywhere at once.
TITLE = 20
HEADING = 15
LABEL = 13
INPUT = 15
BUTTON = 20
BUTTON_SMALL = 13
SMALL = 11
TINY = 9


def style_entry(widget):
    """Flat, chunky text input that shows focus."""
    widget.configure(
        bg=FIELD, fg=TEXT, insertbackground=TEXT,
        relief="flat", bd=0,
        highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT,
    )
    widget.bind("<FocusIn>", lambda e: widget.configure(bg=FIELD_FOCUS), add="+")
    widget.bind("<FocusOut>", lambda e: widget.configure(bg=FIELD), add="+")


def style_button(widget, base: str, hover: str):
    """Hover feedback on the Label-based buttons.

    They are Labels rather than Buttons because tk.Button ignores background
    colour on macOS, and this has to look the same on both.
    """
    widget.configure(bg=base, relief="flat", bd=0)

    def enter(_e):
        if widget.cget("cursor") != "watch":
            widget.configure(bg=hover)

    def leave(_e):
        if widget.cget("cursor") != "watch":
            widget.configure(bg=base)

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", leave, add="+")
