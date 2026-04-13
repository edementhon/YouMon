from __future__ import annotations
import pathlib
from PIL import Image
from core.card_model import CardData
import config


class CardStorage:
    """Manages card JSON + image files in the cards/ directory."""

    def __init__(self, cards_dir: pathlib.Path | None = None):
        self.cards_dir = cards_dir or config.CARDS_DIR
        self.cards_dir.mkdir(exist_ok=True)

    def save_card(self, card: CardData, front_img: Image.Image,
                  back_img: Image.Image) -> None:
        prefix = f"card_{card.id}"
        # Save images
        front_path = self.cards_dir / f"{prefix}_front.png"
        back_path = self.cards_dir / f"{prefix}_back.png"
        front_img.save(str(front_path), dpi=(config.CARD_DPI, config.CARD_DPI))
        back_img.save(str(back_path), dpi=(config.CARD_DPI, config.CARD_DPI))
        # Record filenames in card data
        card.front_image = front_path.name
        card.back_image = back_path.name
        # Save JSON
        json_path = self.cards_dir / f"{prefix}.json"
        json_path.write_text(card.to_json())

    def load_all_cards(self) -> list[CardData]:
        cards = []
        # Sort by file modification time (oldest first)
        json_files = sorted(self.cards_dir.glob("card_*.json"),
                            key=lambda p: p.stat().st_mtime)
        for p in json_files:
            try:
                cards.append(CardData.from_json(p.read_text()))
            except Exception:
                continue
        return cards

    def load_front_image(self, card: CardData) -> Image.Image:
        path = self.cards_dir / card.front_image
        return Image.open(str(path))

    def load_back_image(self, card: CardData) -> Image.Image:
        path = self.cards_dir / card.back_image
        return Image.open(str(path))

    def load_thumbnail(self, card: CardData) -> Image.Image:
        img = self.load_front_image(card)
        ratio = config.THUMBNAIL_HEIGHT / img.height
        new_w = int(img.width * ratio)
        return img.resize((new_w, config.THUMBNAIL_HEIGHT), Image.LANCZOS)

    def find_back_for_user(self, user_name: str) -> str | None:
        """Find an existing card back image for this user name."""
        for p in self.cards_dir.glob("card_*.json"):
            try:
                card = CardData.from_json(p.read_text())
                if card.user_name == user_name and card.back_image:
                    back_path = self.cards_dir / card.back_image
                    if back_path.exists():
                        return str(back_path)
            except Exception:
                continue
        return None

    def delete_card(self, card: CardData) -> None:
        prefix = f"card_{card.id}"
        for p in self.cards_dir.glob(f"{prefix}*"):
            p.unlink()
