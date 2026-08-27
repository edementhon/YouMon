"""Quality eval: generate cards at real settings and have a vision model grade them.

    python -m evals.run_quality --variants default mini
    python -m evals.run_quality --variants terra-img2-med terra-img2-high --sample 6

Prints a per-variant scorecard with cost per card, so "is high quality worth 4x"
is answered with numbers instead of taste.

This one costs real money — it runs at each variant's actual image quality.
Check the printed estimate before letting it run.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor

from evals import corpus, harness, judge

# A spread across bands: enough variety to catch a model that only handles
# easy prompts, small enough to run for pocket change.
DEFAULT_SAMPLE = ["cloudbunny", "noodlecat", "pikachu_like", "charizard_like",
                  "skeleton", "mecha", "booger", "bareminimum"]


def run_variant(variant: str, prompts: list, workers: int, regrade: bool = False) -> dict:
    out_dir = harness.RESULTS_DIR / "quality" / variant
    print(f"\n=== {variant} ===")

    if regrade:
        # Re-judge images already on disk. Iterating on the rubric shouldn't
        # cost another round of image generation.
        results = []
        for p in prompts:
            path = out_dir / f"{variant}__{p.key}.json"
            if path.exists():
                d = json.loads(path.read_text())
                results.append(harness.GenOutcome(**d))
        print(f"  regrading {len(results)} saved card(s)")
    else:
        def progress(r: harness.GenOutcome):
            print(f"  gen  {r.status:<8} {r.key:<16} {r.seconds:>6.1f}s  {r.image_size}")

        results = harness.generate_many(prompts, variant, out_dir,
                                        workers=workers, on_done=progress)

    ok = [r for r in results if r.status == "ok"]
    lookup = {p.key: p for p in prompts}

    allow_brand = harness.VARIANTS[variant].allow_brand_text

    def grade_one(r):
        p = lookup[r.key]
        try:
            g = judge.judge_card(r.image_path, p.monster_name, p.description,
                                 allow_brand_text=allow_brand)
        except Exception as e:  # noqa: BLE001
            return r.key, {"error": f"{type(e).__name__}: {e}"[:200]}
        return r.key, g

    with ThreadPoolExecutor(max_workers=workers) as ex:
        grades = dict(ex.map(grade_one, ok))

    for key, g in sorted(grades.items()):
        if "error" in g:
            print(f"  JUDGE FAILED {key}: {g['error']}")
            continue
        flags = []
        if g["misspellings"]:
            flags.append(f"misspelled={g['misspellings'][:3]}")
        if g["missing_elements"]:
            flags.append(f"missing={g['missing_elements'][:3]}")
        if not g["border_reaches_edges"]:
            flags.append("white-margin")
        if g.get("brand_names_on_card"):
            flags.append(f"BRAND-ON-CARD={g['brand_names_on_card']}")
        if g["resembles_existing_character"]:
            flags.append("looks-like-existing-character")
        print(f"  judge {key:<16} overall={judge.overall(g):.2f} "
              f"text={g['text_quality']} layout={g['layout_fidelity']} "
              f"art={g['art_quality']} appeal={g['kid_appeal']} "
              f"{'print' if g['printable'] else 'REPRINT'} {' '.join(flags)}")

    good = [g for g in grades.values() if "error" not in g]
    summary = {
        "variant": variant,
        "settings": vars(harness.VARIANTS[variant]) if hasattr(harness.VARIANTS[variant], "__dict__")
                    else harness.VARIANTS[variant].__dict__,
        "generated": len(ok),
        "failed": len(results) - len(ok),
        "cost_per_card": harness.card_cost(harness.VARIANTS[variant]),
        "median_seconds": statistics.median([r.seconds for r in ok]) if ok else None,
        "overall": round(statistics.mean([judge.overall(g) for g in good]), 2) if good else None,
        "text_quality": round(statistics.mean([g["text_quality"] for g in good]), 2) if good else None,
        "layout_fidelity": round(statistics.mean([g["layout_fidelity"] for g in good]), 2) if good else None,
        "art_quality": round(statistics.mean([g["art_quality"] for g in good]), 2) if good else None,
        "kid_appeal": round(statistics.mean([g["kid_appeal"] for g in good]), 2) if good else None,
        "printable_rate": round(sum(g["printable"] for g in good) / len(good), 2) if good else None,
        "cards_with_misspellings": sum(1 for g in good if g["misspellings"]),
        "cards_with_brand_text": sum(1 for g in good if g.get("brand_names_on_card")),
        "grades": grades,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=["default"],
                    choices=sorted(harness.VARIANTS))
    ap.add_argument("--sample", type=int, default=len(DEFAULT_SAMPLE))
    ap.add_argument("--band", default=None, choices=sorted(corpus.BANDS),
                    help="grade a whole band instead of the default spread")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--regrade", action="store_true",
                    help="re-judge cards already in results/ instead of generating new ones")
    args = ap.parse_args()

    if args.band:
        prompts = corpus.by_band(args.band)[:args.sample]
    else:
        keys = DEFAULT_SAMPLE[:args.sample]
        prompts = [p for p in corpus.PROMPTS if p.key in keys]

    est = 0.0
    if not args.regrade:
        for v in args.variants:
            c = harness.card_cost(harness.VARIANTS[v])
            est += (c or 0) * len(prompts)
    judging = 0.016 * len(prompts) * len(args.variants)
    print(f"{len(args.variants)} variant(s) x {len(prompts)} cards, "
          f"generation ~${est:.2f} + judging ~${judging:.2f}"
          f"{' (regrade: no generation)' if args.regrade else ''}")

    summaries = [run_variant(v, prompts, args.workers, args.regrade)
                 for v in args.variants]

    print(f"\n{'variant':<18}{'overall':>8}{'text':>6}{'layout':>8}{'art':>6}"
          f"{'appeal':>8}{'print%':>8}{'$/card':>9}{'secs':>7}")
    for s in sorted(summaries, key=lambda s: -(s["overall"] or 0)):
        cost = f"${s['cost_per_card']:.4f}" if s["cost_per_card"] else "?"
        print(f"{s['variant']:<18}{s['overall'] or 0:>8.2f}{s['text_quality'] or 0:>6.1f}"
              f"{s['layout_fidelity'] or 0:>8.1f}{s['art_quality'] or 0:>6.1f}"
              f"{s['kid_appeal'] or 0:>8.1f}"
              f"{(s['printable_rate'] or 0) * 100:>7.0f}%{cost:>9}"
              f"{s['median_seconds'] or 0:>7.0f}")

    path = harness.RESULTS_DIR / "quality" / "comparison.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summaries, indent=2))
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
