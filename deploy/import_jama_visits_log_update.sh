#!/usr/bin/env bash
# تحديث سجل الزيارات والأعطال لجما من Excel واحد — خطوتان منفصلتان
# Usage (GCP SSH):
#   cd ~/liftcore/jama-elevator-app && git pull origin main
#   bash deploy/import_jama_visits_log_update.sh --dry-run
#   bash deploy/import_jama_visits_log_update.sh
#
# زيارات الصيانة فقط (صيانة دورية):
#   bash deploy/import_jama_visits_log_update.sh --visits-only
# أعطال فقط (عطل / زيارة متابعة):
#   bash deploy/import_jama_visits_log_update.sh --faults-only

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
XLSX="${XLSX:-$JAMA_DIR/deploy/data/jama_import/سجل الزيارات 1_7_2026.xlsx}"
SERVICE="${SERVICE:-liftcore-jama}"
DRY=0
RUN_VISITS=1
RUN_FAULTS=1

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --visits-only) RUN_FAULTS=0 ;;
    --faults-only) RUN_VISITS=0 ;;
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

EXTRA=()
if [ "$DRY" = "1" ]; then
  EXTRA+=(--dry-run)
fi

echo "==> Jama visits log import"
echo "    DB:   $DB_FILE"
echo "    File: $XLSX"
echo ""

if [ "$RUN_VISITS" = "1" ]; then
  echo "=============================================="
  echo "  1) زيارات الصيانة (صيانة دورية فقط)"
  echo "=============================================="
  python scripts/import_maintenance_visits_xlsx.py "$XLSX" "${EXTRA[@]}"
  echo ""
fi

if [ "$RUN_FAULTS" = "1" ]; then
  echo "=============================================="
  echo "  2) الأعطال (عطل + زيارة متابعة)"
  echo "=============================================="
  python scripts/import_faults_from_visits_xlsx.py "$XLSX" "${EXTRA[@]}"
  echo ""
fi

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE" 2>/dev/null || true
  echo "==> Done"
  [ "$RUN_VISITS" = "1" ] && echo "    Visits:  https://jama.liftcoreapp.com/maintenance-visits"
  [ "$RUN_FAULTS" = "1" ] && echo "    Faults:  https://jama.liftcoreapp.com/faults"
fi
