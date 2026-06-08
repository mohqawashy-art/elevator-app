#!/usr/bin/env bash
# LiftCore — استعادة التحديثات على السيرفر (شغّل من GCP Console SSH)
#   cd ~/liftcore/elevator-app && bash deploy/recover_server.sh

set -euo pipefail

if [ -d "$HOME/liftcore/elevator-app/.git" ]; then
  APP_DIR="$HOME/liftcore/elevator-app"
elif [ -d "/var/www/elevator-app/.git" ]; then
  APP_DIR="/var/www/elevator-app"
else
  echo "ERROR: لم يُعثر على مجلد المشروع. جرّب: cd ~/liftcore/elevator-app"
  exit 1
fi

SERVICE_NAME="${SERVICE_NAME:-liftcore}"
VENV="${VENV:-$APP_DIR/.venv}"

echo "=============================================="
echo "  LiftCore — استعادة التحديثات"
echo "  $(date)"
echo "=============================================="
echo ""
echo "المجلد: $APP_DIR"
cd "$APP_DIR"

echo ""
echo "==> 1) الحالة الحالية"
git log -1 --oneline 2>/dev/null || echo "  (لا يوجد git)"
if [ -f instance/liftcore.db ]; then
  echo "  قاعدة البيانات: instance/liftcore.db ($(du -h instance/liftcore.db | cut -f1))"
elif [ -f liftcore.db ]; then
  echo "  قاعدة البيانات: liftcore.db ($(du -h liftcore.db | cut -f1))"
fi

echo ""
echo "==> 2) نسخة احتياطية لقاعدة البيانات"
TS="$(date +%Y%m%d%H%M%S)"
for db in "$APP_DIR/instance/liftcore.db" "$APP_DIR/liftcore.db"; do
  if [ -f "$db" ]; then
    cp "$db" "${db}.bak.${TS}"
    echo "  تم: ${db}.bak.${TS}"
    break
  fi
done
echo "  نسخ سابقة:"
ls -1t "$APP_DIR"/instance/liftcore.db.bak.* "$APP_DIR"/liftcore.db.bak.* 2>/dev/null | head -5 || echo "  (لا توجد)"

echo ""
echo "==> 3) جلب آخر كود من GitHub (بدون reset --hard)"
git fetch origin main
BEFORE="$(git rev-parse --short HEAD 2>/dev/null || echo none)"

# ملفات نُسخت يدوياً على السيرفر وتمنع git pull
CONFLICT_BACKUP="$APP_DIR/.merge-backup.${TS}"
mkdir -p "$CONFLICT_BACKUP"
for f in \
  templates/partials/app_header.html \
  templates/partials/liftcore_head.html \
  zatca_qr.py \
  static/liftcore-shell.css \
  static/liftcore-shell.js; do
  if [ -f "$f" ] && ! git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    mkdir -p "$CONFLICT_BACKUP/$(dirname "$f")"
    cp -a "$f" "$CONFLICT_BACKUP/$f"
    rm -f "$f"
    echo "  moved untracked blocker: $f"
  fi
done

if ! git pull --ff-only origin main; then
  echo ""
  echo "ERROR: git pull فشل. الحالة:"
  git status -sb
  echo ""
  echo "إذا ظهرت ملفات أخرى تمنع الدمج، انسخها للنسخة الاحتياطية ثم أعد التشغيل:"
  echo "  cp -a <الملف> $CONFLICT_BACKUP/ && rm -f <الملف>"
  exit 1
fi

AFTER="$(git rev-parse --short HEAD)"
echo "  commit: $BEFORE -> $AFTER"
git log -1 --oneline

echo ""
echo "==> 4) التحقق من الملفات المهمة"
OK=1
for f in \
  templates/partials/app_header.html \
  templates/settings.html \
  static/liftcore-shell.css \
  templates/purchase-orders.html \
  deploy/gcp_update.sh; do
  if [ -f "$f" ]; then
    echo "  OK  $f"
  else
    echo "  MISSING  $f"
    OK=0
  fi
done
if ! grep -q 'settings_user_add' app.py; then
  echo "  MISSING  settings routes in app.py"
  OK=0
fi
if ! grep -q 'enforce_auth' app.py; then
  echo "  MISSING  login guard in app.py"
  OK=0
fi
if [ "$OK" -eq 0 ]; then
  echo ""
  echo "ERROR: الكود على السيرفر ناقص. تأكد أن الريبو:"
  echo "  https://github.com/mohqawashy-art/elevator-app"
  echo "وفرع main يحتوي commit 085a530 أو أحدث."
  exit 1
fi

if [ -d "$VENV" ]; then
  echo ""
  echo "==> 5) pip install"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  pip install -q -r requirements.txt 2>/dev/null || pip install -q flask flask-sqlalchemy gunicorn werkzeug
fi

echo ""
echo "==> 6) إعادة تشغيل الخدمة"
DROP_IN="/etc/systemd/system/${SERVICE_NAME}.service.d"
if command -v systemctl >/dev/null 2>&1; then
  sudo mkdir -p "$DROP_IN"
  printf '%s\n' '[Service]' 'Environment=LIFTCORE_HTTPS=1' | sudo tee "$DROP_IN/https.conf" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl restart "$SERVICE_NAME"
  sleep 3
  sudo systemctl is-active "$SERVICE_NAME"
fi

echo ""
echo "==> 7) فحص الإصدار المحلي"
if command -v curl >/dev/null 2>&1; then
  curl -sS "http://127.0.0.1:5001/api/version" 2>/dev/null || \
  curl -sS "http://127.0.0.1:5000/api/version" 2>/dev/null || \
  echo "  (شغّل يدوياً: curl https://app.liftcoreapp.com/api/version)"
else
  echo "  افتح: https://app.liftcoreapp.com/api/version"
fi

echo ""
echo "=============================================="
echo "  تم. تحقق من المتصفح:"
echo "  https://app.liftcoreapp.com/api/version"
echo "    يجب: version=085a530-full و settings_full=true"
echo "  https://app.liftcoreapp.com/settings"
echo "    يجب: 4 تبويبات (شركة / مستخدمين / حسابي / مظهر)"
echo ""
echo "  إذا الأصناف ناقصة (بعد تحديث الكود):"
echo "    source .venv/bin/activate"
echo "    python -c \"from app import app; from seed_inventory_parts import ensure_inventory_catalog; app.app_context().push(); print('added', ensure_inventory_catalog())\""
echo "=============================================="
