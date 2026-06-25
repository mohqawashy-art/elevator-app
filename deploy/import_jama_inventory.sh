#!/usr/bin/env bash
# استيراد جدول الأصناف إلى مخزون جما
#
#   bash deploy/import_jama_inventory.sh --dry-run
#   bash deploy/import_jama_inventory.sh
#   bash deploy/import_jama_inventory.sh --replace

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
DATA_DIR="${DATA_DIR:-$JAMA_DIR/deploy/data/jama_import}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
DRY=0
REPLACE=0
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --replace) REPLACE=1 ;;
  esac
done

if [ "$REPLACE" = "1" ]; then EXTRA+=(--replace); fi

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: Jama app dir not found: $JAMA_DIR"
  exit 1
fi

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q openpyxl pandas

pick_file() {
  local candidate
  for candidate in "$@"; do
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

XLSX="${XLSX:-$(pick_file \
  "$DATA_DIR/inventory_items_25_6_2026.xlsx" \
  "$DATA_DIR/جدول الاصناف 25_6_2026.xlsx" \
  "$DATA_DIR/inventory_25_6_2026.xlsx" || true)}"

if [ -z "$XLSX" ] || [ ! -f "$XLSX" ]; then
  echo "ERROR: inventory Excel not found in $DATA_DIR"
  echo "Expected: inventory_items_25_6_2026.xlsx"
  exit 1
fi

if [ ! -f "$DB_FILE" ]; then
  echo "ERROR: Database not found: $DB_FILE"
  exit 1
fi

export DATABASE_URL="sqlite:///${DB_FILE}"

echo "=============================================="
echo "  Jama import: inventory items"
echo "  DB:   $DB_FILE"
echo "  File: $XLSX"
echo "  Replace existing: $([ "$REPLACE" = "1" ] && echo yes || echo no)"
echo "=============================================="

if [ "$DRY" = "1" ]; then
  python - "$XLSX" <<'PY'
import sys
from import_inventory_csv import import_inventory_file
path = sys.argv[1]
stats = import_inventory_file(path, replace=False)
print("DRY preview — rolling back would happen in real import")
print(stats)
PY
  exit 0
fi

python import_inventory_csv.py "$XLSX" "${EXTRA[@]}"

sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
sleep 2
echo ""
echo "Done — https://jama.liftcoreapp.com/inventory"
