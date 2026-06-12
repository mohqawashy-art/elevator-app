#!/usr/bin/env bash
# إصلاح سريع — خدمة liftcore-jama بعد فشل gunicorn
#   bash deploy/fix_jama.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
PORT="${PORT:-5002}"
DOMAIN="${DOMAIN:-jama.liftcoreapp.com}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q --upgrade pip gunicorn flask flask-sqlalchemy werkzeug cryptography

GUNICORN_BIN="$VENV/bin/gunicorn"
if [ ! -x "$GUNICORN_BIN" ]; then
  echo "ERROR: still missing $GUNICORN_BIN"
  exit 1
fi
echo "gunicorn: $GUNICORN_BIN"

UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
if [ -f "$UNIT" ]; then
  sudo sed -i "s|^ExecStart=.*|ExecStart=${GUNICORN_BIN} -w 2 -b 127.0.0.1:${PORT} --timeout 120 app:app|" "$UNIT"
else
  echo "ERROR: $UNIT missing — run: bash deploy/provision_jama.sh"
  exit 1
fi

sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE_NAME"
sleep 3
sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
curl -sS "http://127.0.0.1:${PORT}/api/version" | head -c 400 || true
echo ""
MAIN_DIR="${MAIN_DIR:-$HOME/liftcore/elevator-app}"
if [ -f "$MAIN_DIR/deploy/fix_jama_nginx.sh" ]; then
  echo ""
  echo "==> إصلاح Nginx (إزالة Coming Soon)"
  bash "$MAIN_DIR/deploy/fix_jama_nginx.sh"
else
  echo "افتح: https://${DOMAIN}/login"
fi
