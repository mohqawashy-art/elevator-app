#!/usr/bin/env bash
# LiftCore — تحديث على Google Cloud VM
# على السيرفر:
#   bash deploy/gcp_update.sh

set -euo pipefail

if [ -n "${APP_DIR:-}" ] && [ -d "$APP_DIR/.git" ]; then
  :
elif [ -d "$HOME/liftcore/elevator-app/.git" ]; then
  APP_DIR="$HOME/liftcore/elevator-app"
elif [ -d "/var/www/elevator-app/.git" ]; then
  APP_DIR="/var/www/elevator-app"
else
  APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
fi

SERVICE_NAME="${SERVICE_NAME:-liftcore}"
VENV="${VENV:-$APP_DIR/.venv}"

echo "==> LiftCore update in $APP_DIR"
cd "$APP_DIR"

echo "==> git pull"
git fetch origin main
git pull --ff-only origin main

if [ -d "$VENV" ]; then
  echo "==> pip install"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  if [ -f requirements.txt ]; then
    pip install -q -r requirements.txt
  else
    pip install -q flask flask-sqlalchemy gunicorn werkzeug
  fi
else
  echo "==> no venv at $VENV — skipping pip"
fi

echo "==> restart service: $SERVICE_NAME"
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl restart "$SERVICE_NAME"
  sleep 2
  sudo systemctl is-active "$SERVICE_NAME"
elif command -v supervisorctl >/dev/null 2>&1; then
  sudo supervisorctl restart "$SERVICE_NAME" || sudo supervisorctl restart all
else
  echo "WARN: restart manually: sudo systemctl restart $SERVICE_NAME"
fi

echo "==> verify"
test -f "$APP_DIR/static/liftcore-dates.js" && echo "  liftcore-dates.js OK"
test -f "$APP_DIR/templates/purchase-orders.html" && echo "  purchase-orders.html OK"
grep -q "purchase-orders" "$APP_DIR/app.py" && echo "  purchase-orders route OK"

echo ""
echo "==> Done — https://app.liftcoreapp.com"
echo "    تحقق: /inventory و /purchase-orders"
