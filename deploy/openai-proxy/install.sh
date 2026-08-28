#!/usr/bin/env bash
# Install the OpenAI-only CONNECT proxy as a system service on Blackwell.
# Run on the HOST (not in the container):
#
#   cd ~/Projects/ClaudeSkills/YouMon/deploy/openai-proxy && ./install.sh
#
# Idempotent: safe to re-run. Needs sudo for /usr/local/bin and the unit file.
set -euo pipefail

BIN_SRC="$(cd "$(dirname "$0")" && pwd)/openai-proxy"
BIN_DST=/usr/local/bin/openai-proxy
UNIT=/etc/systemd/system/openai-proxy.service
CLIENT_IP=${CLIENT_IP:-192.168.1.25}          # kidscomp
ALLOW=${ALLOW:-api.openai.com}
PORT=${PORT:-3128}

[ -x "$BIN_SRC" ] || { echo "missing binary: $BIN_SRC"; exit 1; }

echo "installing $BIN_SRC -> $BIN_DST"
sudo install -m 0755 "$BIN_SRC" "$BIN_DST"

echo "writing $UNIT"
sudo tee "$UNIT" >/dev/null <<UNITEOF
[Unit]
Description=OpenAI-only CONNECT proxy (egress allowlist for kidscomp)
Documentation=file://$(cd "$(dirname "$0")" && pwd)/main.go
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=$BIN_DST -listen 0.0.0.0:$PORT -allow $ALLOW -clients $CLIENT_IP
Restart=always
RestartSec=2

# It needs a listening socket and outbound TCP. Nothing else.
DynamicUser=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_INET AF_INET6
RestrictNamespaces=yes
LockPersonality=yes
MemoryMax=128M

[Install]
WantedBy=multi-user.target
UNITEOF

sudo systemctl daemon-reload
sudo systemctl enable --now openai-proxy.service
sudo systemctl restart openai-proxy.service
sleep 1

echo
echo "=== status ==="
systemctl --no-pager --lines=5 status openai-proxy.service || true

echo
echo "=== smoke test from this host ==="
echo -n "  allowed  (api.openai.com): "
curl -s --max-time 20 -x "http://127.0.0.1:$PORT" -o /dev/null -w "http=%{http_code} (401 = tunnel works, no api key sent)\n" \
  https://api.openai.com/v1/models || echo "FAILED"
echo -n "  blocked  (example.com):    "
curl -s --max-time 10 -x "http://127.0.0.1:$PORT" -o /dev/null -w "http=%{http_code}\n" \
  https://example.com/ 2>/dev/null || echo "refused (correct)"

echo
echo "Listening on 0.0.0.0:$PORT, accepting only $CLIENT_IP, allowing only $ALLOW."
echo "Logs: journalctl -u openai-proxy -f"
