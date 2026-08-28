from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
import threading
from PIL import Image

from ui.card_form import CardFormPanel
from ui.card_preview import CardPreviewPanel
from ui.card_drawer import CardDrawerPanel
from ui.print_dialog import PrintDialog
from ui import theme
from core.card_model import CardData
from core.storage import CardStorage
from api import card_gen, back_gen
import config


class AppWindow:
    """Main application window — orchestrates form, preview, drawer, and generation pipeline."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("YouMon - Monster Card Maker!")
        self.root.geometry("1180x860")
        self.root.configure(bg=theme.BG)
        self.root.minsize(1000, 760)

        self.storage = CardStorage()
        self._current_card: CardData | None = None
        self._showing_back = False

        # --- Menu bar ---
        menubar = tk.Menu(root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="View Card Back", command=self._toggle_back)
        file_menu.add_command(label="Generate New Card Back", command=self._generate_new_back)
        file_menu.add_separator()
        file_menu.add_command(label="Print Layout...", command=self._open_print_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        root.config(menu=menubar)

        # --- Layout: [Drawer] [Form] [Preview] ---
        # Drawer and Preview have fixed widths; Form fills the middle
        self.drawer = CardDrawerPanel(root, on_card_selected=self._on_card_selected)
        self.drawer.frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0), pady=5)

        self.preview = CardPreviewPanel(root)
        self.preview.on_click = self._toggle_back
        self.preview.frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)

        self.form = CardFormPanel(root, on_generate=self._on_generate)
        self.form.frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # Load existing cards into drawer
        self._refresh_drawer()

        # Check for API key
        self._check_api_key()

    def _check_api_key(self):
        key = config.load_api_key()
        if not key:
            messagebox.showwarning(
                "API Key Needed",
                "No OpenAI API key found!\n\n"
                "Ask a grown-up to either:\n"
                "1. Set the OPENAI_API_KEY environment variable, or\n"
                '2. Create a config.json file with:\n'
                '   {"openai_api_key": "sk-..."}'
            )

    def _refresh_drawer(self):
        cards = self.storage.load_all_cards()
        self.drawer.refresh(cards, self.storage)
        self._warm_thumbnails(cards)

    def _warm_thumbnails(self, cards: list[CardData]):
        """Build any missing thumbnail caches in the background.

        The drawer only renders what is on screen, so the app starts fast even
        with an empty cache. This fills in the rest quietly so that scrolling
        stays smooth instead of pausing on each uncached card. Touches only
        files, never Tk, so it is safe off the main thread.
        """
        def worker():
            for card in cards:
                try:
                    self.storage.load_thumbnail(card)
                except Exception:
                    continue

        threading.Thread(target=worker, daemon=True).start()

    def _on_card_selected(self, card: CardData):
        """User clicked a card in the drawer."""
        self._current_card = card
        self._showing_back = False
        self.form.populate(card)
        try:
            front_img = self.storage.load_front_image(card)
            self.preview.show_image(front_img, side="front")
        except Exception:
            self.preview.show_error("Could not load\ncard image")

    def _on_generate(self, card: CardData):
        """User clicked Generate Card — run API calls in background thread."""
        self.form.set_generating(True)
        self.preview.show_loading()
        self.form.set_status("Generating card text...")

        def worker():
            try:
                # Step 1: Single GPT-5.4 call — generates text + card image together
                self.root.after(0, lambda: self.form.set_status("Creating your monster card..."))
                front_img, text_data = card_gen.generate_card(card)

                card.flavor_text = text_data.get("flavor_text", "")
                card.monster_type = text_data.get("monster_type", "Unknown")
                if not card.hitpoints and text_data.get("hitpoints"):
                    card.hitpoints = text_data["hitpoints"]
                for i, atk_data in enumerate(text_data.get("attacks", [])):
                    if i < len(card.attacks):
                        card.attacks[i].name = atk_data.get("name", "")
                        card.attacks[i].damage = atk_data.get("damage", 0)
                        if not card.attacks[i].description:
                            card.attacks[i].description = atk_data.get("description", "")

                # Step 2: Get or generate card back
                self.root.after(0, lambda: self.form.set_status("Making card back..."))
                back_path = self.storage.find_back_for_user(card.user_name)
                if back_path:
                    back_img = Image.open(back_path).convert("RGBA")
                else:
                    back_img = back_gen.generate_card_back(card.user_name)

                # Step 3: Save everything
                self.root.after(0, lambda: self.form.set_status("Saving your card..."))
                self.storage.save_card(card, front_img, back_img)

                # Step 4: Update UI on main thread
                self._current_card = card
                self.root.after(0, lambda: self._generation_done(front_img))

            except card_gen.CardRefused as e:
                error_msg = str(e)
                self.root.after(0, lambda: self._generation_error(error_msg, refused=True))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self._generation_error(error_msg))

        threading.Thread(target=worker, daemon=True).start()

    def _generation_done(self, front_img: Image.Image):
        self._showing_back = False
        self.preview.show_image(front_img, side="front")
        # Insert the one new card instead of reloading every thumbnail, which
        # is what made the sidebar lag for minutes after each generation.
        if self._current_card is not None:
            self.drawer.add_card(self._current_card, self.storage)
            self.drawer.select(self._current_card)
        self.form.set_generating(False)
        self.form.set_status("Card created!")

    def _generation_error(self, error_msg: str, refused: bool = False):
        self.form.set_generating(False)
        if refused:
            # A player can actually fix this one, so say how instead of
            # showing them a stack trace.
            self.form.set_status("Try a different monster")
            self.preview.show_error("The art robot\nsaid no to that one.\nTry another idea!")
            messagebox.showinfo("Let's try a different monster", error_msg)
        else:
            self.form.set_status("Error - see details")
            self.preview.show_error("Generation failed.\nCheck your API key\nand internet.")
            messagebox.showerror("Generation Error", f"Something went wrong:\n\n{error_msg}")

    def _open_print_dialog(self):
        cards = self.storage.load_all_cards()
        if not cards:
            messagebox.showinfo("No Cards", "Generate some cards first!")
            return
        PrintDialog(self.root, cards, self.storage)

    def _generate_new_back(self):
        """Force-generate a new card back for the current user name."""
        user_name = self.form.user_name_var.get().strip()
        if not user_name:
            messagebox.showinfo("Name Needed", "Enter your name first!")
            return

        self.form.set_generating(True)
        self.form.set_status("Generating new card back...")

        def worker():
            try:
                back_img = back_gen.generate_card_back(user_name)
                # Save it as a standalone file so future cards pick it up
                back_filename = f"back_{user_name.lower()}.png"
                back_path = self.storage.cards_dir / back_filename
                back_img.save(str(back_path), dpi=(config.CARD_DPI, config.CARD_DPI))
                self.root.after(0, lambda: self._back_gen_done())
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self._generation_error(error_msg))

        threading.Thread(target=worker, daemon=True).start()

    def _back_gen_done(self):
        self.form.set_generating(False)
        self.form.set_status("New card back generated!")
        messagebox.showinfo("Card Back", "New card back design created! It will be used for future cards.")

    def _toggle_back(self):
        """Toggle the preview between card front and card back."""
        if self._current_card is None:
            return
        try:
            if self._showing_back:
                img = self.storage.load_front_image(self._current_card)
                self._showing_back = False
                self.preview.show_image(img, side="front")
            else:
                img = self.storage.load_back_image(self._current_card)
                self._showing_back = True
                self.preview.show_image(img, side="back")
        except Exception:
            self.preview.show_error("Could not load\ncard image")
