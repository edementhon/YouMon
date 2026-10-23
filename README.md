# YouMon - Kids' Monster Card Maker

YouMon is a desktop app that lets you make your own Japanese-style collectible card game cards, with {yournamehere}Mon on the back, so if your name is Bob, yours will be BobMon. Enter a monster name and description, and the AI generates a complete card with artwork, attacks, stats, and flavor text — all in the style of Japanese collectible card games. And then, for the most important part - they're printable! **File > Print Layout** will lay out 9 cards on a sheet. If you have a nice photo printer around, get some glossy card stock, it makes the cards really pop. We've had good luck with this glossy card stock: https://amzn.to/4c5vqQU

## Features

- **AI-generated cards** — a single API call creates both the card artwork and game stats
- **Personalized card backs** — each player gets a custom "{Name}Mon" back design
- **Card collection** — browse, search, and manage all your saved cards
- **Print-ready PDF export** — configurable grid layout with crop marks, duplex support, and column mirroring for double-sided printing

## Setup

You need two things: an OpenAI API key, and Python 3.10 or newer. Plan on
about 15 minutes the first time.

### 1. Get an OpenAI API key

1. Sign in at [platform.openai.com](https://platform.openai.com/).
2. Add credit under **Settings > Billing**. The API is prepaid; $5 is about
   70 cards (see [Models and cost](#models-and-cost)). Setting a monthly
   budget there is a good idea if kids will be pressing the button.
3. Verify your organization under **Settings > Organization > General >
   Verify Organization**. OpenAI requires this (an ID check) for its image
   models; without it every card fails. It can take a few minutes to take
   effect after it says you're verified.
4. Create a key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
   and copy it (it's shown only once).

The key is stored in plain text in `config.json` on your computer, and anyone
who has it can spend your credit, so don't share that file.

### 2. Install and run: macOS and Linux

```bash
git clone https://github.com/edementhon/YouMon.git
cd YouMon
cp config.json.example config.json
# open config.json in a text editor and replace sk-your-key-here with your key
./launch.sh
```

(No git? Use **Code > Download ZIP** on GitHub and unzip it.)

The first run sets up a private Python environment in `.venv` and installs
what YouMon needs, which takes a minute or two. After that, `./launch.sh` just
starts the app. If your Python is missing a piece (often `tkinter`, which draws
the window), the launcher tells you the exact command to install it.

- **macOS:** Python from [python.org](https://www.python.org/downloads/) has
  everything. Homebrew's Python needs the window toolkit added:
  `brew install python-tk@3.12` (match your Python version).
- **Linux desktop icon:** `YouMon.desktop` assumes the folder is at `~/YouMon`.
  Fix the `Exec=` line if it's elsewhere, then copy the file to
  `~/.local/share/applications/`.

### 2. Install and run: Windows

1. Install Python from [python.org](https://www.python.org/downloads/). On the
   first installer screen, tick **Add python.exe to PATH**.
2. Download YouMon with **Code > Download ZIP** on GitHub and unzip it.
3. In the YouMon folder, copy `config.json.example` to `config.json`, open it in
   Notepad, and replace `sk-your-key-here` with your key.
4. Open PowerShell in that folder (in Explorer: **File > Open Windows
   PowerShell**, or Shift+right-click) and run:

   ```powershell
   py -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   .venv\Scripts\python main.py
   ```

   Next time, only the last line is needed.

We run YouMon on Linux and haven't tested Windows ourselves. If something
breaks, please open an issue.

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

`gpt-image-2` is the only image model with a future: `gpt-image-1` shut down
on 2026-10-23, and `gpt-image-1.5` and `gpt-image-1-mini` follow on 2026-12-01.

## Evals

`evals/` measures the two things that actually break this app: guardrail
refusals (a kid describing his monster as "like Pikachu but a fox" must still
get a card) and card quality (cheap image models misspell the attack names).
See [evals/README.md](evals/README.md).

## Printing!

We've found that a photo printer plus glossy card stock makes them look awesome. This card stock has been great: https://amzn.to/4c5vqQU

Just make sure you set the printer settings to glossy photo paper, up the print quality, that sort of thing.

## The deploy folder

`deploy/` holds scripts for our own setup (a Raspberry Pi that reaches the
internet only through a filtering proxy). You don't need any of it.

## License

MIT — see [LICENSE](LICENSE).
