#!/usr/bin/env bash
# LiftCore — مزامنة إجبارية مع GitHub (الكود فقط — قاعدة البيانات لا تُمس)
# استخدمه عندما git pull يفشل بسبب ملفات غير متتبعة.
#   cd ~/liftcore/elevator-app && bash deploy/force_sync.sh

set -euo pipefail

for try in "$HOME/liftcore/elevator-app" "/var/www/elevator-app"; do
  if [ -d "$try/.git" ]; then APP_DIR="$try"; break; fi
done
APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
SERVICE_NAME="${SERVICE_NAME:-liftcore}"

echo "=============================================="
echo "  LiftCore FORCE SYNC — $(date)"
echo "  المجلد: $APP_DIR"
echo "=============================================="

cd "$APP_DIR"

echo ""
echo "==> خدمة systemd (تأكد أننا نحدّث المجلد الصحيح)"
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl cat "$SERVICE_NAME" 2>/dev/null | grep -E 'WorkingDirectory|ExecStart' || true
fi

echo ""
echo "==> نسخة احتياطية لقاعدة البيانات"
TS="$(date +%Y%m%d%H%M%S)"
for db in "$APP_DIR/instance/liftcore.db" "$APP_DIR/liftcore.db"; do
  if [ -f "$db" ]; then
    cp "$db" "${db}.bak.${TS}"
    echo "  OK ${db}.bak.${TS}"
    break
  fi
done

echo ""
echo "==> الحالة قبل التحديث"
git log -1 --oneline || true
echo "ملفات غير متتبعة:"
git status -u --porcelain | grep '^\?\?' || echo "  (لا يوجد)"

echo ""
echo "==> جلب GitHub"
git fetch origin main

echo ""
echo "==> إزالة الملفات غير المتتبعة (تمنع pull)"
BACKUP="$APP_DIR/.force-sync-backup.${TS}"
mkdir -p "$BACKUP"
while IFS= read -r f; do
  [ -z "$f" ] && continue
  mkdir -p "$BACKUP/$(dirname "$f")"
  cp -a "$f" "$BACKUP/$f" 2>/dev/null || true
  rm -rf "$f"
  echo "  removed: $f"
done < <(git status -u --porcelain | awk '/^\?\?/{print $2}')

echo ""
echo "==> مزامنة الكود مع origin/main (لا يمس liftcore.db)"
git reset --hard origin/main

echo ""
echo "==> بعد التحديث"
git log -1 --oneline
SETTINGS_LINES="$(wc -l < templates/settings.html)"
echo "  settings.html: ${SETTINGS_LINES} سطر (المطلوب ~460)"
grep -q 'المظهر' templates/settings.html && echo "  تبويب المظهر: OK" || echo "  تبويب المظهر: MISSING"
test -f templates/partials/app_header.html && echo "  app_header: OK" || echo "  app_header: MISSING"
grep -q 'enforce_auth' app.py && echo "  enforce_auth: OK" || echo "  enforce_auth: MISSING"
grep -q 'purchase-orders' app.py && echo "  purchase-orders: OK" || echo "  purchase-orders: MISSING"

if [ "$SETTINGS_LINES" -lt 400 ]; then
  echo ""
  echo "ERROR: settings.html ما زال قديم. تحقق من الريبو على GitHub."
  exit 1
fi

VENV="${VENV:-$APP_DIR/.venv}"
if [ -d "$VENV" ]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  pip install -q -r requirements.txt 2>/dev/null || pip install -q flask flask-sqlalchemy gunicorn werkzeug
fi

echo ""
echo "==> إعادة تشغيل $SERVICE_NAME"
if command -v systemctl >/dev/null 2>&1; then
  DROP_IN="/etc/systemd/system/${SERVICE_NAME}.service.d"
  sudo mkdir -p "$DROP_IN"
  printf '%s\n' '[Service]' 'Environment=LIFTCORE_HTTPS=1' | sudo tee "$DROP_IN/https.conf" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl restart "$SERVICE_NAME"
  sleep 3
  sudo systemctl is-active "$SERVICE_NAME"
fi

echo ""
echo "==> عملية التشغيل"
ps aux | grep -E '[g]unicorn.*app:app' || ps aux | grep -E '[p]ython.*app\.py' || true

echo ""
echo "=============================================="
echo "  تم. افتح:"
echo "  https://app.liftcoreapp.com/api/version"
echo "  https://app.liftcoreapp.com/settings"
echo "  (Ctrl+Shift+R لتحديث قوي في المتصفح)"
echo "=============================================="
