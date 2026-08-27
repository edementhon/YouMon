"""Vision judge: score a generated card the way a parent and a kid would.

Two things decide whether a YouMon card is any good, and they pull apart:

  craft  — is the text spelled right, does it have the parts of a real card,
           does the frame reach the edges? This is where cheap image models
           fail, and it is objectively checkable from the image.
  cool   — would a six-year-old want this one in his binder? Not the same as
           craft; a technically clean card can still be boring.

The schema asks for observations before scores on purpose. A model that emits
the number first spends the rest of the response justifying it.
"""
from __future__ import annotations

import base64
import io
import json

from PIL import Image

from api.openai_client import get_client

JUDGE_MODEL = "gpt-5.6-sol"

RUBRIC = """You are grading a card from YouMon, an app where children aged 5-10 invent \
their own monster and the app draws it as a Japanese-style collectible trading card. \
The finished cards get printed on glossy stock and put in a binder.

Look at the card image and grade it honestly. Be strict about text: these get printed \
at 2.5 x 3.5 inches, and a garbled word is a ruined card.

A well-formed card has: the monster name top-left, HP top-right with an elemental icon, \
a large illustration window in the upper half, a species/category bar under the art, \
two or three attacks each with cost icons, an attack name and a damage number, italic \
flavor text near the bottom, and a Weakness/Resistance/Retreat bar at the very bottom. \
The coloured frame should run all the way to the edges of the image with no white margin.

One hard rule, because it ruins a card that otherwise looks fine:

- If any word on the card is misspelled or garbled, text_quality is at most 2.

Always list any real-world brand or franchise names printed on the card in \
brand_names_on_card, whatever the policy below says. "YouMon", and any "<Name>Mon" built \
from the player's own name, is this app's own branding — it belongs on the card and is \
never a brand name.

{brand_policy}

Scores are 0-5 and 5 should be rare. Reserve 5 for a card with nothing you would change; \
a clean, competent, unremarkable card is a 3. If you find yourself giving 5s across the \
board, look harder at the small type: the flavor text, the attack costs, and the \
Weakness/Resistance/Retreat bar are where these cards fall apart."""

# Whether a printed franchise name counts against the card is a product
# decision, not a fact about the image, so it is a policy the caller sets. The
# judge reports the names either way; only the scoring changes.
BRAND_POLICY_ALLOWED = """These cards are printed at home for one child's own binder, and \
franchise names appearing in the card text are accepted. Do not lower any score or set \
printable false because of them. Judge the card on craft and appeal alone."""

BRAND_POLICY_FORBIDDEN = """If any real-world brand or franchise name is printed on the \
card (Pokemon, Pikachu, Minecraft, Mario, and so on), text_quality is at most 2 and \
printable is false. Drawing an original creature in a familiar art style is fine and \
expected; printing someone else's trademark on the card is not."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "transcribed_text": {
            "type": "string",
            "description": "Every word you can read on the card, in reading order.",
        },
        "misspellings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Words that are garbled, misspelled, or nonsense. Empty if clean.",
        },
        "missing_elements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required card parts that are absent or unreadable.",
        },
        "border_reaches_edges": {"type": "boolean"},
        "art_description": {
            "type": "string",
            "description": "One sentence: what the monster looks like and how it is posed.",
        },
        "brand_names_on_card": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Real-world brand, franchise, or character names printed as text "
                           "anywhere on the card. Empty if none.",
        },
        "resembles_existing_character": {
            "type": "boolean",
            "description": "True only if this is recognisably a copyrighted character rather "
                           "than an original creature in a similar style.",
        },
        "craft_reasoning": {"type": "string"},
        "text_quality": {"type": "integer", "minimum": 0, "maximum": 5},
        "layout_fidelity": {"type": "integer", "minimum": 0, "maximum": 5},
        "cool_reasoning": {
            "type": "string",
            "description": "Would a six-year-old pick this out of a stack? Why or why not?",
        },
        "art_quality": {"type": "integer", "minimum": 0, "maximum": 5},
        "kid_appeal": {"type": "integer", "minimum": 0, "maximum": 5},
        "printable": {
            "type": "boolean",
            "description": "Would you print this one, or regenerate it?",
        },
    },
    "required": [
        "transcribed_text", "misspellings", "missing_elements", "border_reaches_edges",
        "art_description", "brand_names_on_card", "resembles_existing_character",
        "craft_reasoning", "text_quality", "layout_fidelity", "cool_reasoning",
        "art_quality", "kid_appeal", "printable",
    ],
}


def _data_url(path: str, max_edge: int = 1024) -> str:
    """Downscale before sending: the judge reads a printed-size card, and full
    resolution just costs image input tokens."""
    img = Image.open(path).convert("RGB")
    if max(img.size) > max_edge:
        scale = max_edge / max(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def judge_card(image_path: str, monster_name: str, description: str,
               allow_brand_text: bool = True) -> dict:
    """Grade one card image. Returns the parsed rubric dict.

    allow_brand_text must match the setting the card was generated under, or
    the card gets marked down for obeying its own instructions.
    """
    client = get_client()
    rubric = RUBRIC.replace(
        "{brand_policy}",
        BRAND_POLICY_ALLOWED if allow_brand_text else BRAND_POLICY_FORBIDDEN,
    )
    asked_for = (
        f"The child asked for a monster named \"{monster_name}\""
        + (f" described as: {description}" if description else " with no description")
        + "."
    )
    response = client.responses.create(
        model=JUDGE_MODEL,
        input=[
            {"role": "system", "content": rubric},
            {"role": "user", "content": [
                {"type": "input_text", "text": asked_for},
                {"type": "input_image", "image_url": _data_url(image_path)},
            ]},
        ],
        text={"format": {
            "type": "json_schema",
            "name": "card_grade",
            "strict": True,
            "schema": SCHEMA,
        }},
    )
    return json.loads(response.output_text)


def overall(grade: dict) -> float:
    """One number for ranking variants.

    Craft is weighted over art because a beautiful card with 'HIP 90' on it is
    still a bad card, and craft is the axis the cheap models fail on.
    """
    return round(
        0.3 * grade["text_quality"]
        + 0.25 * grade["layout_fidelity"]
        + 0.25 * grade["art_quality"]
        + 0.2 * grade["kid_appeal"],
        2,
    )
