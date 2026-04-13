import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from core.card_model import CardData
from core.storage import CardStorage
from core.print_layout import export_pdf
import config


class PrintDialog(tk.Toplevel):
    """Dialog for selecting cards and exporting a printable PDF layout."""

    def __init__(self, parent: tk.Tk, cards: list[CardData], storage: CardStorage):
        super().__init__(parent)
        self.title("Print Cards")
        self.geometry("500x600")
        self.configure(bg="#2d2d5e")
        self.transient(parent)
        self.grab_set()

        self.cards = list(reversed(cards))  # newest first
        self.storage = storage
        self._check_vars: list[tuple[tk.BooleanVar, CardData]] = []
        self._check_widgets: list[tk.Checkbutton] = []

        # --- Paper size ---
        settings = tk.Frame(self, bg="#2d2d5e")
        settings.pack(fill=tk.X, padx=15, pady=10)

        tk.Label(
            settings, text="Paper Size:", font=("Helvetica", 11),
            fg="white", bg="#2d2d5e"
        ).grid(row=0, column=0, sticky="w")

        self.paper_var = tk.StringVar(value="letter")
        ttk.Radiobutton(settings, text="US Letter", variable=self.paper_var, value="letter").grid(row=0, column=1, padx=5)
        ttk.Radiobutton(settings, text="A4", variable=self.paper_var, value="a4").grid(row=0, column=2, padx=5)

        # --- Grid size ---
        tk.Label(
            settings, text="Cards across:", font=("Helvetica", 11),
            fg="white", bg="#2d2d5e"
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.cols_var = tk.IntVar(value=3)
        tk.Spinbox(
            settings, from_=1, to=4, textvariable=self.cols_var, width=4,
            font=("Helvetica", 11)
        ).grid(row=1, column=1, pady=(8, 0))

        tk.Label(
            settings, text="Cards down:", font=("Helvetica", 11),
            fg="white", bg="#2d2d5e"
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.rows_var = tk.IntVar(value=3)
        tk.Spinbox(
            settings, from_=1, to=4, textvariable=self.rows_var, width=4,
            font=("Helvetica", 11)
        ).grid(row=2, column=1, pady=(4, 0))

        # --- Duplex option ---
        self.duplex_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            settings, text="Mirror backs for duplex printing",
            variable=self.duplex_var, fg="white", bg="#2d2d5e",
            selectcolor="#3d3d7e", font=("Helvetica", 10),
            activebackground="#2d2d5e", activeforeground="white"
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # --- Card selection ---
        tk.Label(
            self, text="Select cards to print:",
            font=("Helvetica", 12, "bold"), fg="white", bg="#2d2d5e"
        ).pack(pady=(5, 0), anchor="w", padx=15)

        # Search box
        search_frame = tk.Frame(self, bg="#2d2d5e")
        search_frame.pack(fill=tk.X, padx=15, pady=(2, 0))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_cards())
        search_entry = tk.Entry(
            search_frame, textvariable=self._search_var,
            font=("Helvetica", 10), bg="#1a1a40", fg="white",
            insertbackground="white"
        )
        search_entry.pack(fill=tk.X)
        search_entry.insert(0, "")
        # Placeholder behavior
        self._search_placeholder = "Search cards..."
        search_entry.insert(0, self._search_placeholder)
        search_entry.config(fg="#888")
        search_entry.bind("<FocusIn>", lambda e: self._on_search_focus_in(e.widget))
        search_entry.bind("<FocusOut>", lambda e: self._on_search_focus_out(e.widget))
        self._search_entry = search_entry

        card_frame = tk.Frame(self, bg="#2d2d5e")
        card_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        canvas = tk.Canvas(card_frame, bg="#1a1a40", highlightthickness=0)
        scrollbar = tk.Scrollbar(card_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg="#1a1a40")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Select All / Deselect All buttons
        sel_frame = tk.Frame(self, bg="#2d2d5e")
        sel_frame.pack(fill=tk.X, padx=15)

        sel_all = tk.Label(
            sel_frame, text="Select All", font=("Helvetica", 10),
            bg="#3d3d7e", fg="white", cursor="hand2", padx=8, pady=3,
            relief=tk.RAISED, bd=1,
        )
        sel_all.pack(side=tk.LEFT, padx=(0, 5))
        sel_all.bind("<Button-1>", lambda e: self._set_all(True))

        desel_all = tk.Label(
            sel_frame, text="Deselect All", font=("Helvetica", 10),
            bg="#3d3d7e", fg="white", cursor="hand2", padx=8, pady=3,
            relief=tk.RAISED, bd=1,
        )
        desel_all.pack(side=tk.LEFT)
        desel_all.bind("<Button-1>", lambda e: self._set_all(False))

        for card in self.cards:
            var = tk.BooleanVar(value=False)
            self._check_vars.append((var, card))
            cb = tk.Checkbutton(
                inner, text=f"{card.monster_name} ({card.hitpoints} HP)",
                variable=var, fg="white", bg="#1a1a40",
                selectcolor="#3d3d7e", font=("Helvetica", 10),
                activebackground="#1a1a40", activeforeground="white",
                anchor="w"
            )
            cb.pack(fill=tk.X, padx=5, pady=1)
            self._check_widgets.append(cb)

        # Bind scrollwheel to the entire dialog when mouse is over card area
        self._print_canvas = canvas
        self._print_inner = inner
        self.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, canvas))

        # --- Export buttons ---
        btn_frame = tk.Frame(self, bg="#2d2d5e")
        btn_frame.pack(fill=tk.X, padx=15, pady=10)

        for text, color, cmd in [
            ("Export Fronts", "#ff6b35", self._export_fronts),
            ("Export Backs", "#ff6b35", self._export_backs),
            ("Export Both", "#35b0ff", self._export_both),
        ]:
            btn = tk.Label(
                btn_frame, text=text, font=("Helvetica", 11, "bold"),
                bg=color, fg="white", cursor="hand2",
                pady=8, relief=tk.RAISED, bd=2,
            )
            btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
            btn.bind("<Button-1>", lambda e, c=cmd: c())

    def _on_search_focus_in(self, widget):
        if widget.get() == self._search_placeholder:
            widget.delete(0, tk.END)
            widget.config(fg="white")

    def _on_search_focus_out(self, widget):
        if not widget.get():
            widget.insert(0, self._search_placeholder)
            widget.config(fg="#888")

    def _filter_cards(self):
        query = self._search_var.get().lower().strip()
        if query == self._search_placeholder.lower():
            query = ""
        for (var, card), cb in zip(self._check_vars, self._check_widgets):
            if not query or query in card.monster_name.lower():
                cb.pack(fill=tk.X, padx=5, pady=1)
            else:
                cb.pack_forget()

    def _set_all(self, value: bool):
        for var, _ in self._check_vars:
            var.set(value)

    def _on_mousewheel(self, event, canvas):
        canvas.yview_scroll(int(-event.delta / 120), "units")

    def _get_selected_cards(self) -> list[CardData]:
        return [card for var, card in self._check_vars if var.get()]

    def _export_fronts(self):
        cards = self._get_selected_cards()
        if not cards:
            messagebox.showinfo("No Cards", "Select at least one card!", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")], title="Save Fronts PDF"
        )
        if not path:
            return
        front_images = [self.storage.load_front_image(c) for c in cards]
        export_pdf(
            front_images, self.paper_var.get(),
            self.cols_var.get(), self.rows_var.get(), path
        )
        messagebox.showinfo("Exported", f"Fronts PDF saved!\n{path}", parent=self)

    def _export_backs(self):
        cards = self._get_selected_cards()
        if not cards:
            messagebox.showinfo("No Cards", "Select at least one card!", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")], title="Save Backs PDF"
        )
        if not path:
            return
        back_images = [self.storage.load_back_image(c) for c in cards]
        mirror = self.duplex_var.get()
        export_pdf(
            back_images, self.paper_var.get(),
            self.cols_var.get(), self.rows_var.get(), path,
            mirror_for_duplex=mirror
        )
        messagebox.showinfo("Exported", f"Backs PDF saved!\n{path}", parent=self)

    def _export_both(self):
        cards = self._get_selected_cards()
        if not cards:
            messagebox.showinfo("No Cards", "Select at least one card!", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")], title="Save Cards PDF"
        )
        if not path:
            return
        front_images = [self.storage.load_front_image(c) for c in cards]
        back_images = [self.storage.load_back_image(c) for c in cards]
        mirror = self.duplex_var.get()
        export_pdf(
            front_images, self.paper_var.get(),
            self.cols_var.get(), self.rows_var.get(), path,
            back_images=back_images, mirror_for_duplex=mirror
        )
        messagebox.showinfo("Exported", f"Cards PDF saved!\n{path}", parent=self)
