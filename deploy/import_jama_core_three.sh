#!/usr/bin/env bash
# Import Jama clients + technicians + elevators (with map geocoding)
#
# Data files (in git):
#   deploy/data/jama_import/clients_24_6_2026.xlsx
#   deploy/data/jama_import/technicians_24_6_2026.xlsx
#   deploy/data/jama_import/elevators_24_6_2026.xlsx
#
# Usage:
#   bash deploy/import_jama_core_three.sh --dry-run
#   bash deploy/import_jama_core_three.sh
#   bash deploy/import_jama_core_three.sh --skip-geocode

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
DATA_DIR="${DATA_DIR:-$JAMA_DIR/deploy/data/jama_import}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
DRY=0
SKIP_GEO=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --skip-geocode) SKIP_GEO=1 ;;
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
  local key="$1"
  shift
  local candidate
  for candidate in "$@"; do
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  export DATA_DIR
  python - "$key" <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from import_real_data import find_excel_files
key = sys.argv[1]
folder = os.environ.get("DATA_DIR", ".")
found = find_excel_files(folder, prefer_date="24_6_2026")
path = found.get(key, "")
if path and os.path.isfile(path):
    print(path)
PY
}

CLIENTS_XLSX="${CLIENTS_XLSX:-$(pick_file customers \
  "$DATA_DIR/clients_24_6_2026.xlsx" \
  "$DATA_DIR/العملاء 24_6_2026.xlsx")}"
TECHS_XLSX="${TECHS_XLSX:-$(pick_file technicians \
  "$DATA_DIR/technicians_24_6_2026.xlsx" \
  "$DATA_DIR/الفنيين 24_6_2026.xlsx")}"
ELEVATORS_XLSX="${ELEVATORS_XLSX:-$(pick_file elevators \
  "$DATA_DIR/elevators_24_6_2026.xlsx" \
  "$DATA_DIR/المصاعد 24_6_2026.xlsx")}"

if [ -z "$CLIENTS_XLSX" ] || [ ! -f "$CLIENTS_XLSX" ]; then
  echo "ERROR: clients file not found under $DATA_DIR"
  echo "Run: git pull origin main"
  exit 1
fi
if [ -z "$TECHS_XLSX" ] || [ ! -f "$TECHS_XLSX" ]; then
  echo "ERROR: technicians file not found under $DATA_DIR"
  exit 1
fi
if [ -z "$ELEVATORS_XLSX" ] || [ ! -f "$ELEVATORS_XLSX" ]; then
  echo "ERROR: elevators file not found under $DATA_DIR"
  exit 1
fi

export DATABASE_URL="sqlite:///${DB_FILE}"

ARGS=(
  --clients "$CLIENTS_XLSX"
  --technicians "$TECHS_XLSX"
  --elevators "$ELEVATORS_XLSX"
)
if [ "$DRY" = "1" ]; then ARGS+=(--dry-run); fi
if [ "$SKIP_GEO" = "1" ]; then ARGS+=(--skip-geocode); fi

echo "=============================================="
echo "  Jama import: clients + technicians + elevators"
echo "  DB: $DB_FILE"
echo "  clients:     $CLIENTS_XLSX"
echo "  technicians: $TECHS_XLSX"
echo "  elevators:   $ELEVATORS_XLSX"
echo "=============================================="

python scripts/import_jama_core_three.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  sleep 2
  echo ""
  echo "Done — https://jama.liftcoreapp.com/clients"
fi
