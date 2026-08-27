# YouMon evals

Two questions decide whether YouMon is any good, and neither is answerable by
staring at one card:

1. **Does it refuse?** A six-year-old describes his monster as "like Pikachu but
   a fox". If the app says no, he stops using it. `run_refusal.py` measures how
   often that happens.
2. **Are the cards good?** Cheap image models draw pretty monsters and then
   misspell the attack names. `run_quality.py` generates cards at real settings
   and has a vision model grade them on craft *and* on whether a kid would want
   the card.

Both import the app's own `api/card_gen.py`, so a prompt change is picked up by
the evals automatically. Results land in `evals/results/` (gitignored).

## Running

```bash
python -m evals.run_refusal                       # all 19 prompts, ~$0.40
python -m evals.run_refusal --band ip_adjacent --repeat 3
python -m evals.run_quality --variants default mini
python -m evals.measure_image_tokens              # re-measure prices, ~$0.26
```

Every runner prints a cost estimate before it spends anything. `run_refusal`
exits non-zero if a prompt in the `plain` band gets refused, so it works as a
gate.

## Cost

The Responses API reports the orchestrator's text tokens but **not** the image
tokens, which are billed separately and never appear in the response. So
`harness.py` carries a measured table instead. Numbers below were measured
against `v1/images/generations` on 2026-08-27; re-run `measure_image_tokens.py`
after any OpenAI repricing.

| gpt-image-2 | low | medium | high |
|---|---|---|---|
| 1024x1536 | 158 tok / $0.005 | 1372 tok / $0.041 | — |
| 1200x1680 | 177 tok / $0.005 | 1639 tok / $0.049 | 6651 tok / $0.200 |

Add ~$0.016 for the `gpt-5.6-terra` orchestrator, or ~$0.002 on `gpt-5.6-luna`.

## Reading the results

`run_refusal` reports, per band, how many cards came back and how many arrived
on the **first** try. First-try matters on its own: each reword is another
30-40 second wait, and the app looks broken while it happens.

`run_quality` scores 0-5 on four axes and combines them
`0.3*text + 0.25*layout + 0.25*art + 0.2*appeal`. Craft outweighs art on
purpose — a gorgeous card that says `HIP 90` is still a ruined card, and craft
is exactly where the cheap models fall over.

**Know what this eval is for.** The absolute scores saturate: on `gpt-image-2`
nearly every card comes back 5/5, so the number cannot rank two good models
against each other. What it does reliably is catch a card falling off a cliff —
`mini` scores 3.42 with 0% printable against 5.00 and ~90% for `gpt-image-2`.
Treat it as a regression gate, and read the flags rather than the average. If
you ever need real ranking between two good variants, absolute scoring is the
wrong tool; show the judge two cards and ask which is better.

Watch these flags in the output:

- `misspelled=[...]` — garbled text in the printed card. The main failure mode.
- `white-margin` — frame doesn't bleed to the edge, so the cut card has a border.
- `LOOKS-LIKE-EXISTING-IP` — the judge thinks this is a copy, not an original
  creature in a similar style. Should stay at zero; the app is supposed to take
  inspiration and invent.

## Adding prompts

Put them in `corpus.py` in a child's actual voice, tagged with the band they
probe. Do not tidy up the phrasing — the awkward wording is the test.
