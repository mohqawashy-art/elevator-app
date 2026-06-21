#!/usr/bin/env bash
# استيراد كل بيانات جما من ملفات Excel (بالترتيب الصحيح)
# Usage (GCP SSH):
#   cd ~/liftcore/jama-elevator-app && git pull origin main
#   bash deploy/import_jama_all.sh --dry-run    # معاينة فقط
#   bash deploy/import_jama_all.sh              # تنفيذ كامل
#   bash deploy/import_jama_all.sh --no-geocode # بدون تحديد إحداثيات الخريطة

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
DRY=0
NO_GEO=0
SKIP_GEO=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --no-geocode) NO_GEO=1 ;;
    --skip-geocode) SKIP_GEO=1 ;;
  esac
done

DEPLOY="$JAMA_DIR/deploy"
ARGS=()
if [ "$DRY" = "1" ]; then
  ARGS+=(--dry-run)
fi

echo "=============================================="
echo "  LiftCore — استيراد بيانات جما"
echo "  المجلد: $JAMA_DIR"
echo "  وضع المعاينة: $([ "$DRY" = "1" ] && echo نعم || echo لا)"
echo "=============================================="

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: Jama app dir not found: $JAMA_DIR"
  exit 1
fi

run_step() {
  local label="$1"
  local script="$2"
  shift 2
  echo ""
  echo "==> [$label]"
  if [ ! -f "$script" ]; then
    echo "ERROR: missing $script"
    exit 1
  fi
  bash "$script" "$@" "${ARGS[@]}"
}

# 1) عناوين العملاء + إحداثيات (إن وُجدت في Excel)
GEO_ARGS=()
if [ "$NO_GEO" = "1" ]; then
  GEO_ARGS+=(--no-geocode)
fi
run_step "عملاء / عناوين" "$DEPLOY/import_jama_client_addresses.sh" "${GEO_ARGS[@]}"

# 2) مصاعد (يعتمد على العملاء)
run_step "مصاعد" "$DEPLOY/import_jama_elevators.sh"

# 3) زيارات الصيانة
run_step "زيارات الصيانة" "$DEPLOY/import_jama_maintenance_visits.sh"

# 4) أعطال (من نفس ملف الزيارات — صفوف «عطل»)
run_step "أعطال" "$DEPLOY/import_jama_faults.sh"

# 5) بيان تركيب قطع الغيار
run_step "قطع الغيار / الفوترة" "$DEPLOY/import_jama_parts_billing.sh"

# 6) تحديد مواقع العملاء المتبقين على الخريطة
if [ "$SKIP_GEO" != "1" ] && [ "$NO_GEO" != "1" ]; then
  run_step "إحداثيات الخريطة (geocode)" "$DEPLOY/geocode_jama_clients.sh"
fi

echo ""
echo "=============================================="
if [ "$DRY" = "1" ]; then
  echo "  معاينة اكتملت — لا تغييرات على القاعدة"
  echo "  للتنفيذ: bash deploy/import_jama_all.sh"
else
  echo "  اكتمل استيراد بيانات جما"
  echo "  https://jama.liftcoreapp.com"
fi
echo "=============================================="
