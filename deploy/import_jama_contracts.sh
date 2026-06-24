#!/usr/bin/env bash
# Import Jama contracts from Excel (requires clients already imported)
#
#   bash deploy/import_jama_contracts.sh --dry-run
#   bash deploy/import_jama_contracts.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
DATA_DIR="${DATA_DIR:-$JAMA_DIR/deploy/data/jama_import}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
DRY=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
  esac
done

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
  python - contracts <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from import_real_data import find_excel_files
folder = os.environ.get("DATA_DIR", ".")
found = find_excel_files(folder, prefer_date="24_6_2026")
path = found.get("contracts", "")
if path and os.path.isfile(path):
    print(path)
PY
}

CONTRACTS_XLSX="${CONTRACTS_XLSX:-$(pick_file \
  "$DATA_DIR/contracts_24_6_2026.xlsx" \
  "$DATA_DIR/العقود 24_6_2026.xlsx")}"

if [ -z "$CONTRACTS_XLSX" ] || [ ! -f "$CONTRACTS_XLSX" ]; then
  echo "ERROR: contracts file not found under $DATA_DIR"
  echo "Run: git pull origin main"
  exit 1
fi

export DATABASE_URL="sqlite:///${DB_FILE}"

ARGS=("$CONTRACTS_XLSX")
if [ "$DRY" = "1" ]; then ARGS+=(--dry-run); fi

echo "=============================================="
echo "  Jama import: contracts"
echo "  DB: $DB_FILE"
echo "  file: $CONTRACTS_XLSX"
echo "=============================================="

python scripts/import_jama_contracts.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  sleep 2
  echo ""
  echo "Done — https://jama.liftcoreapp.com/contracts"
fi
