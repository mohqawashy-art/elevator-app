#!/usr/bin/env bash
# Import parts billing — treat imported rows as غير محصل
#
#   bash deploy/import_jama_parts_billing.sh --dry-run
#   bash deploy/import_jama_parts_billing.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
DATA_DIR="${DATA_DIR:-$JAMA_DIR/deploy/data/jama_import}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
DRY=0
REPLACE=1
UNCOLLECTED=0
FORCE_UNCOLLECTED=1
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --force) EXTRA+=(--force) ;;
    --keep-existing) REPLACE=0 ;;
    --uncollected-only) UNCOLLECTED=1 ;;
    --keep-status) FORCE_UNCOLLECTED=0 ;;
  esac
done

if [ "$REPLACE" = "1" ]; then EXTRA+=(--replace); fi
if [ "$UNCOLLECTED" = "1" ]; then EXTRA+=(--uncollected-only); fi
if [ "$FORCE_UNCOLLECTED" = "1" ]; then EXTRA+=(--force-uncollected); fi
if [ "$DRY" = "1" ]; then EXTRA+=(--dry-run); fi

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: Jama app dir not found: $JAMA_DIR"
  exit 1
fi

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q openpyxl

pick_file() {
  local candidate
  for candidate in "$@"; do
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  export DATA_DIR
  python - spare_parts <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from import_real_data import find_excel_files
folder = os.environ.get("DATA_DIR", ".")
found = find_excel_files(folder, prefer_date="25_6_2026")
path = found.get("spare_parts", "")
if path and os.path.isfile(path):
    print(path)
PY
}

XLSX="${XLSX:-$(pick_file \
  "$DATA_DIR/parts_billing_25_6_2026.xlsx" \
  "$DATA_DIR/بيان تركيب قطع الغيار 25_6_2026.xlsx")}"

if [ -z "$XLSX" ] || [ ! -f "$XLSX" ]; then
  echo "ERROR: parts billing Excel not found"
  echo "Run: git pull origin main"
  exit 1
fi

if [ ! -f "$DB_FILE" ]; then
  echo "ERROR: Database not found: $DB_FILE"
  exit 1
fi

export DATABASE_URL="sqlite:///${DB_FILE}"

echo "=============================================="
echo "  Jama import: parts billing (كلها غير محصل)"
echo "  DB:   $DB_FILE"
echo "  File: $XLSX"
echo "=============================================="

python scripts/import_parts_billing_xlsx.py "$XLSX" "${EXTRA[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  sleep 2
  echo ""
  echo "Done — https://jama.liftcoreapp.com/parts-billing"
fi
