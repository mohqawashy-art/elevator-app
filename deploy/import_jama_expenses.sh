#!/usr/bin/env bash
# Import Jama expenses from Excel
#
#   bash deploy/import_jama_expenses.sh --dry-run
#   bash deploy/import_jama_expenses.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
DATA_DIR="${DATA_DIR:-$JAMA_DIR/deploy/data/jama_import}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
DRY=0
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1; EXTRA+=(--dry-run) ;;
    --force) EXTRA+=(--force) ;;
    --sync) EXTRA+=(--sync) ;;
  esac
done

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
  export DATA_DIR
  python - expenses <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from import_real_data import find_excel_files
folder = os.environ.get("DATA_DIR", ".")
found = find_excel_files(folder, prefer_date="24_6_2026")
path = found.get("expenses", "")
if path and os.path.isfile(path):
    print(path)
PY
}

XLSX="${XLSX:-$(pick_file \
  "$DATA_DIR/expenses_27_6_2026.xlsx" \
  "$DATA_DIR/المصروفات 27_6_2026.xlsx" \
  "$DATA_DIR/expenses_24_6_2026.xlsx" \
  "$DATA_DIR/المصروفات 24_6_2026.xlsx")}"

if [ -z "$XLSX" ] || [ ! -f "$XLSX" ]; then
  echo "ERROR: expenses file not found"
  echo "Run: git pull origin main"
  exit 1
fi

export DATABASE_URL="sqlite:///${DB_FILE}"

echo "=============================================="
echo "  Jama import: expenses"
echo "  DB:   $DB_FILE"
echo "  File: $XLSX"
echo "=============================================="

python scripts/import_jama_expenses.py "$XLSX" "${EXTRA[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  sleep 2
  echo ""
  echo "Done — https://jama.liftcoreapp.com/expenses"
fi
