#!/usr/bin/env bash
# استيراد العملاء + الفنيين + المصاعد لجما (بالترتيب + خريطة)
#
# ارفع الملفات إلى:
#   ~/liftcore/jama-elevator-app/deploy/data/jama_import/
#
#   العملاء 24_6_2026.xlsx
#   الفنيين 24_6_2026.xlsx
#   المصاعد 24_6_2026.xlsx
#
# الاستخدام:
#   bash deploy/import_jama_core_three.sh --dry-run
#   bash deploy/import_jama_core_three.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
DATA_DIR="${DATA_DIR:-$JAMA_DIR/deploy/data/jama_import}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
DRY=0
SKIP_GEO=0

CLIENTS_XLSX="${CLIENTS_XLSX:-$DATA_DIR/العملاء 24_6_2026.xlsx}"
TECHS_XLSX="${TECHS_XLSX:-$DATA_DIR/الفنيين 24_6_2026.xlsx}"
ELEVATORS_XLSX="${ELEVATORS_XLSX:-$DATA_DIR/المصاعد 24_6_2026.xlsx}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --skip-geocode) SKIP_GEO=1 ;;
  esac
done

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: مجلد جما غير موجود: $JAMA_DIR"
  exit 1
fi

for f in "$CLIENTS_XLSX" "$TECHS_XLSX" "$ELEVATORS_XLSX"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: ملف غير موجود: $f"
    echo "ارفع الملفات الثلاثة إلى: $DATA_DIR"
    exit 1
  fi
done

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q openpyxl pandas

export DATABASE_URL="sqlite:///${DB_FILE}"

ARGS=(
  --clients "$CLIENTS_XLSX"
  --technicians "$TECHS_XLSX"
  --elevators "$ELEVATORS_XLSX"
)
if [ "$DRY" = "1" ]; then ARGS+=(--dry-run); fi
if [ "$SKIP_GEO" = "1" ]; then ARGS+=(--skip-geocode); fi

echo "=============================================="
echo "  جما — استيراد عملاء + فنيين + مصاعد"
echo "  DB: $DB_FILE"
echo "=============================================="

python scripts/import_jama_core_three.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  sleep 2
  echo ""
  echo "تم — https://jama.liftcoreapp.com/clients"
fi
