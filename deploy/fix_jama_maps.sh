#!/usr/bin/env bash
# ربط خرائط Google لجما — يقرأ /etc/liftcore/platform.env (نفس LiftCore)
#   cd ~/liftcore/elevator-app && bash deploy/fix_jama_maps.sh

set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
PORT="${PORT:-5002}"
PLATFORM_ENV="/etc/liftcore/platform.env"
DROP_IN="/etc/systemd/system/${SERVICE_NAME}.service.d"

echo "==> Fix Google Maps for $SERVICE_NAME"

if [ ! -f "$PLATFORM_ENV" ]; then
  echo "ERROR: $PLATFORM_ENV missing"
  echo "  Create it with GOOGLE_MAPS_API_KEY=... (same as LiftCore)"
  exit 1
fi
if ! grep -q '^GOOGLE_MAPS_API_KEY=' "$PLATFORM_ENV"; then
  echo "ERROR: GOOGLE_MAPS_API_KEY not set in $PLATFORM_ENV"
  exit 1
fi

sudo mkdir -p "$DROP_IN"
printf '%s\n' '[Service]' "EnvironmentFile=$PLATFORM_ENV" | sudo tee "$DROP_IN/platform-env.conf" >/dev/null
echo "  drop-in: $DROP_IN/platform-env.conf"

sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE_NAME"
sleep 2
sudo systemctl is-active "$SERVICE_NAME"

echo ""
echo "==> API check (port $PORT)"
curl -sS --max-time 5 "http://127.0.0.1:${PORT}/api/version" || true
echo ""
echo ""
echo "==> Done"
echo "  1) Google Cloud → API key → add referrer: https://jama.liftcoreapp.com/*"
echo "  2) Browser: https://jama.liftcoreapp.com/clients → Ctrl+Shift+R"
echo "  3) F12 Console — if RefererNotAllowedMapError → fix referrers in Google Cloud"
