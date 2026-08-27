# YouMon - Kids' Monster Card Maker

YouMon is a desktop app that lets you make your own Japanese-style collectible card game cards, with {yournamehere}Mon on the back, so if your name is Bob, yours will be BobMon. Enter a monster name and description, and the AI generates a complete card with artwork, attacks, stats, and flavor text — all in the style of Japanese collectible card games. And then, for the most important part - they're printable! **File > Print Layout** will lay out 9 cards on a sheet. If you have a nice photo printer around, get some glossy card stock, it makes the cards really pop. We've had good luck with this glossy card stock: https://amzn.to/4c5vqQU

## Features

- **AI-generated cards** — a single API call creates both the card artwork and game stats
- **Personalized card backs** — each player gets a custom "{Name}Mon" back design
- **Card collection** — browse, search, and manage all your saved cards
- **Print-ready PDF export** — configurable grid layout with crop marks, duplex support, and column mirroring for double-sided printing

## Requirements

- Python 3.10+
- tkinter (included with Python on most systems; on Linux: `sudo apt-get install python3-tk`)
- An OpenAI API key on an organization that has completed API verification (GPT
  Image models require it)

## Quick Start (Debian/Ubuntu/Raspbian)

1. Clone the repo:
   ```bash
   git clone https://github.com/edementhon/YouMon.git
   cd YouMon
   ```

2. Add your OpenAI API key:
   ```bash
   cp config.json.example config.json
   # Edit config.json and paste your key
   ```

3. Run the launcher (creates the venv, installs dependencies, and starts the app):
   ```bash
   ./launch.sh
   ```

## Manual Setup (macOS / other)

If `launch.sh` doesn't suit your platform, set up manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your API key via environment variable or `config.json` as above, then:

```bash
python main.py
```

On macOS, tkinter is included with Python from python.org or Homebrew. On Linux you may need `sudo apt-get install python3-tk` (or equivalent for your distro).

## How It Works

Enter your name and your monster's name, optionally add a description, HP, and attack ideas. Hit **Generate Card!** and the AI creates a full trading card — artwork, polished attack names, damage values, elemental type, and flavor text.

Cards are saved locally in the `cards/` directory as PNG images (300 DPI, standard 2.5" x 3.5" trading card size) with JSON metadata. Use **File > Print Layout** to export a PDF sheet for printing and cutting out real cards.

## Models and cost

One card front costs about **6.5 cents**: `gpt-5.6-terra` writes the stats and
calls the hosted image tool, and `gpt-image-2` draws the card at 1200x1680
(exactly 2.5:3.5, so it drops into the print layout without stretching).
Card backs are generated once per player name and reused.

All of that lives in `config.GenSettings` if you want to change it. Two knobs
are worth knowing about:

- `image_quality="high"` costs 4x more (~22 cents/card) and takes twice as long,
  for detail that mostly disappears at 2.5 inches wide.
- `text_model="gpt-5.6-luna"` cuts the text cost by 90%, but the attack names
  and flavor text get noticeably blander.

`gpt-image-2` is the only image model with a future — `gpt-image-1` shuts down
2026-10-23, `gpt-image-1.5` and `gpt-image-1-mini` on 2026-12-01.

## Evals

`evals/` measures the two things that actually break this app: guardrail
refusals (a kid describing his monster as "like Pikachu but a fox" must still
get a card) and card quality (cheap image models misspell the attack names).
See [evals/README.md](evals/README.md).

## Printing!

We've found that a photo printer plus glossy card stock makes them look awesome. This card stock has been great: https://amzn.to/4c5vqQU

Just make sure you set the printer settings to glossy photo paper, up the print quality, that sort of thing.

## License

MIT — see [LICENSE](LICENSE).
