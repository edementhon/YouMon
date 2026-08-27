from __future__ import annotations
import base64
import io
import json
import time
from PIL import Image
from api.openai_client import get_client
from core.card_model import CardData
import config


_SYSTEM_PROMPT_TEMPLATE = """You design cards for YouMon, an original kids' monster trading card game. \
Every monster is a brand-new, wholly original creature.

The players are children, roughly 5 to 10 years old, making cards of monsters they invented. \
Kids describe their monster using the characters they already know: "like Pikachu but a fox", \
"a blue hedgehog", "a fire dragon like Charizard". That is how children explain an idea, and it \
is inspiration, not a request for a copy. Never refuse or water down a card for this reason. \
Instead, take the general vibe — element, colours, mood, energy — and design a genuinely new \
creature with its own silhouette, markings, and personality. Never reproduce an existing \
character, name, or logo, and never put one in the artwork.

Keep it adventurous but age-appropriate: no blood, wounds, gore, realistic firearms, or cruelty. \
Spooky, fierce, slimy, and monstrous are all welcome — this is a monster game.

When given a monster's details, you will:
1. If HP is missing, pick a suitable HP for the monster
2. If any attack descriptions are empty, invent creative attacks that fit the monster's theme
3. Come up with a polished attack name (1-3 punchy words) for each attack
4. Assign appropriate damage values based on the monster's power level
5. Write a short flavor text sentence for the bottom of the card
6. Assign an elemental type: Fire, Water, Grass, Lightning, Psychic, Fighting, Dark, Metal, Dragon, Fairy, Normal, Ice, or Colorless
7. Generate the card image

The card image should look like a Japanese-style collectible monster trading card:
- Gold/yellow outer border with rounded corners
- Monster name top-left, HP top-right with a small elemental type icon
- Large illustration window in the upper half showing the original monster in an action scene
- A thin info bar below the illustration with the monster's species category{brand_rule}
- Attack section: each attack shows small elemental cost icons on the left, attack name in the middle, damage number on the right
- Thin divider lines between attacks
- Italic flavor text near the bottom
- A stats bar at the very bottom showing Weakness, Resistance, and Retreat Cost
- Card border color tinted to match the elemental type
- Portrait orientation, 2.5:3.5 aspect ratio
- The card border/frame must extend all the way to the edges of the image with NO margin or gap — the colored border should touch all four edges
- Monster art style: vivid, colorful, dynamic pose, anime-influenced, original creature design
- All text must be spelled correctly and clearly legible

After generating the image, respond with a JSON block:
```json
{"flavor_text": "...", "monster_type": "...", "hitpoints": 100, "attacks": [{"name": "...", "description": "...", "damage": 30}, {"name": "...", "description": "...", "damage": 50}, {"name": "...", "description": "...", "damage": 70}]}
```"""

# Left out of the prompt entirely when brand text is allowed, rather than
# phrased as permission — telling a model it *may* print trademarks reads as a
# flag either way, and the whole question here is whether raising the subject
# changes the refusal rate.
_BRAND_RULE = (
    ", worded like \"Spark-Tail Fox Monster\" or \"Spark-Tail Fox YouMon\" — never the "
    "name of a real game, show, or franchise\n"
    "- No real-world brand, franchise, or trademark name appears anywhere on the card, "
    "in any text or logo"
)


def build_system_prompt(allow_brand_text: bool) -> str:
    # str.replace, not str.format — the template carries a JSON example whose
    # braces format() would try to interpret.
    return _SYSTEM_PROMPT_TEMPLATE.replace(
        "{brand_rule}", "" if allow_brand_text else _BRAND_RULE
    )


SYSTEM_PROMPT = build_system_prompt(config.DEFAULT_GEN.allow_brand_text)

# Retries walk down this ladder. Attempt 1 sends the child's words untouched;
# later attempts add progressively firmer reframing. Re-sending an identical
# prompt after a content block just gets blocked again, so each rung has to
# actually change something.
RETRY_NUDGES = [
    "",
    (
        "\n\nReminder: design a brand-new original creature inspired by this description. "
        "Do not draw any existing character. Keep the art bright and age-appropriate."
    ),
    (
        "\n\nImportant: ignore any resemblance to characters from existing games, shows, or "
        "movies. Read the description only as a loose mood board — take just the colour, "
        "element, and feeling from it — and invent a completely original monster of your own "
        "with a different body shape and different markings. Wholesome, cartoon, all-ages art."
    ),
]

MAX_RETRIES = len(RETRY_NUDGES)


class CardRefused(RuntimeError):
    """The model declined to draw this monster on every attempt.

    Carries a message safe to show to a child, since this is the one failure a
    player can actually do something about.
    """

    def __init__(self, monster_name: str, detail: str = ""):
        self.monster_name = monster_name
        self.detail = detail
        super().__init__(
            f"The art robot got shy about \"{monster_name or 'that monster'}\" and would not "
            f"draw it. Try describing the monster in your own words instead of naming a "
            f"character from a game or show, and give it a new name."
        )


