import os
import json
import pathlib

APP_DIR = pathlib.Path(__file__).parent
CARDS_DIR = APP_DIR / "cards"
CONFIG_FILE = APP_DIR / "config.json"

# Card dimensions at 300 DPI (standard trading card 2.5" x 3.5")
CARD_WIDTH_PX = 750
CARD_HEIGHT_PX = 1050
CARD_DPI = 300

# Preview scale for on-screen display
PREVIEW_WIDTH = 372
PREVIEW_HEIGHT = 520

# Thumbnail height for the card drawer
THUMBNAIL_HEIGHT = 150


def load_api_key() -> str:
    """Load OpenAI API key from env var or config.json."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        return key
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text())
        return data.get("openai_api_key", "")
    return ""
