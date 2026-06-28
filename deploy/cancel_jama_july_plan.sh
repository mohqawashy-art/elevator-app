#!/usr/bin/env bash
# إلغاء خطة صيانة يوليو على جما
#   bash deploy/cancel_jama_july_plan.sh
#   bash deploy/cancel_jama_july_plan.sh --dry-run
#   PLAN_MONTH=2026-07 bash deploy/cancel_jama_july_plan.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
PLAN_MONTH="${PLAN_MONTH:-2026-07}"
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) EXTRA+=(--dry-run) ;;
  esac
done

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
export DATABASE_URL="sqlite:///${DB_FILE}"

echo "=============================================="
echo "  Cancel maintenance plan: $PLAN_MONTH"
echo "  DB: $DB_FILE"
echo "=============================================="

python scripts/cancel_maintenance_plan.py "$PLAN_MONTH" "${EXTRA[@]}"

if [[ " ${EXTRA[*]} " != *" --dry-run "* ]]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  echo ""
  echo "Done — https://jama.liftcoreapp.com/maintenance-visits"
fi
