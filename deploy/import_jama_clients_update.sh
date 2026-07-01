#!/usr/bin/env bash
# تحديث بيانات عملاء جما من Excel (العملاء 1_7_2026)
# Usage (GCP SSH):
#   cd ~/liftcore/jama-elevator-app && git pull origin main
#   bash deploy/import_jama_clients_update.sh --dry-run
#   bash deploy/import_jama_clients_update.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
XLSX="${XLSX:-$JAMA_DIR/deploy/data/jama_import/العملاء 1_7_2026.xlsx}"
DRY="${DRY:-0}"
NO_GEO="${NO_GEO:-0}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --no-geocode) NO_GEO=1 ;;
  esac
done

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: Jama app dir not found: $JAMA_DIR"
  exit 1
fi

cd "$JAMA_DIR"

if [ ! -f "$XLSX" ]; then
  echo "ERROR: Excel file not found: $XLSX"
  echo "Run: git pull origin main"
  exit 1
fi

if [ ! -f "$DB_FILE" ]; then
  echo "ERROR: Database not found: $DB_FILE"
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q openpyxl

export DATABASE_URL="sqlite:///${DB_FILE}"

ARGS=("$XLSX")
if [ "$DRY" = "1" ]; then
  ARGS+=(--dry-run)
fi
if [ "$NO_GEO" = "1" ]; then
  ARGS+=(--no-geocode)
fi

echo "==> Update Jama customers from Excel"
echo "    DB:   $DB_FILE"
echo "    File: $XLSX"
python scripts/import_jama_clients_xlsx.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart liftcore-jama 2>/dev/null || true
  echo "==> Done — https://jama.liftcoreapp.com/clients"
fi
