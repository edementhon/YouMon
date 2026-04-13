#!/bin/bash
# YouMon - Monster Card Maker launcher
cd "$(dirname "$0")"

# First run: set up venv and install dependencies
if [ ! -d .venv ]; then
    echo "First launch — setting up YouMon..."
    sudo apt-get install -y python3-tk 2>/dev/null
    python3 -m venv .venv
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

.venv/bin/python main.py
