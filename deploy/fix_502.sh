#!/usr/bin/env bash
# استعادة LiftCore بعد 502 Bad Gateway
#   cd ~/liftcore/elevator-app && bash deploy/fix_502.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

for try in "$HOME/liftcore/elevator-app" "/var/www/elevator-app"; do
  if [ -d "$try/.git" ]; then APP_DIR="$try"; break; fi
done
APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
SERVICE_NAME="${SERVICE_NAME:-liftcore}"
VENV="$(lc_resolve_venv "$APP_DIR" "$SERVICE_NAME")"

cd "$APP_DIR"
echo "==> LiftCore fix 502 — $APP_DIR"

PLATFORM_ENV="/etc/liftcore/platform.env"
if [ -f "$APP_DIR/deploy/check_platform_env.sh" ]; then
  echo ""
  if ! bash "$APP_DIR/deploy/check_platform_env.sh"; then
    echo ""
    echo "أصلح $PLATFORM_ENV ثم أعد تشغيل هذا السكربت."
    exit 1
  fi
fi

echo ""
echo "==> آخر أخطاء الخدمة:"
sudo journalctl -u "$SERVICE_NAME" -n 40 --no-pager 2>/dev/null || echo "(لا journalctl)"

if [ -x "$VENV/bin/python" ]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  echo ""
  echo "==> اختبار تحميل التطبيق (venv: $VENV):"
  export LIFTCORE_HTTPS=1
  if [ -f "$PLATFORM_ENV" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$PLATFORM_ENV" 2>/dev/null || true
    set +a
  fi
  if python -c "from app import app; print('IMPORT OK')" 2>&1; then
    echo "  الكود سليم — إعادة تشغيل الخدمة فقط"
  else
    echo ""
    echo "==> فشل الاستيراد — pip install في $VENV"
    lc_pip_install_requirements "$VENV" "$APP_DIR"
    export LIFTCORE_HTTPS=1
    if [ -f "$PLATFORM_ENV" ]; then
      set -a
      # shellcheck disable=SC1090
      source "$PLATFORM_ENV" 2>/dev/null || true
      set +a
    fi
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
if [ -f "$PLATFORM_ENV" ]; then
  lc_fix_platform_env_perms "$PLATFORM_ENV"
  printf '%s\n' '[Service]' "EnvironmentFile=$PLATFORM_ENV" | sudo tee "$DROP_IN/platform-env.conf" >/dev/null
fi
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
