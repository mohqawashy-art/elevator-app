#!/usr/bin/env bash
# LiftCore — تحديث فوري من GitHub (شغّل من GCP Console SSH)
#   cd ~/liftcore/elevator-app && bash deploy/server_update_now.sh

set -euo pipefail

for try in "$HOME/liftcore/elevator-app" "/var/www/elevator-app"; do
  if [ -d "$try/.git" ]; then APP_DIR="$try"; break; fi
done
APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"

echo "==> LiftCore server update: $APP_DIR"
cd "$APP_DIR"

echo "==> قبل:"
git log -1 --oneline 2>/dev/null || echo "(no git)"

echo "==> جلب آخر main من GitHub"
git fetch origin main

if ! git pull --ff-only origin main 2>/dev/null; then
  echo "==> pull فشل — مزامنة إجبارية"
  git reset --hard origin/main
fi

echo "==> بعد:"
git log -1 --oneline
test -d installation && echo "  installation/: OK" || { echo "  ERROR: installation/ missing"; exit 1; }

echo "==> تشغيل gcp_update.sh"
bash deploy/gcp_update.sh

echo ""
echo "==> تحقق (يجب install_enabled: true)"
for PORT in 5000 5001 8000; do
  OUT="$(curl -sS --max-time 3 "http://127.0.0.1:${PORT}/api/version" 2>/dev/null || true)"
  if [ -n "$OUT" ]; then echo "  :${PORT} => $OUT"; break; fi
done
echo ""
echo "افتح: https://app.liftcoreapp.com/installation/ (بعد تسجيل الدخول)"
