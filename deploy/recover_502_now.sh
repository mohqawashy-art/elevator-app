#!/usr/bin/env bash
# استعادة فورية من 502 — انسخ هذا السطر في GCP SSH:
#   cd ~/liftcore/elevator-app && git pull origin main && bash deploy/recover_502_now.sh
set -euo pipefail

for try in "$HOME/liftcore/elevator-app" "/var/www/elevator-app"; do
  if [ -d "$try/.git" ]; then APP_DIR="$try"; break; fi
done
APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
cd "$APP_DIR"

echo "=============================================="
echo "  LiftCore recover_502_now"
echo "  $(date)"
echo "=============================================="

git fetch origin main
git pull --ff-only origin main

bash "$APP_DIR/deploy/ensure_platform_env.sh"
bash "$APP_DIR/deploy/gcp_update.sh"

echo ""
echo "==> فحص محلي"
for PORT in 5000 5001 8000; do
  OUT="$(curl -sS --max-time 4 "http://127.0.0.1:${PORT}/api/health" 2>/dev/null || true)"
  if echo "$OUT" | grep -q '"ok"'; then
    echo "  OK :${PORT} => $OUT"
    break
  fi
done

echo ""
echo "افتح: https://app.liftcoreapp.com/login"
echo "إن استمر 502: sudo journalctl -u liftcore -n 40 --no-pager"
