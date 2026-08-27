"""Shared plumbing for the YouMon evals: model variants, generation, costing.

Evals call the app's own api.card_gen so that a prompt change ships to the
eval automatically. Nothing here reimplements card generation.
"""
from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import pathlib
import time
from typing import Callable

from PIL import Image

import config
from api import card_gen
from core.card_model import Attack, CardData
from evals.corpus import MonsterPrompt

RESULTS_DIR = pathlib.Path(__file__).parent / "results"

# Model variants worth comparing. "default" tracks whatever the app ships.
VARIANTS: dict[str, config.GenSettings] = {
    "default": config.DEFAULT_GEN,
    "terra-img2-med": config.GenSettings("gpt-5.6-terra", "gpt-image-2", "medium", "1200x1680"),
    "terra-img2-high": config.GenSettings("gpt-5.6-terra", "gpt-image-2", "high", "1200x1680"),
    "luna-img2-med": config.GenSettings("gpt-5.6-luna", "gpt-image-2", "medium", "1200x1680"),
    "sol-img2-med": config.GenSettings("gpt-5.6-sol", "gpt-image-2", "medium", "1200x1680"),
    # A/B arm: identical to default except the prompt forbids franchise names in
    # the card text. Paired with "default" this measures whether letting a card
    # say "Pokemon" costs anything in refusals or silently dropped renders.
    "brand-free": config.GenSettings("gpt-5.6-terra", "gpt-image-2", "medium",
                                     "1200x1680", allow_brand_text=False),
    # What YouMon shipped before this round. gpt-image-1 shuts down 2026-10-23,
    # so this variant is a baseline for comparison, not an option.
    "legacy": config.GenSettings("gpt-5.4", "gpt-image-1", "auto", "1024x1536"),
    # Cheapest thing that will draw a card. Kept because it is the obvious
    # cost-cutting suggestion, and the eval is how we show it is a bad one.
    "mini": config.GenSettings("gpt-5.6-luna", "gpt-image-1-mini", "medium", "1024x1536"),
}

# --- Costing -------------------------------------------------------------
# The Responses API reports the orchestrator's text tokens but NOT the image
# tokens, which are billed separately and invisibly. These counts were measured
# directly against v1/images/generations on 2026-08-27; re-measure with
# evals/measure_image_tokens.py if OpenAI reprices or retunes a model.
IMAGE_TOKENS: dict[tuple[str, str, str], int] = {
    ("gpt-image-2", "1024x1536", "low"): 158,
    ("gpt-image-2", "1024x1536", "medium"): 1372,
    ("gpt-image-2", "1200x1680", "low"): 177,
    ("gpt-image-2", "1200x1680", "medium"): 1639,
    ("gpt-image-2", "1200x1680", "high"): 6651,
}

# $ per 1M image output tokens, from OpenAI's pricing page (2026-08-27).
IMAGE_OUTPUT_PRICE = {
    "gpt-image-2": 30.0,
    "gpt-image-1.5": 32.0,
    "gpt-image-1": 40.0,
    "gpt-image-1-mini": 8.0,
}

# Published per-image prices for the models we did not measure, so the legacy
# baselines still cost out. From each model's page on developers.openai.com.
PUBLISHED_PER_IMAGE: dict[tuple[str, str, str], float] = {
    ("gpt-image-1", "1024x1536", "low"): 0.016,
    ("gpt-image-1", "1024x1536", "medium"): 0.063,
    ("gpt-image-1", "1024x1536", "high"): 0.25,
    ("gpt-image-1-mini", "1024x1536", "low"): 0.006,
    ("gpt-image-1-mini", "1024x1536", "medium"): 0.015,
    ("gpt-image-1-mini", "1024x1536", "high"): 0.052,
    ("gpt-image-1.5", "1024x1536", "low"): 0.013,
    ("gpt-image-1.5", "1024x1536", "medium"): 0.05,
    ("gpt-image-1.5", "1024x1536", "high"): 0.20,
}

# $ per 1M tokens, (input, output).
TEXT_PRICE = {
    "gpt-5.6-sol": (4.00, 20.00),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
}

