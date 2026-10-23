#!/bin/bash
# YouMon - Monster Card Maker launcher (Linux and macOS).
# Sets up a private Python environment in .venv on first run, then starts the app.
cd "$(dirname "$0")"

# Refuse to run from anywhere that isn't a YouMon folder. A stray copy of this
# script elsewhere would otherwise take the first-run path below and start a
# pip install in the wrong directory.
if [ ! -f main.py ] || [ ! -f config.py ]; then
    echo "This doesn't look like the YouMon folder ($(pwd)) — stopping."
    exit 1
fi

fail() {
    echo ""
    echo "$@"
    echo ""
    # Keep the window open when started from a desktop icon.
    [ -t 0 ] && read -r -p "Press Enter to exit..."
    exit 1
}

# Optional per-machine settings, kept out of the repo. On our firewalled Pi
# this points HTTPS_PROXY at an egress proxy; sourced before setup so pip can
# use it too. Most people never need this file.
[ -f local.env ] && . ./local.env

# The venv counts as set up only if it can import everything the app needs.
# A half-built venv (say, pip missing) fails this and gets rebuilt, instead of
# being skipped forever because the folder exists.
venv_ok() {
    [ -x .venv/bin/python ] &&
        .venv/bin/python -c "import tkinter, openai, PIL, reportlab" 2>/dev/null
}

if ! venv_ok; then
    echo "Setting up YouMon (first run, takes a minute or two)..."

    command -v python3 >/dev/null ||
        fail "Python 3 isn't installed. Get Python 3.10 or newer from https://www.python.org/downloads/ (or your package manager), then run ./launch.sh again."
    python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' ||
        fail "YouMon needs Python 3.10 or newer; this is $(python3 --version 2>&1)."

    # Check what's missing up front and name the fix, rather than half-building.
    missing=()
    python3 -c "import tkinter" 2>/dev/null || missing+=(tkinter)
    python3 -c "import ensurepip" 2>/dev/null || missing+=(venv)
    if [ ${#missing[@]} -gt 0 ]; then
        ver=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
        if command -v apt-get >/dev/null; then
            fix="sudo apt-get install python3-tk python3-venv"
        elif command -v dnf >/dev/null; then
            fix="sudo dnf install python3-tkinter"
        elif command -v pacman >/dev/null; then
            fix="sudo pacman -S tk"
        elif command -v brew >/dev/null; then
            fix="brew install python-tk@$ver"
        else
            fix="install Python's tkinter and venv support for your system"
        fi
        fail "Python is missing: ${missing[*]}. To fix, run:

    $fix

then run ./launch.sh again."
    fi

    rm -rf .venv
    # --system-site-packages so a distro-provided Pillow/reportlab counts,
    # rather than forcing a from-source build on machines without wheels
    # (e.g. a 32-bit Raspberry Pi).
    python3 -m venv --system-site-packages .venv &&
        .venv/bin/python -m pip install -r requirements.txt ||
        { rm -rf .venv; fail "Setup failed (see the messages above). Fix the problem and run ./launch.sh again."; }
    venv_ok || { rm -rf .venv; fail "Setup finished but the app's libraries still won't load (see above)."; }
    echo "Setup complete!"
fi

# Check for an API key: the OPENAI_API_KEY environment variable, or config.json.
if ! .venv/bin/python -c "import config, sys; sys.exit(not config.load_api_key())"; then
    fail "No OpenAI API key yet. Ask a grown-up to copy config.json.example to
config.json and paste the key in (the README explains how to get one)."
fi

.venv/bin/python main.py
