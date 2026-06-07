#!/usr/bin/env bash
# LiftCore — تحديث سريع على Google Cloud VM
# الاستخدام على السيرفر:
#   cd /var/www/elevator-app   # أو مسار مشروعك
#   bash deploy/gcp_update.sh

set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SERVICE_NAME="${SERVICE_NAME:-liftcore}"
VENV="${VENV:-$APP_DIR/.venv}"

echo "==> LiftCore update in $APP_DIR"
cd "$APP_DIR"

echo "==> git pull"
git pull origin main

if [ -d "$VENV" ]; then
  echo "==> pip install"
  source "$VENV/bin/activate"
  pip install -q flask flask-sqlalchemy gunicorn 2>/dev/null || true
else
  echo "==> no venv at $VENV — skipping pip"
fi

echo "==> DB migrations (create_all on startup)"
# الأعمدة الجديدة name_en تُضاف تلقائياً عند تشغيل app.py

if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
  echo "==> restart systemd: $SERVICE_NAME"
  sudo systemctl restart "$SERVICE_NAME"
elif command -v supervisorctl >/dev/null 2>&1; then
  echo "==> restart supervisor"
  sudo supervisorctl restart "$SERVICE_NAME" || sudo supervisorctl restart all
else
  echo "==> restart manually (systemd service not found)"
  echo "    sudo systemctl restart $SERVICE_NAME"
fi

echo "==> Done. Check: https://app.liftcoreapp.com"
