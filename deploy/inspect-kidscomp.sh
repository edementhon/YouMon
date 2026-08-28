#!/usr/bin/env bash
# Read-only survey of the YouMon install on kidscomp. Touches nothing.
# Run on the host:  bash inspect-kidscomp.sh
set -uo pipefail

ssh kidscomp 'bash -s' <<'REMOTE'
set -uo pipefail
echo "=== host ==="
uname -a; echo "user: $(whoami)"; echo "home: $HOME"

echo; echo "=== where is YouMon ==="
for d in ~/YouMon ~/youmon ~/Desktop/YouMon /opt/YouMon /home/pi/YouMon; do
  [ -d "$d" ] && echo "FOUND: $d"
done
find "$HOME" -maxdepth 3 -iname "YouMon" -type d 2>/dev/null | head

APP=$(find "$HOME" -maxdepth 3 -iname "YouMon" -type d 2>/dev/null | head -1)
if [ -z "$APP" ]; then echo "!! no YouMon directory found"; exit 0; fi
echo; echo "APP=$APP"

echo; echo "=== install shape ==="
ls -la "$APP"
echo "--- is it a git checkout?"
if [ -d "$APP/.git" ]; then
  git -C "$APP" remote -v
  git -C "$APP" log --oneline -3
  git -C "$APP" status --short | head -20
  echo "branch: $(git -C "$APP" branch --show-current)"
else
  echo "no .git -- copied, not cloned"
fi

echo; echo "=== the kids' cards (DO NOT TOUCH) ==="
if [ -d "$APP/cards" ]; then
  echo "card json files: $(ls "$APP"/cards/card_*.json 2>/dev/null | wc -l)"
  echo "png files:       $(ls "$APP"/cards/*.png 2>/dev/null | wc -l)"
  echo "cards dir size:  $(du -sh "$APP/cards" 2>/dev/null | cut -f1)"
  echo "newest card:     $(ls -t "$APP"/cards/*.json 2>/dev/null | head -1)"
else
  echo "no cards/ directory"
fi

echo; echo "=== python + deps ==="
python3 -V
[ -d "$APP/.venv" ] && { echo "venv present:"; "$APP/.venv/bin/python" -V 2>&1; \
  "$APP/.venv/bin/python" -c "import openai,PIL,reportlab;print('openai',openai.__version__)" 2>&1 | tail -2; } \
  || echo "no .venv"
python3 -c "import tkinter; print('tkinter ok')" 2>&1 | tail -1

echo; echo "=== config (presence only, no secrets printed) ==="
[ -f "$APP/config.json" ] && echo "config.json present, $(wc -c < "$APP/config.json") bytes" || echo "no config.json"
[ -n "${OPENAI_API_KEY:-}" ] && echo "OPENAI_API_KEY set in env" || echo "OPENAI_API_KEY not in env"

echo; echo "=== how it launches ==="
[ -f "$APP/launch.sh" ] && { echo "--- launch.sh:"; cat "$APP/launch.sh"; }
echo "--- desktop entries:"
grep -rl -i youmon ~/.local/share/applications ~/Desktop /usr/share/applications 2>/dev/null | while read -r f; do
  echo "  $f"; sed -n '1,15p' "$f"; done
echo "--- autostart:"
ls -la ~/.config/autostart 2>/dev/null | grep -i youmon || echo "  none"
echo "--- systemd user units:"
systemctl --user list-unit-files 2>/dev/null | grep -i youmon || echo "  none"
echo "--- cron:"
crontab -l 2>/dev/null | grep -i youmon || echo "  none"

echo; echo "=== disk ==="
df -h "$HOME" | tail -1
REMOTE
