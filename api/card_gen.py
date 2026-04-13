from __future__ import annotations
import base64
import io
import json
import time
from PIL import Image
from api.openai_client import get_client
from core.card_model import CardData


SYSTEM_PROMPT = """You design cards for YouMon, an original kids' monster trading card game. \
Every monster is a brand-new, wholly original creature.

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
- A thin info bar below the illustration with the monster's species category
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

MAX_RETRIES = 3


def generate_card(card: CardData) -> tuple[Image.Image, dict]:
    """
    Single GPT-5.4 call that enriches the card text AND generates the card image.
    Returns (card_image, text_data_dict).
    """
    client = get_client()

    attack_lines = ""
    for i, a in enumerate(card.attacks):
        if a.description:
            attack_lines += f"- Attack {i+1}: {a.description}\n"
        else:
            attack_lines += f"- Attack {i+1}: (you decide!)\n"

    hp_line = f"HP: {card.hitpoints}" if card.hitpoints else "HP: (you decide!)"

    user_msg = (
        f"Create a YouMon trading card for:\n"
        f"Monster name: {card.monster_name}\n"
        f"Description: {card.description or 'You decide the look!'}\n"
        f"{hp_line}\n"
        f"Attacks:\n{attack_lines}\n"
        f"Please generate the card image and provide the JSON with the attack names, "
        f"damage values, flavor text, and monster type."
    )

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[YouMon] Calling GPT-5.4 for '{card.monster_name}' (attempt {attempt}/{MAX_RETRIES})...")
        t0 = time.time()

        try:
            response = client.responses.create(
                model="gpt-5.4",
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                tools=[{"type": "image_generation"}],
            )
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "moderation" in error_str.lower() or "safety" in error_str.lower():
                print(f"[YouMon]   Moderation block on attempt {attempt}, retrying...")
                time.sleep(1)
                continue
            raise

        elapsed = time.time() - t0
        print(f"[YouMon] GPT-5.4 responded in {elapsed:.1f}s")

        # Extract image and text from response
        card_image = None
        text_data = {}

        for output in response.output:
            print(f"[YouMon]   output type: {output.type}")
            if output.type == "image_generation_call":
                image_bytes = base64.b64decode(output.result)
                card_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
                print(f"[YouMon]   image size: {card_image.size}")

            elif output.type == "message":
                # Parse JSON from the text content
                for content in output.content:
                    if content.type == "output_text":
                        text = content.text
                        print(f"[YouMon]   text: {text[:200]}")
                        json_str = _extract_json(text)
                        if json_str:
                            text_data = json.loads(json_str)

        if card_image is None:
            print(f"[YouMon]   No image in response on attempt {attempt}, retrying...")
            last_error = RuntimeError("GPT-5.4 did not generate a card image")
            time.sleep(1)
            continue

        print(f"[YouMon] Card generated: type={text_data.get('monster_type')}, "
              f"flavor={text_data.get('flavor_text', '')[:60]}")
        return card_image, text_data

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
