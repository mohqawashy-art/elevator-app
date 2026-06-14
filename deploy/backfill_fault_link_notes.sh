#!/usr/bin/env bash
# تحديث ربط الزيارة/العقد في ملاحظات الأعطال (LiftCore + Jama)
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/jama-elevator-app}"
if [ -d "$HOME/liftcore/elevator-app" ] && [ "${TENANT:-jama}" = "liftcore" ]; then
  APP_DIR="$HOME/liftcore/elevator-app"
fi

VENV="${VENV:-$APP_DIR/.venv}"
DB_FILE="${DB_FILE:-$APP_DIR/instance/jama.db}"
if [ "${TENANT:-}" = "liftcore" ] || [ -f "$APP_DIR/instance/liftcore.db" ]; then
  DB_FILE="${DB_FILE:-$APP_DIR/instance/liftcore.db}"
fi
XLSX="${XLSX:-$APP_DIR/deploy/data/jama_visits_14_6_2026.xlsx}"
DRY="${DRY:-0}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
  esac
done

cd "$APP_DIR"
source "$VENV/bin/activate"
export DATABASE_URL="sqlite:///${DB_FILE}"

ARGS=("$XLSX")
[ "$DRY" = "1" ] && ARGS+=(--dry-run)

python scripts/backfill_fault_link_notes.py "${ARGS[@]}"
