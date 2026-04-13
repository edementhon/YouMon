import tkinter as tk
from tkinter import ttk
from core.card_model import CardData, Attack


class CardFormPanel:
    """Input fields for designing a monster card, plus the Generate button."""

    def __init__(self, parent: tk.Widget, on_generate):
        self.on_generate = on_generate

        self.frame = tk.Frame(parent, bg="#2d2d5e")

        # Title
        tk.Label(
            self.frame, text="Design Your Monster!",
            font=("Helvetica", 16, "bold"), fg="white", bg="#2d2d5e"
        ).pack(pady=(10, 15))

        # Form area
        form = tk.Frame(self.frame, bg="#2d2d5e")
        form.pack(fill=tk.X, padx=15)

        self.user_name_var = tk.StringVar()
        self.monster_name_var = tk.StringVar()
        self.description_var = tk.StringVar()
        self.hp_var = tk.StringVar()
        self.attack1_var = tk.StringVar()
        self.attack2_var = tk.StringVar()
        self.attack3_var = tk.StringVar()

        fields = [
            ("Your Name:", self.user_name_var),
            ("Monster Name:", self.monster_name_var),
            ("Description (optional):", self.description_var),
            ("Hit Points (optional):", self.hp_var),
            ("Attack 1 (optional):", self.attack1_var),
            ("Attack 2 (optional):", self.attack2_var),
            ("Attack 3 (optional):", self.attack3_var),
        ]

        for i, (label_text, var) in enumerate(fields):
            tk.Label(
                form, text=label_text, font=("Helvetica", 11),
                fg="#ddd", bg="#2d2d5e", anchor="w"
            ).grid(row=i, column=0, sticky="w", pady=3)
            entry = tk.Entry(
                form, textvariable=var, font=("Helvetica", 12),
                width=28, bg="#3d3d7e", fg="white", insertbackground="white",
                relief=tk.FLAT, highlightthickness=1, highlightcolor="#ff6b35"
            )
            entry.grid(row=i, column=1, sticky="ew", pady=3, padx=(8, 0))

        form.columnconfigure(1, weight=1)

        # Generate button (using Label so colors work on macOS)
        self.generate_btn = tk.Label(
            self.frame, text="Generate Card!",
            font=("Helvetica", 16, "bold"), bg="#ff6b35", fg="white",
            cursor="hand2", pady=10, relief=tk.RAISED, bd=2,
        )
        self.generate_btn.pack(pady=(20, 5), padx=15, fill=tk.X)
        self.generate_btn.bind("<Button-1>", lambda e: self._on_generate_click())

        # Remix button
        self.remix_btn = tk.Label(
            self.frame, text="Remix This Card",
            font=("Helvetica", 11, "bold"), bg="#9b59b6", fg="white",
            cursor="hand2", pady=6, relief=tk.RAISED, bd=2,
        )
        self.remix_btn.pack(pady=(0, 5), padx=15, fill=tk.X)
        self.remix_btn.bind("<Button-1>", lambda e: self._on_generate_click())
        self._generating = False

        # Status label
        self.status_var = tk.StringVar(value="Ready to create!")
        self.status_label = tk.Label(
            self.frame, textvariable=self.status_var,
            font=("Helvetica", 10), fg="#aaa", bg="#2d2d5e"
        )
        self.status_label.pack()

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
            description=self.description_var.get().strip(),
            hitpoints=hp,
            attacks=[
                Attack(description=self.attack1_var.get().strip()),
                Attack(description=self.attack2_var.get().strip()),
                Attack(description=self.attack3_var.get().strip()),
            ],
        )
        self.on_generate(card)

    def set_status(self, text: str):
        self.status_var.set(text)

    def set_generating(self, active: bool):
        self._generating = active
        if active:
            self.generate_btn.config(bg="#888", fg="#ccc", cursor="watch")
        else:
            self.generate_btn.config(bg="#ff6b35", fg="white", cursor="hand2")

    def populate(self, card: CardData):
        """Fill fields from an existing CardData."""
        self.user_name_var.set(card.user_name)
        self.monster_name_var.set(card.monster_name)
        self.description_var.set(card.description)
        self.hp_var.set(str(card.hitpoints))
        if len(card.attacks) >= 1:
            self.attack1_var.set(card.attacks[0].description)
        if len(card.attacks) >= 2:
            self.attack2_var.set(card.attacks[1].description)
        if len(card.attacks) >= 3:
            self.attack3_var.set(card.attacks[2].description)
