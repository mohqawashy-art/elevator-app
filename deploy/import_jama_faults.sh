#!/usr/bin/env bash
# استيراد الأعطال لجما من Excel (صفوف نوع الزيارة «عطل» فقط)
# Usage (GCP SSH):
#   cd ~/liftcore/jama-elevator-app && git pull origin main
#   bash deploy/import_jama_faults.sh --dry-run
#   bash deploy/import_jama_faults.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
XLSX="${XLSX:-$JAMA_DIR/deploy/data/jama_visits_14_6_2026.xlsx}"
DRY="${DRY:-0}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
  esac
done

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: Jama app dir not found: $JAMA_DIR"
  exit 1
fi

cd "$JAMA_DIR"

if [ ! -f "$XLSX" ]; then
  echo "ERROR: Excel file not found: $XLSX"
  echo "Upload your file to: deploy/data/jama_visits_14_6_2026.xlsx"
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

echo "==> Import faults (عطل rows only) into Jama"
echo "    DB:   $DB_FILE"
echo "    File: $XLSX"
python scripts/import_faults_from_visits_xlsx.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart liftcore-jama 2>/dev/null || true
  echo "==> Done. Refresh https://jama.liftcoreapp.com/faults"
fi
