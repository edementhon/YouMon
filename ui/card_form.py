from __future__ import annotations
import tkinter as tk
from core.card_model import CardData, Attack
from ui import theme


class _MultilineField:
    """A tk.Text that behaves enough like an Entry for this form.

    Description and attack ideas get several visible lines because children
    write long, run-on descriptions and a one-line Entry scrolls the start of
    their own sentence out of view while they are still typing it.
    """

    def __init__(self, parent, height: int):
        self.widget = tk.Text(
            parent, height=height, wrap="word",
            font=theme.font(theme.INPUT), padx=8, pady=6,
            undo=True, spacing1=1, spacing3=1,
        )
        theme.style_entry(self.widget)

    def get(self) -> str:
        return self.widget.get("1.0", "end-1c").strip()

    def set(self, value: str):
        self.widget.delete("1.0", "end")
        self.widget.insert("1.0", value or "")

    def grid(self, **kw):
        self.widget.grid(**kw)


class CardFormPanel:
    """Input fields for designing a monster card, plus the Generate button."""

    def __init__(self, parent: tk.Widget, on_generate):
        self.on_generate = on_generate

        self.frame = tk.Frame(parent, bg=theme.PANEL)

        tk.Label(
            self.frame, text="Design Your Monster!",
            font=theme.font(theme.TITLE, bold=True),
            fg=theme.TEXT, bg=theme.PANEL,
        ).pack(pady=(16, 14))

        form = tk.Frame(self.frame, bg=theme.PANEL)
        form.pack(fill=tk.BOTH, expand=True, padx=18)

        self.user_name_var = tk.StringVar()
        self.monster_name_var = tk.StringVar()
        self.hp_var = tk.StringVar()

        row = 0

        def label(text: str, r: int):
            tk.Label(
                form, text=text, font=theme.font(theme.LABEL),
                fg=theme.TEXT_DIM, bg=theme.PANEL, anchor="w",
            ).grid(row=r, column=0, sticky="nw", pady=(8, 2))

        def entry(var: tk.StringVar, r: int):
            e = tk.Entry(form, textvariable=var, font=theme.font(theme.INPUT))
            theme.style_entry(e)
            e.grid(row=r, column=1, sticky="ew", pady=(8, 2), padx=(10, 0), ipady=6)
            return e

        label("Your Name:", row)
        entry(self.user_name_var, row)
        row += 1

        label("Monster Name:", row)
        entry(self.monster_name_var, row)
        row += 1

        label("What does it\nlook like?", row)
        self.description_field = _MultilineField(form, height=4)
        self.description_field.grid(row=row, column=1, sticky="nsew",
                                    pady=(8, 2), padx=(10, 0))
        form.rowconfigure(row, weight=3)
        row += 1

        label("Hit Points:", row)
        entry(self.hp_var, row)
        row += 1

        self.attack_fields: list[_MultilineField] = []
        for i in range(3):
            label(f"Attack {i + 1}:", row)
            f = _MultilineField(form, height=2)
            f.grid(row=row, column=1, sticky="nsew", pady=(8, 2), padx=(10, 0))
            form.rowconfigure(row, weight=1)
            self.attack_fields.append(f)
            row += 1

        tk.Label(
            form, text="Leave anything blank and the AI will pick for you.",
            font=theme.font(theme.TINY), fg=theme.MUTED, bg=theme.PANEL,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))

        form.columnconfigure(1, weight=1)

        self.generate_btn = tk.Label(
            self.frame, text="Generate Card!",
            font=theme.font(theme.BUTTON, bold=True), fg="white",
            cursor="hand2", pady=16,
        )
        theme.style_button(self.generate_btn, theme.ACCENT, theme.ACCENT_HOVER)
        self.generate_btn.pack(pady=(16, 6), padx=18, fill=tk.X)
        self.generate_btn.bind("<Button-1>", lambda e: self._on_generate_click())

        self.remix_btn = tk.Label(
            self.frame, text="Remix This Card",
            font=theme.font(theme.BUTTON_SMALL, bold=True), fg="white",
            cursor="hand2", pady=9,
        )
        theme.style_button(self.remix_btn, theme.SECONDARY, theme.SECONDARY_HOVER)
        self.remix_btn.pack(pady=(0, 8), padx=18, fill=tk.X)
        self.remix_btn.bind("<Button-1>", lambda e: self._on_generate_click())
        self._generating = False

        self.status_var = tk.StringVar(value="Ready to create!")
        self.status_label = tk.Label(
            self.frame, textvariable=self.status_var,
            font=theme.font(theme.SMALL), fg=theme.MUTED, bg=theme.PANEL,
        )
        self.status_label.pack(pady=(0, 12))

    # --- actions ---------------------------------------------------------

    def _on_generate_click(self):
        if self._generating:
            return
        user_name = self.user_name_var.get().strip()
        if not user_name:
            self.set_status("Please enter your name!")
            return

        monster_name = self.monster_name_var.get().strip()
        if not monster_name:
            self.set_status("Please enter a monster name!")
            return

        hp_str = self.hp_var.get().strip()
        try:
            hp = int(hp_str) if hp_str else 0
        except ValueError:
            self.set_status("Hit Points must be a number!")
            return

        card = CardData(
            user_name=user_name,
            monster_name=monster_name,
            description=self.description_field.get(),
            hitpoints=hp,
            attacks=[Attack(description=f.get()) for f in self.attack_fields],
        )
        self.on_generate(card)

    def set_status(self, text: str):
        self.status_var.set(text)

    def set_generating(self, active: bool):
        self._generating = active
        if active:
            self.generate_btn.config(
                bg=theme.ACCENT_DISABLED, fg="#dddddd", cursor="watch",
                text="Working on it...",
            )
        else:
            self.generate_btn.config(
                bg=theme.ACCENT, fg="white", cursor="hand2",
                text="Generate Card!",
            )

    def populate(self, card: CardData):
        """Fill fields from an existing CardData."""
        self.user_name_var.set(card.user_name)
        self.monster_name_var.set(card.monster_name)
        self.description_field.set(card.description)
        self.hp_var.set(str(card.hitpoints) if card.hitpoints else "")
        for i, field in enumerate(self.attack_fields):
            field.set(card.attacks[i].description if i < len(card.attacks) else "")
