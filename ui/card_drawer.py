import tkinter as tk
from PIL import ImageTk
from core.card_model import CardData
from core.storage import CardStorage


class CardDrawerPanel:
    """Scrollable sidebar showing thumbnails of all saved cards."""

    def __init__(self, parent: tk.Widget, on_card_selected):
        self.on_card_selected = on_card_selected
        self._photo_refs = []
        self._card_widgets: list[tuple[CardData, list[tk.Widget]]] = []

        self.frame = tk.Frame(parent, width=170, bg="#1a1a40")
        self.frame.pack_propagate(False)  # Keep fixed width

        # Title
        tk.Label(
            self.frame, text="My Cards",
            font=("Helvetica", 13, "bold"), fg="white", bg="#1a1a40"
        ).pack(pady=(10, 5))

        # Search box
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_cards())
        self._search_entry = tk.Entry(
            self.frame, textvariable=self._search_var,
            font=("Helvetica", 9), bg="#2d2d5e", fg="white",
            insertbackground="white", width=15
        )
        self._search_entry.pack(padx=10, pady=(0, 5))
        # Placeholder behavior
        self._search_placeholder = "Search..."
        self._search_entry.insert(0, self._search_placeholder)
        self._search_entry.config(fg="#888")
        self._search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self._search_entry.bind("<FocusOut>", self._on_search_focus_out)

        # Scrollable area
        self.canvas = tk.Canvas(
            self.frame, width=150, bg="#1a1a40",
            highlightthickness=0, bd=0
        )
        self.scrollbar = tk.Scrollbar(
            self.frame, orient=tk.VERTICAL, command=self.canvas.yview
        )
        self.inner_frame = tk.Frame(self.canvas, bg="#1a1a40")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw"
        )

        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        # Make canvas width follow the frame
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )

        # Bind scrollwheel when hovering over this panel
        self.frame.bind("<Enter>", self._bind_mousewheel)
        self.frame.bind("<Leave>", self._unbind_mousewheel)

        # Empty state label
        self.empty_label = tk.Label(
            self.inner_frame, text="No cards yet!\nGenerate your\nfirst card.",
            font=("Helvetica", 10), fg="#666", bg="#1a1a40", justify=tk.CENTER
        )
        self.empty_label.pack(pady=20)

    def _on_search_focus_in(self, event):
        if self._search_entry.get() == self._search_placeholder:
            self._search_entry.delete(0, tk.END)
            self._search_entry.config(fg="white")

    def _on_search_focus_out(self, event):
        if not self._search_entry.get():
            self._search_entry.insert(0, self._search_placeholder)
            self._search_entry.config(fg="#888")

    def _filter_cards(self):
        query = self._search_var.get().lower().strip()
        if query == self._search_placeholder.lower():
            query = ""
        for card, widgets in self._card_widgets:
            if not query or query in card.monster_name.lower():
                for w in widgets:
                    w.pack(pady=4 if isinstance(w, tk.Button) else 0, padx=10 if isinstance(w, tk.Button) else 0)
            else:
                for w in widgets:
                    w.pack_forget()

    def _bind_mousewheel(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def refresh(self, cards: list[CardData], storage: CardStorage):
        """Reload all thumbnails."""
        for widget in self.inner_frame.winfo_children():
            widget.destroy()
        self._photo_refs.clear()
        self._card_widgets.clear()

        if not cards:
            self.empty_label = tk.Label(
                self.inner_frame, text="No cards yet!\nGenerate your\nfirst card.",
                font=("Helvetica", 10), fg="#666", bg="#1a1a40", justify=tk.CENTER
            )
            self.empty_label.pack(pady=20)
            return

        for card in reversed(cards):  # newest first
            try:
                thumb = storage.load_thumbnail(card)
                photo = ImageTk.PhotoImage(thumb)
                self._photo_refs.append(photo)

                btn = tk.Button(
                    self.inner_frame, image=photo, bd=2,
                    relief=tk.GROOVE, bg="#2d2d5e", cursor="hand2",
                    command=lambda c=card: self.on_card_selected(c),
                )
                btn.pack(pady=4, padx=10)

                # Monster name label below thumbnail
                lbl = tk.Label(
                    self.inner_frame, text=card.monster_name,
                    font=("Helvetica", 9), fg="#ccc", bg="#1a1a40"
                )
                lbl.pack()

                self._card_widgets.append((card, [btn, lbl]))

            except Exception:
                continue
