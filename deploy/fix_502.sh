#!/usr/bin/env bash
# استعادة LiftCore بعد 502 Bad Gateway
#   cd ~/liftcore/elevator-app && bash deploy/fix_502.sh

set -euo pipefail

for try in "$HOME/liftcore/elevator-app" "/var/www/elevator-app"; do
  if [ -d "$try/.git" ]; then APP_DIR="$try"; break; fi
done
APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
SERVICE_NAME="${SERVICE_NAME:-liftcore}"
VENV="${VENV:-$APP_DIR/.venv}"

cd "$APP_DIR"
echo "==> LiftCore fix 502 — $APP_DIR"

echo ""
echo "==> آخر أخطاء الخدمة:"
sudo journalctl -u "$SERVICE_NAME" -n 40 --no-pager 2>/dev/null || echo "(لا journalctl)"

if [ -d "$VENV" ]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  echo ""
  echo "==> اختبار تحميل التطبيق:"
  if python -c "from app import app; print('IMPORT OK')" 2>&1; then
    echo "  الكود سليم — إعادة تشغيل الخدمة فقط"
  else
    echo ""
    echo "==> فشل الاستيراد — محاولة pip install"
    pip install -q -r requirements.txt 2>/dev/null || pip install -q flask flask-sqlalchemy gunicorn werkzeug cryptography
    python -c "from app import app; print('IMPORT OK after pip')" || {
      echo ""
      echo "ERROR: ما زال فشل الاستيراد. أرسل مخرجات الأمر أعلاه للدعم."
      exit 1
    }
  fi
fi

DROP_IN="/etc/systemd/system/${SERVICE_NAME}.service.d"
sudo mkdir -p "$DROP_IN"
printf '%s\n' '[Service]' 'Environment=LIFTCORE_HTTPS=1' | sudo tee "$DROP_IN/https.conf" >/dev/null
printf '%s\n' '[Service]' 'Environment=LIFTCORE_INSTALL_MODULE=1' | sudo tee "$DROP_IN/install-module.conf" >/dev/null
sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE_NAME"
sleep 3

if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
  echo ""
  echo "OK — الخدمة تعمل"
  for PORT in 5000 5001 8000; do
    OUT="$(curl -sS --max-time 3 "http://127.0.0.1:${PORT}/api/version" 2>/dev/null || true)"
    if [ -n "$OUT" ]; then
      echo "  api/version on :${PORT} => $OUT" | head -c 500
      break
    fi
  done
  echo ""
  echo "افتح: https://app.liftcoreapp.com/dashboard"
else
  echo "ERROR: الخدمة ما زالت متوقفة"
  sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
  exit 1
fi
