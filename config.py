import os
import json
import pathlib
from dataclasses import dataclass

APP_DIR = pathlib.Path(__file__).parent
CARDS_DIR = APP_DIR / "cards"
CONFIG_FILE = APP_DIR / "config.json"


@dataclass(frozen=True)
class GenSettings:
    """Which models draw the card, and how big/nice the drawing is.

    Kept in one object so the eval suite can sweep variants without the app
    and the evals drifting apart.
    """
    text_model: str = "gpt-5.6-terra"
    image_model: str = "gpt-image-2"
    image_quality: str = "medium"
    image_size: str = "1200x1680"


# gpt-image-2 is the only image model with a future: gpt-image-1 shuts down
# 2026-10-23, gpt-image-1.5 and gpt-image-1-mini on 2026-12-01.
#
# 1200x1680 is exactly 2.5:3.5 (the trading-card ratio) and satisfies
# gpt-image-2's "every edge a multiple of 16" rule, so the card drops into the
# print box with no stretching. It downsamples to 750x1050 at 300 DPI cleanly.
#
# medium quality: high costs 4x more and takes 2x longer for detail that
# disappears on a 2.5" card. See evals/README.md.
DEFAULT_GEN = GenSettings()

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
