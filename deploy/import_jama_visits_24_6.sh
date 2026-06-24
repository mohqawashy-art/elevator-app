#!/usr/bin/env bash
# Import visits log split: routine maintenance + faults/follow-ups
#
#   bash deploy/import_jama_visits_24_6.sh --dry-run
#   bash deploy/import_jama_visits_24_6.sh
#
# File (in git): deploy/data/jama_import/visits_24_6_2026.xlsx
#   صيانة دورية  → maintenance-visits
#   عطل + زيارة متابعة → faults

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
  python - visits <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from import_real_data import find_excel_files
folder = os.environ.get("DATA_DIR", ".")
found = find_excel_files(folder, prefer_date="24_6_2026")
path = found.get("visits", "")
if path and os.path.isfile(path):
    print(path)
PY
}

VISITS_XLSX="${VISITS_XLSX:-$(pick_file \
  "$DATA_DIR/visits_24_6_2026.xlsx" \
  "$DATA_DIR/سجل الزيارات 24_6_2026.xlsx")}"

if [ -z "$VISITS_XLSX" ] || [ ! -f "$VISITS_XLSX" ]; then
  echo "ERROR: visits file not found under $DATA_DIR"
  echo "Run: git pull origin main"
  exit 1
fi

export DATABASE_URL="sqlite:///${DB_FILE}"
export XLSX="$VISITS_XLSX"

echo "=============================================="
echo "  Jama visits import (split)"
echo "  DB:   $DB_FILE"
echo "  file: $VISITS_XLSX"
echo "=============================================="

echo ""
echo "==> [1/2] صيانة دورية → زيارات الصيانة"
python scripts/import_maintenance_visits_xlsx.py "$VISITS_XLSX" "${EXTRA[@]}"

echo ""
echo "==> [2/2] عطل + متابعة → الأعطال"
python scripts/import_faults_from_visits_xlsx.py "$VISITS_XLSX" "${EXTRA[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  sleep 2
  echo ""
  echo "Done —"
  echo "  https://jama.liftcoreapp.com/maintenance-visits"
  echo "  https://jama.liftcoreapp.com/faults"
fi
