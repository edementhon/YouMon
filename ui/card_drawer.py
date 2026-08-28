from __future__ import annotations
import tkinter as tk
import tkinter.font as tkfont
from PIL import ImageTk
from core.card_model import CardData
from core.storage import CardStorage
from ui import theme
import config


class CardDrawerPanel:
    """Scrollable sidebar showing thumbnails of all saved cards.

    Draws canvas items rather than packing a Button per card, and only builds
    the rows currently on screen. Both of those matter once a child has a few
    hundred cards:

    - A packed widget per card made the inner frame taller than X11 can
      address. Window coordinates are 16-bit signed, so past ~32767 pixels
      (about 187 cards) everything landed at wrapped coordinates and piled up
      on top of each other. Searching hid enough rows to drop back under the
      limit, which is why filtering appeared to "fix" it. Canvas items are
      drawn, not windowed, so the ceiling is gone.
    - Building every row up front meant decoding every card image up front.
      Now a row costs nothing until it scrolls into view.
    """

    THUMB_H = config.THUMBNAIL_HEIGHT
    PAD = 4
    LABEL_H = 16
    ROW_H = PAD + THUMB_H + PAD + LABEL_H
    OVERSCAN = 3          # rows to build beyond the viewport, so scrolling is smooth
    PHOTO_CACHE_MAX = 80  # decoded thumbnails held in memory

    def __init__(self, parent: tk.Widget, on_card_selected):
        self.on_card_selected = on_card_selected
        self.storage: CardStorage | None = None
        self._all_cards: list[CardData] = []
        self._visible_cards: list[CardData] = []
        self._rows: dict[int, list[int]] = {}      # row index -> canvas item ids
        self._photos: dict[str, ImageTk.PhotoImage] = {}
        self._photo_order: list[str] = []
        self._selected_id: str | None = None
        self._name_font: tkfont.Font | None = None
        self._last_width = 0

        self.frame = tk.Frame(parent, width=170, bg=theme.PANEL_ALT)
        self.frame.pack_propagate(False)

        tk.Label(
            self.frame, text="My Cards",
            font=theme.font(theme.HEADING, bold=True), fg=theme.TEXT, bg=theme.PANEL_ALT
        ).pack(pady=(10, 5))

        self._count_label = tk.Label(
            self.frame, text="", font=theme.font(theme.TINY), fg=theme.MUTED, bg=theme.PANEL_ALT
        )
        self._count_label.pack()

        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(
            self.frame, textvariable=self._search_var,
            font=theme.font(theme.SMALL), bg=theme.FIELD, fg=theme.TEXT,
            insertbackground=theme.TEXT, width=15, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=theme.BORDER,
            highlightcolor=theme.ACCENT
        )
        self._search_entry.pack(padx=10, pady=(2, 5))
        self._search_placeholder = "Search..."
        self._search_entry.insert(0, self._search_placeholder)
        self._search_entry.config(fg=theme.MUTED)
        self._search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self._search_entry.bind("<FocusOut>", self._on_search_focus_out)

        self.canvas = tk.Canvas(
            self.frame, width=150, bg=theme.PANEL_ALT, highlightthickness=0, bd=0
        )
        self.scrollbar = tk.Scrollbar(
            self.frame, orient=tk.VERTICAL, command=self._on_scrollbar
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", lambda e: self._render())
        self.frame.bind("<Enter>", self._bind_mousewheel)
        self.frame.bind("<Leave>", self._unbind_mousewheel)

        self._empty_id: int | None = None

        # Wired last on purpose: inserting the placeholder text above writes to
        # the StringVar, and a trace attached earlier would fire _filter_cards
        # before the canvas it draws on exists.
        self._search_var.trace_add("write", lambda *_: self._filter_cards())

    # --- scrolling -------------------------------------------------------

    def _on_scrollbar(self, *args):
        self.canvas.yview(*args)
        self._render()

    def _bind_mousewheel(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)   # X11 wheel up
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)   # X11 wheel down

    def _unbind_mousewheel(self, event=None):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(seq)

    def _on_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = int(-event.delta / 120)
        self.canvas.yview_scroll(delta, "units")
        self._render()

    # --- search ----------------------------------------------------------

    def _on_search_focus_in(self, event):
        if self._search_entry.get() == self._search_placeholder:
            self._search_entry.delete(0, tk.END)
            self._search_entry.config(fg=theme.TEXT)

    def _on_search_focus_out(self, event):
        if not self._search_entry.get():
            self._search_entry.insert(0, self._search_placeholder)
            self._search_entry.config(fg=theme.MUTED)

    def _query(self) -> str:
        q = self._search_var.get().lower().strip()
        return "" if q == self._search_placeholder.lower() else q

    def _filter_cards(self):
        q = self._query()
        if q:
            self._visible_cards = [
                c for c in self._all_cards if q in c.monster_name.lower()
            ]
        else:
            self._visible_cards = list(self._all_cards)
        self.canvas.yview_moveto(0)
        self._reset_rows()
        self._render()

    # --- public API ------------------------------------------------------

    def refresh(self, cards: list[CardData], storage: CardStorage):
        """Replace the whole list (startup, or after a delete)."""
        self.storage = storage
        self._all_cards = list(reversed(cards))   # newest first
        self._filter_cards()

    def add_card(self, card: CardData, storage: CardStorage):
        """Put one new card at the top without rebuilding the rest.

        Generating a card used to trigger a full reload of every thumbnail,
        which is why the sidebar took as long to catch up as the app took to
        start.
        """
        self.storage = storage
        self._all_cards.insert(0, card)
        self._filter_cards()

    def select(self, card: CardData | None):
        self._selected_id = card.id if card else None
        self._reset_rows()
        self._render()

    # --- rendering -------------------------------------------------------

    def _reset_rows(self):
        self.canvas.delete("row")
        self._rows.clear()

    def _fit_name(self, name: str, max_px: int) -> str:
        """Trim a monster name to the sidebar width, with an ellipsis.

        Names are centred, so an over-long one used to run off both edges and
        get clipped into nonsense like ":k gust".
        """
        if self._name_font is None:
            self._name_font = tkfont.Font(font=theme.font(theme.SMALL))
        if self._name_font.measure(name) <= max_px:
            return name
        trimmed = name
        while trimmed and self._name_font.measure(trimmed + "\u2026") > max_px:
            trimmed = trimmed[:-1]
        return (trimmed + "\u2026") if trimmed else ""

    def _photo_for(self, card: CardData):
        photo = self._photos.get(card.id)
        if photo is not None:
            return photo
        try:
            thumb = self.storage.load_thumbnail(card)
        except Exception:
            return None
        photo = ImageTk.PhotoImage(thumb)
        self._photos[card.id] = photo
        self._photo_order.append(card.id)
        while len(self._photo_order) > self.PHOTO_CACHE_MAX:
            self._photos.pop(self._photo_order.pop(0), None)
        return photo

    def _render(self):
        if self.storage is None:
            return

        # Before the canvas is mapped winfo_width() reports 1, and rows built
        # at that point centre themselves at x=0 (clipped) with names trimmed to
        # nothing. Wait for a real width, and rebuild if it changes.
        width = self.canvas.winfo_width()
        if width <= 1:
            return
        if width != self._last_width:
            self._last_width = width
            self._reset_rows()

        total = len(self._visible_cards)
        height = max(total * self.ROW_H, 1)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        self._count_label.config(
            text=f"{total} card{'s' if total != 1 else ''}"
            + ("" if not self._query() else f" of {len(self._all_cards)}")
        )

        if total == 0:
            if self._empty_id is None:
                msg = ("No cards yet!\nGenerate your\nfirst card."
                       if not self._all_cards else "No cards match\nyour search.")
                self._empty_id = self.canvas.create_text(
                    width // 2, 40, text=msg, fill=theme.MUTED,
                    font=theme.font(theme.SMALL), justify=tk.CENTER,
                )
            return
        if self._empty_id is not None:
            self.canvas.delete(self._empty_id)
            self._empty_id = None

        top = self.canvas.canvasy(0)
        view_h = self.canvas.winfo_height() or 400
        first = max(0, int(top // self.ROW_H) - self.OVERSCAN)
        last = min(total - 1, int((top + view_h) // self.ROW_H) + self.OVERSCAN)

        for idx in list(self._rows):
            if idx < first or idx > last:
                for item in self._rows.pop(idx):
                    self.canvas.delete(item)

        for idx in range(first, last + 1):
            if idx not in self._rows:
                self._build_row(idx, width)

    def _build_row(self, idx: int, width: int):
        card = self._visible_cards[idx]
        y = idx * self.ROW_H
        cx = width // 2
        items: list[int] = []
        tag = f"card:{card.id}"

        photo = self._photo_for(card)
        if photo is None:
            return

        if card.id == self._selected_id:
            items.append(self.canvas.create_rectangle(
                cx - photo.width() // 2 - 3, y + self.PAD - 3,
                cx + photo.width() // 2 + 3, y + self.PAD + self.THUMB_H + 3,
                outline=theme.GOLD, width=2, tags=("row", tag),
            ))

        items.append(self.canvas.create_image(
            cx, y + self.PAD, image=photo, anchor="n", tags=("row", tag),
        ))
        items.append(self.canvas.create_text(
            cx, y + self.PAD + self.THUMB_H + 2,
            text=self._fit_name(card.monster_name, width - 10),
            fill=theme.TEXT_DIM, font=theme.font(theme.SMALL), anchor="n", tags=("row", tag),
        ))

        self.canvas.tag_bind(tag, "<Button-1>", lambda _e, c=card: self.on_card_selected(c))
        self._rows[idx] = items
