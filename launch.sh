#!/bin/bash
# YouMon - Monster Card Maker launcher
cd "$(dirname "$0")"

# Refuse to run from anywhere that isn't a YouMon folder. A stray copy of this
# script elsewhere would otherwise take the first-run path below and start an
# apt-get and a from-source pip build in the wrong directory.
if [ ! -f main.py ] || [ ! -f config.py ]; then
    echo "This doesn't look like the YouMon folder ($(pwd)) — stopping."
    exit 1
fi

# First run: set up venv and install dependencies
if [ ! -d .venv ]; then
    echo "First launch — setting up YouMon..."
    sudo apt-get install -y python3-tk 2>/dev/null
    # --system-site-packages so a distro-provided Pillow/reportlab counts,
    # rather than forcing a from-source build on machines without wheels.
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install -r requirements.txt
    echo "Setup complete!"
fi

# Check for API key
if [ ! -f config.json ]; then
    echo ""
    echo "No API key found!"
    echo "Ask a grown-up to create config.json with:"
    echo '  {"openai_api_key": "sk-..."}'
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Optional per-machine settings, kept out of the repo so a sync can't clobber
# them. On kidscomp this points HTTPS_PROXY at the allowlisted egress proxy,
# since that machine is firewalled off the internet at the router.
[ -f local.env ] && . ./local.env

.venv/bin/python main.py