def _looks_like_refusal(text: str) -> bool:
    """Did the model answer with a polite no instead of a card?

    Only consulted when a response came back with no image attached, so this is
    a tie-breaker between "refused" and "something else went wrong" — not a
    content classifier.
    """
    t = text.lower()
    return any(
        p in t for p in (
            "can't create", "cannot create", "can't generate", "cannot generate",
            "can't help", "cannot help", "won't be able", "unable to create",
            "unable to generate", "copyrighted", "trademark", "intellectual property",
            "content policy", "i'm sorry", "i am sorry",
        )
    )


def generate_card(
    card: CardData,
    settings: config.GenSettings | None = None,
    on_attempt=None,
) -> tuple[Image.Image, dict]:
    """
    Single call that enriches the card text AND generates the card image.
    Returns (card_image, text_data_dict).

    on_attempt, if given, is called as on_attempt(attempt_number, outcome) with
    outcome in {"ok", "blocked", "refused", "no_image"}. The eval suite uses it
    to tell "worked first try" from "worked, but only after two rewordings" —
    which is the difference between a happy child and a bored one.
    """
    settings = settings or config.DEFAULT_GEN

    def _note(attempt: int, outcome: str):
        if on_attempt:
            on_attempt(attempt, outcome)
    client = get_client()

    attack_lines = ""
    for i, a in enumerate(card.attacks):
        if a.description:
            attack_lines += f"- Attack {i+1}: {a.description}\n"
        else:
            attack_lines += f"- Attack {i+1}: (you decide!)\n"

    hp_line = f"HP: {card.hitpoints}" if card.hitpoints else "HP: (you decide!)"

    base_msg = (
        f"Create a YouMon trading card for:\n"
        f"Monster name: {card.monster_name}\n"
        f"Description: {card.description or 'You decide the look!'}\n"
        f"{hp_line}\n"
        f"Attacks:\n{attack_lines}\n"
        f"Please generate the card image and provide the JSON with the attack names, "
        f"damage values, flavor text, and monster type."
    )

    last_error = None
    refusal_detail = ""
    for attempt in range(1, MAX_RETRIES + 1):
        user_msg = base_msg + RETRY_NUDGES[attempt - 1]
        print(f"[YouMon] Calling {settings.text_model} + {settings.image_model} for "
              f"'{card.monster_name}' (attempt {attempt}/{MAX_RETRIES})...")
        t0 = time.time()

        try:
            response = client.responses.create(
                model=settings.text_model,
                input=[
                    {"role": "system",
                     "content": build_system_prompt(settings.allow_brand_text)},
                    {"role": "user", "content": user_msg},
                ],
                tools=[{
                    "type": "image_generation",
                    "model": settings.image_model,
                    "quality": settings.image_quality,
                    "size": settings.image_size,
                }],
            )
        except Exception as e:
            last_error = e
            error_str = str(e)
            if any(k in error_str.lower() for k in
                   ("moderation", "safety", "content_policy", "content policy")):
                refusal_detail = error_str[:200]
                _note(attempt, "blocked")
                print(f"[YouMon]   Content block on attempt {attempt}, rewording...")
                time.sleep(1)
                continue
            raise

        elapsed = time.time() - t0
        print(f"[YouMon] {settings.text_model} responded in {elapsed:.1f}s")

        # Extract image and text from response
        card_image = None
        text_data = {}
        message_text = ""

        for output in response.output:
            print(f"[YouMon]   output type: {output.type}")
            if output.type == "image_generation_call":
                # The call can come back without pixels — status "incomplete"
                # or a partial render — in which case result is None. Treat it
                # as a miss and retry rather than blowing up on the decode.
                if not getattr(output, "result", None):
                    print(f"[YouMon]   image call returned no data "
                          f"(status={getattr(output, 'status', '?')})")
                    continue
                image_bytes = base64.b64decode(output.result)
                card_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
                print(f"[YouMon]   image size: {card_image.size}")

            elif output.type == "message":
                # Parse JSON from the text content
                for content in output.content:
                    if content.type == "output_text":
                        text = content.text
                        message_text += text
                        print(f"[YouMon]   text: {text[:200]}")
                        json_str = _extract_json(text)
                        if json_str:
                            try:
                                text_data = json.loads(json_str)
                            except json.JSONDecodeError:
                                pass
                    elif content.type == "refusal":
                        message_text += content.refusal
                        print(f"[YouMon]   refusal: {content.refusal[:200]}")

        if card_image is None:
            if _looks_like_refusal(message_text):
                refusal_detail = message_text[:200]
                _note(attempt, "refused")
                print(f"[YouMon]   Model declined on attempt {attempt}, rewording...")
            else:
                _note(attempt, "no_image")
                print(f"[YouMon]   No image in response on attempt {attempt}, retrying...")
            last_error = RuntimeError("no card image in response")
            time.sleep(1)
            continue

        _note(attempt, "ok")
        print(f"[YouMon] Card generated: type={text_data.get('monster_type')}, "
              f"flavor={text_data.get('flavor_text', '')[:60]}")
        return card_image, text_data

    if refusal_detail:
        raise CardRefused(card.monster_name, refusal_detail)
    raise last_error or RuntimeError("Card generation failed after all retries")


def _extract_json(text: str) -> str | None:
    """Pull a JSON object out of text that may contain markdown code fences."""
    # Try to find JSON in code blocks first
    import re
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # Try to find a raw JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return None
