#!/usr/bin/env bash
# تحديث الإيرادات والمصروفات لجما من Excel 1_7_2026 — خطوتان منفصلتان
# Usage (GCP SSH):
#   cd ~/liftcore/jama-elevator-app && git pull origin main
#   bash deploy/import_jama_revenues_expenses_update.sh --dry-run
#   bash deploy/import_jama_revenues_expenses_update.sh
#
# إيرادات فقط:
#   bash deploy/import_jama_revenues_expenses_update.sh --revenues-only
# مصروفات فقط:
#   bash deploy/import_jama_revenues_expenses_update.sh --expenses-only
#
# تحديث صفوف موجودة (بدل تخطيها):
#   bash deploy/import_jama_revenues_expenses_update.sh --sync

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
REV_XLSX="${REV_XLSX:-$JAMA_DIR/deploy/data/jama_import/إيرادات 1_7_2026.xlsx}"
EXP_XLSX="${EXP_XLSX:-$JAMA_DIR/deploy/data/jama_import/المصروفات 1_7_2026.xlsx}"
SERVICE="${SERVICE:-liftcore-jama}"
DRY=0
RUN_REV=1
RUN_EXP=1
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --revenues-only) RUN_EXP=0 ;;
    --expenses-only) RUN_REV=0 ;;
    --sync) EXTRA+=(--sync) ;;
    --force) EXTRA+=(--force) ;;
    --import-all) EXTRA+=(--import-all) ;;
  esac
done

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: Jama app dir not found: $JAMA_DIR"
  exit 1
fi

cd "$JAMA_DIR"

if [ "$RUN_REV" = "1" ] && [ ! -f "$REV_XLSX" ]; then
  echo "ERROR: Revenues file not found: $REV_XLSX"
  exit 1
fi

if [ "$RUN_EXP" = "1" ] && [ ! -f "$EXP_XLSX" ]; then
  echo "ERROR: Expenses file not found: $EXP_XLSX"
  exit 1
fi

if [ ! -f "$DB_FILE" ]; then
  echo "ERROR: Database not found: $DB_FILE"
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q openpyxl pandas

export DATABASE_URL="sqlite:///${DB_FILE}"

if [ "$DRY" = "1" ]; then
  EXTRA+=(--dry-run)
fi

echo "==> Jama revenues & expenses import"
echo "    DB: $DB_FILE"
echo ""

if [ "$RUN_REV" = "1" ]; then
  echo "=============================================="
  echo "  1) الإيرادات"
  echo "=============================================="
  echo "    File: $REV_XLSX"
  python scripts/import_jama_revenues.py "$REV_XLSX" "${EXTRA[@]}"
  echo ""
fi

if [ "$RUN_EXP" = "1" ]; then
  echo "=============================================="
  echo "  2) المصروفات"
  echo "=============================================="
  echo "    File: $EXP_XLSX"
  python scripts/import_jama_expenses.py "$EXP_XLSX" "${EXTRA[@]}"
  echo ""
fi

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE" 2>/dev/null || true
  echo "==> Done"
  [ "$RUN_REV" = "1" ] && echo "    Revenues:  https://jama.liftcoreapp.com/revenues"
  [ "$RUN_EXP" = "1" ] && echo "    Expenses:  https://jama.liftcoreapp.com/expenses"
fi
