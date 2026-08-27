"""Re-measure what an image actually costs, instead of trusting a table.

The Responses API never reports image tokens, so harness.IMAGE_TOKENS is a
hand-maintained table and hand-maintained tables go stale. This asks the Images
API directly, with a throwaway prompt, and prints a block you can paste back
into harness.py.

    python -m evals.measure_image_tokens
    python -m evals.measure_image_tokens --model gpt-image-2 --sizes 1200x1680

Costs roughly $0.26 at the defaults; almost all of it is the one `high` render.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

from api.openai_client import get_client
from evals.harness import IMAGE_OUTPUT_PRICE

PROBE_PROMPT = "a plain red square"


def measure(model: str, size: str, quality: str) -> tuple[str, str, str, int | None, str]:
    try:
        r = get_client().images.generate(
            model=model, prompt=PROBE_PROMPT, n=1, size=size, quality=quality
        )
    except Exception as e:  # noqa: BLE001
        return model, size, quality, None, f"{type(e).__name__}: {e}"[:120]
    tokens = r.usage.output_tokens_details.image_tokens
    return model, size, quality, tokens, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-image-2")
    ap.add_argument("--sizes", nargs="+", default=["1024x1536", "1200x1680"])
    ap.add_argument("--qualities", nargs="+", default=["low", "medium", "high"])
    args = ap.parse_args()

    cases = [(args.model, s, q) for s in args.sizes for q in args.qualities]
    print(f"{len(cases)} probe renders on {args.model}\n")
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(lambda c: measure(*c), cases))

    price = IMAGE_OUTPUT_PRICE.get(args.model)
    print(f"{'size':<12}{'quality':<9}{'tokens':>8}{'$/image':>10}")
    for model, size, quality, tokens, err in rows:
        if err:
            print(f"{size:<12}{quality:<9}  ERROR {err}")
            continue
        cost = tokens * price / 1e6 if price else 0
        print(f"{size:<12}{quality:<9}{tokens:>8}{cost:>10.4f}")

    print("\npaste into evals/harness.py IMAGE_TOKENS:")
    for model, size, quality, tokens, err in rows:
        if not err:
            print(f'    ("{model}", "{size}", "{quality}"): {tokens},')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
