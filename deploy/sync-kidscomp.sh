#!/usr/bin/env bash
# Sync YouMon code to kidscomp. Nondestructive by construction:
#
#   - the payload is `git archive HEAD`, so it can only ever contain tracked
#     files. cards/, config.json and .venv/ are gitignored and cannot ride along
#     even by accident.
#   - nothing is deleted on the Pi, ever. Files are overwritten in place.
#   - the current code is tarred to a timestamped backup first (code only, a
#     few hundred KB -- the 2.5G of cards is not copied anywhere).
#   - the new code is staged and import-checked under the Pi's own Python
#     before a single file in the live directory is touched. A failed check
#     aborts before the install step.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
REMOTE=kidscomp
APP=/home/pi/YouMon
TS=$(date +%Y%m%d-%H%M%S)
STAGE=/home/pi/.youmon-stage-$TS
BACKUP=/home/pi/youmon-code-backup-$TS.tar.gz

echo "=== 1. building payload from committed tree ==="
cd "$REPO"
git archive --format=tar HEAD | gzip > /tmp/youmon-sync.tar.gz
echo "payload: $(du -h /tmp/youmon-sync.tar.gz | cut -f1)"
echo "contents:"
tar tzf /tmp/youmon-sync.tar.gz | sed 's/^/  /'

echo
echo "=== 2. refusing to ship anything it should not ==="
if tar tzf /tmp/youmon-sync.tar.gz | grep -qE '^(cards/|config\.json$|\.venv/)'; then
  echo "ABORT: payload contains cards, config.json, or venv"; exit 1
fi
echo "clean: no cards/, no config.json, no .venv/"

echo
echo "=== 3. staging on $REMOTE ==="
ssh "$REMOTE" "mkdir -p $STAGE"
scp -q /tmp/youmon-sync.tar.gz "$REMOTE:$STAGE/payload.tar.gz"
ssh "$REMOTE" "cd $STAGE && tar xzf payload.tar.gz && rm payload.tar.gz && ls"

echo
echo "=== 4. import-checking staged code under the Pi's Python ==="
ssh "$REMOTE" "cd $STAGE && cp $APP/config.json . 2>/dev/null; \
  $APP/.venv/bin/python -c \"
import sys
sys.path.insert(0, '.')
print('python', sys.version.split()[0])
import config, main
from api import card_gen, back_gen, openai_client
from core import card_model, storage, print_layout
import openai
print('openai', openai.__version__)
print('settings:', config.DEFAULT_GEN)
print('prompt builds:', len(card_gen.build_system_prompt(True)), 'chars')
# The staged launch.sh skips setup only if the live venv imports these, and
# starts the app only if a key loads; check both before installing it.
import tkinter, PIL, reportlab
assert config.load_api_key(), 'staged config.py finds no API key in config.json'
print('launcher preflight: venv ok, key loads')
print('IMPORT CHECK PASSED')
\"" || { echo "ABORT: staged code failed to import on the Pi. Live install untouched."; exit 1; }

echo
echo "=== 5. backing up current code (no cards) ==="
ssh "$REMOTE" "cd $APP && tar czf $BACKUP \
  --exclude=cards --exclude=.venv --exclude=__pycache__ \
  --exclude='*.pdf' --exclude=.claude-sessions . && \
  echo 'backup: '\$(du -h $BACKUP | cut -f1)' -> $BACKUP'"

echo
echo "=== 6. installing (overwrite only, no deletions) ==="
ssh "$REMOTE" "cd $STAGE && rm -f config.json && \
  cp -rv --preserve=mode api core ui evals config.py main.py requirements.txt \
     README.md launch.sh YouMon.desktop .gitignore config.json.example LICENSE \
     $APP/ 2>&1 | tail -25"

echo
echo "=== 7. verifying the live install ==="
ssh "$REMOTE" "cd $APP && .venv/bin/python -c \"
import config
from api import card_gen
print('live settings:', config.DEFAULT_GEN)
print('image model :', config.DEFAULT_GEN.image_model, config.DEFAULT_GEN.image_size)
\" && echo 'cards still present:' \$(ls cards/card_*.json 2>/dev/null | wc -l) && \
  echo 'cards dir size:' \$(du -sh cards | cut -f1)"

echo
echo "=== 8. cleaning up staging ==="
ssh "$REMOTE" "rm -rf $STAGE"
rm -f /tmp/youmon-sync.tar.gz
echo
echo "DONE. Backup of previous code on the Pi: $BACKUP"
