#!/usr/bin/env bash
# حذف حساب جما بالكامل من المنصة لإعادة دعوته كعميل جديد
#
# Usage (GCP SSH):
#   cd ~/liftcore/elevator-app && git pull --ff-only origin main
#   bash deploy/delete_jama_org.sh
#
# بعد الحذف أنشئ دعوة من:
#   https://admin.liftcoreapp.com/operator/onboarding

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"

cd "$APP_DIR"

if [ -f "$PLATFORM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$PLATFORM_ENV"
  set +a
fi

if [ -d "$APP_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$APP_DIR/.venv/bin/activate"
fi

echo "==> حذف حساب جما بالكامل (بيانات + مؤسسة)"
python scripts/wipe_tenant_data.py --slug jama --delete-org --confirm JAMA_DELETE_ORG

echo ""
echo "=============================================="
echo "  تم حذف jama من المنصة"
echo "  أنشئ دعوة جديدة:"
echo "  https://admin.liftcoreapp.com/operator/onboarding"
echo "  الاسم: شركة تقنية جما التميز للمصاعد"
echo "  المعرّف: jama"
echo "  بعد التفعيل: https://jama.liftcoreapp.com/login"
echo "=============================================="
