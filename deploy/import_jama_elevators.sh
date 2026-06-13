#!/usr/bin/env bash
# استيراد مصاعد جما من Excel إلى قاعدة jama.db
# Usage (GCP SSH):
#   cd ~/liftcore/jama-elevator-app && git pull origin main
#   bash deploy/import_jama_elevators.sh
#   bash deploy/import_jama_elevators.sh --dry-run

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
XLSX="${XLSX:-$JAMA_DIR/deploy/data/jama_elevators_13_6_2026.xlsx}"
DRY="${DRY:-0}"

if [ "${1:-}" = "--dry-run" ]; then
  DRY=1
fi

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: Jama app dir not found: $JAMA_DIR"
  exit 1
fi

cd "$JAMA_DIR"

if [ ! -f "$XLSX" ]; then
  echo "ERROR: Excel file not found: $XLSX"
  echo "Ensure deploy/data/jama_elevators_13_6_2026.xlsx exists (git pull)."
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

echo "==> Import elevators into Jama"
echo "    DB:   $DB_FILE"
echo "    File: $XLSX"
python scripts/import_elevators_xlsx.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart liftcore-jama 2>/dev/null || true
  echo "==> Done. Refresh https://jama.liftcoreapp.com/elevators"
fi