# Measured orchestrator usage for one card: ~3.9k in, ~0.7k out.
TYPICAL_TEXT_IN, TYPICAL_TEXT_OUT = 3900, 680


def image_cost(s: config.GenSettings) -> float | None:
    """Dollars for one generated image, or None if we have no number for it."""
    key = (s.image_model, s.image_size, s.image_quality)
    if key in IMAGE_TOKENS:
        return IMAGE_TOKENS[key] * IMAGE_OUTPUT_PRICE[s.image_model] / 1e6
    return PUBLISHED_PER_IMAGE.get(key)


def text_cost(s: config.GenSettings) -> float | None:
    price = TEXT_PRICE.get(s.text_model)
    if not price:
        return None
    return (TYPICAL_TEXT_IN * price[0] + TYPICAL_TEXT_OUT * price[1]) / 1e6


def card_cost(s: config.GenSettings) -> float | None:
    """Dollars for one card front. 'auto' quality is unpriceable in advance."""
    img, txt = image_cost(s), text_cost(s)
    if img is None or txt is None:
        return None
    return img + txt


# --- Generation ----------------------------------------------------------

@dataclasses.dataclass
class GenOutcome:
    key: str
    band: str
    variant: str
    status: str           # "ok" | "refused" | "error"
    seconds: float
    # One entry per API round trip, e.g. ["blocked", "ok"] means the first
    # wording was rejected and the first reword got through.
    attempts: list[str] = dataclasses.field(default_factory=list)
    image_path: str = ""
    image_size: tuple[int, int] | None = None
    text_data: dict = dataclasses.field(default_factory=dict)
    detail: str = ""


def generate_one(
    prompt: MonsterPrompt,
    variant: str,
    out_dir: pathlib.Path,
    quality_override: str | None = None,
) -> GenOutcome:
    """Run one corpus prompt through the app's real generation path."""
    settings = VARIANTS[variant]
    if quality_override:
        settings = dataclasses.replace(settings, image_quality=quality_override)
    card = CardData(
        user_name="Eval",
        monster_name=prompt.monster_name,
        description=prompt.description,
        hitpoints=0,
        attacks=[Attack(description=d) for d in prompt.attacks]
        or [Attack(), Attack(), Attack()],
    )
    while len(card.attacks) < 3:
        card.attacks.append(Attack())

    attempts: list[str] = []
    t0 = time.time()
    try:
        img, text_data = card_gen.generate_card(
            card, settings, on_attempt=lambda _n, outcome: attempts.append(outcome)
        )
    except card_gen.CardRefused as e:
        return GenOutcome(prompt.key, prompt.band, variant, "refused",
                          round(time.time() - t0, 1), attempts,
                          detail=str(e.detail)[:300])
    except Exception as e:  # noqa: BLE001
        return GenOutcome(prompt.key, prompt.band, variant, "error",
                          round(time.time() - t0, 1), attempts,
                          detail=f"{type(e).__name__}: {e}"[:300])

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{variant}__{prompt.key}.png"
    img.convert("RGB").save(path)
    return GenOutcome(prompt.key, prompt.band, variant, "ok",
                      round(time.time() - t0, 1), attempts, image_path=str(path),
                      image_size=img.size, text_data=text_data)


def generate_many(
    prompts: list[MonsterPrompt],
    variant: str,
    out_dir: pathlib.Path,
    workers: int = 6,
    on_done: Callable[[GenOutcome], None] | None = None,
    quality_override: str | None = None,
) -> list[GenOutcome]:
    """Generate in parallel. Results are written per-item as they land so a
    crash or a Ctrl-C partway through still leaves usable data."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[GenOutcome] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(generate_one, p, variant, out_dir, quality_override): p
            for p in prompts
        }
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            results.append(r)
            (out_dir / f"{variant}__{r.key}.json").write_text(
                json.dumps(dataclasses.asdict(r), indent=2)
            )
            if on_done:
                on_done(r)
    results.sort(key=lambda r: (r.band, r.key))
    return results


def load_image(path: str) -> Image.Image:
    return Image.open(path)
