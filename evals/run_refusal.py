"""Guardrail eval: how often does YouMon tell a six-year-old no?

    python -m evals.run_refusal
    python -m evals.run_refusal --variant legacy --band ip_adjacent

Success is a card coming back at all. Whether it is a *good* card is
run_quality.py's job. Runs at low image quality by default because refusals are
decided from the prompt, not the pixels, and low costs a fifth of a cent.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import pathlib
import sys

from evals import corpus, harness


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="default", choices=sorted(harness.VARIANTS))
    ap.add_argument("--band", default=None, choices=sorted(corpus.BANDS))
    ap.add_argument("--quality", default="low",
                    help="image quality for this run (low keeps it cheap)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="runs per prompt; refusals are stochastic, so >1 for a real number")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    prompts = corpus.by_band(args.band) if args.band else corpus.PROMPTS
    prompts = [p for p in prompts for _ in range(args.repeat)]

    out_dir = harness.RESULTS_DIR / "refusal" / args.variant
    settings = harness.VARIANTS[args.variant]
    per_card = harness.card_cost(
        dataclasses.replace(settings, image_quality=args.quality)
    )
    est = f"~${per_card * len(prompts):.2f}" if per_card else "unknown"
    print(f"variant={args.variant} prompts={len(prompts)} quality={args.quality} "
          f"estimated cost {est}\n")

    def progress(r: harness.GenOutcome):
        mark = {"ok": "ok  ", "refused": "NO  ", "error": "ERR "}[r.status]
        trail = "->".join(r.attempts) or "-"
        print(f"  {mark} {r.band:<12} {r.key:<16} {r.seconds:>6.1f}s  {trail}")

    results = harness.generate_many(
        prompts, args.variant, out_dir, workers=args.workers,
        on_done=progress, quality_override=args.quality,
    )

    # --- Summary ---------------------------------------------------------
    by_band: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in results:
        by_band[r.band][r.status] += 1

    print(f"\n{'band':<14}{'n':>4}{'ok':>5}{'refused':>9}{'error':>7}{'first-try':>11}")
    total = collections.Counter()
    first_try_ok = 0
    for band in sorted(by_band):
        c = by_band[band]
        n = sum(c.values())
        ft = sum(1 for r in results if r.band == band and r.attempts[:1] == ["ok"])
        first_try_ok += ft
        total.update(c)
        print(f"{band:<14}{n:>4}{c['ok']:>5}{c['refused']:>9}{c['error']:>7}"
              f"{ft}/{n:<8}")
    n = sum(total.values())
    print(f"{'ALL':<14}{n:>4}{total['ok']:>5}{total['refused']:>9}{total['error']:>7}"
          f"{first_try_ok}/{n:<8}")
    print(f"\nrefusal rate: {total['refused'] / n:.1%}   "
          f"clean first try: {first_try_ok / n:.1%}")

    # Per-attempt outcomes across every round trip. "no_image" is the one to
    # watch: the call succeeds, bills, and comes back with no pixels, which is
    # what a silent output-moderation drop looks like from the client side.
    attempt_outcomes = collections.Counter(o for r in results for o in r.attempts)
    total_attempts = sum(attempt_outcomes.values())
    print(f"attempts: {total_attempts} -> " +
          ", ".join(f"{k}={v}" for k, v in sorted(attempt_outcomes.items())))

    for r in results:
        if r.status != "ok":
            print(f"\n[{r.status}] {r.key}: {r.detail[:200]}")

    summary = {
        "variant": args.variant,
        "quality": args.quality,
        "n": n,
        "refusal_rate": total["refused"] / n,
        "first_try_rate": first_try_ok / n,
        "attempt_outcomes": dict(attempt_outcomes),
        "by_band": {b: dict(c) for b, c in by_band.items()},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out_dir}/summary.json")
    # A refusal in the plain band is a real regression; fail the run for it.
    return 1 if by_band["plain"]["refused"] else 0


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
