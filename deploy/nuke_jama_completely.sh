#!/usr/bin/env bash
# حذف جما بالكامل من كل المسارات المحتملة (PostgreSQL tenant + SQLite القديم)
# ثم التحقق أن الموقع فارغ / 404 حتى دعوة جديدة.
#
# Usage (GCP Console → SSH فقط — لا يعمل من Windows):
#   cd ~/liftcore/elevator-app
#   git pull --ff-only origin main
#   bash deploy/nuke_jama_completely.sh
#
# يتطلب تأكيد يدوي: اكتب JAMA_NUKE عندما يُطلب منك.

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"

cd "$APP_DIR"

echo "======================================================"
echo "  تحذير: حذف حساب جما بالكامل (بيانات + مؤسسة)"
echo "  PostgreSQL tenant jama  +  SQLite jama.db إن وُجد"
echo "======================================================"
echo ""
read -r -p "اكتب JAMA_NUKE للتأكيد: " CONFIRM
if [ "$CONFIRM" != "JAMA_NUKE" ]; then
  echo "أُلغي — لم يُحذف شيء."
  exit 1
fi

echo ""
echo "==> 0) تشخيص سريع"
echo -n "  liftcore: "; systemctl is-active liftcore 2>/dev/null || echo inactive
echo -n "  liftcore-jama: "; systemctl is-active liftcore-jama 2>/dev/null || echo inactive
echo "  nginx jama/500x:"
sudo grep -RIn "jama\|5001\|5002" /etc/nginx/sites-enabled/ 2>/dev/null | head -20 || true

if [ -f "$PLATFORM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$PLATFORM_ENV"
  set +a
  echo "==> محمّل: $PLATFORM_ENV"
fi
if [ -d "$APP_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$APP_DIR/.venv/bin/activate"
fi

echo ""
echo "==> 1) حذف tenant jama من PostgreSQL (إن وُجد)"
python scripts/wipe_tenant_data.py --slug jama --delete-org --confirm JAMA_DELETE_ORG || true

echo ""
echo "==> 2) إيقاف النسخة القديمة liftcore-jama"
sudo systemctl disable --now liftcore-jama 2>/dev/null || true

if [ -d "$JAMA_DIR" ]; then
  echo "==> 3) تفريغ/نسخ احتياطي لـ jama.db القديمة"
  mkdir -p "$JAMA_DIR/instance"
  if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "${DB_FILE}.bak.nuke.$(date +%Y%m%d%H%M%S)"
    rm -f "$DB_FILE"
    echo "  حُذف: $DB_FILE (مع نسخة bak)"
  else
    echo "  لا يوجد $DB_FILE"
  fi
  # لا نعيد إنشاء قاعدة قديمة — نمنع عودة البيانات بالخطأ
else
  echo "==> 3) مجلد jama-elevator-app غير موجود — تخطي"
fi

echo ""
echo "==> 4) توجيه nginx لـ jama إلى المنصة الرئيسية :5001 (إن لزم)"
NGINX_JAMA=""
for f in /etc/nginx/sites-enabled/*jama* /etc/nginx/sites-available/*jama*; do
  [ -f "$f" ] || continue
  NGINX_JAMA="$f"
  break
done
if [ -n "$NGINX_JAMA" ] && sudo grep -q "5002" "$NGINX_JAMA" 2>/dev/null; then
  echo "  تعديل proxy_pass في $NGINX_JAMA من 5002 → 5001"
  sudo cp "$NGINX_JAMA" "${NGINX_JAMA}.bak.$(date +%Y%m%d%H%M%S)"
  sudo sed -i 's/127\.0\.0\.1:5002/127.0.0.1:5001/g' "$NGINX_JAMA"
  sudo nginx -t && sudo systemctl reload nginx
else
  echo "  لا حاجة لتعديل nginx (أو الملف غير موجود / ليس على 5002)"
fi

echo ""
echo "==> 5) تحقق بعد الحذف"
python - <<'PY'
import os
from app import app
from models import Organization, Customer

with app.app_context():
    org = Organization.query.filter_by(slug='jama').first()
    print('  org jama:', org.id if org else 'DELETED (جيد)')
    if org:
        n = Customer.query.execution_options(skip_tenant=True).filter_by(organization_id=org.id).count()
        print('  customers still:', n, '← إن >0 فالحذف لم يكتمل')
PY

echo ""
echo "  HTTP عبر Host jama → المنصة:"
curl -sS -o /dev/null -w "  localhost:5001 Host=jama → %{http_code}\n" \
  -H "Host: jama.liftcoreapp.com" "http://127.0.0.1:5001/login" || true
curl -sS -o /dev/null -w "  https://jama.liftcoreapp.com/login → %{http_code}\n" \
  "https://jama.liftcoreapp.com/login" || true

echo ""
echo "=============================================="
echo "  المتوقع بعد الحذف الكامل:"
echo "  - org jama: DELETED"
echo "  - الموقع قد يعطي 404 أو صفحة دخول فارغة بدون بيانات"
echo ""
echo "  الخطوة التالية — دعوة كعميل جديد:"
echo "  https://admin.liftcoreapp.com/operator/onboarding"
echo "  المعرّف: jama"
echo "=============================================="
