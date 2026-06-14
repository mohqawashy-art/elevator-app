#!/usr/bin/env bash
# حذف زيارات «عطل» من جدول الصيانة (تبقى في الأعطال)
set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
DRY="${DRY:-0}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
  esac
done

cd "$JAMA_DIR"
source "$VENV/bin/activate"
export DATABASE_URL="sqlite:///${DB_FILE}"

ARGS=()
if [ "$DRY" = "1" ]; then
  ARGS+=(--dry-run)
fi

python scripts/remove_fault_maintenance_visits.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart liftcore-jama 2>/dev/null || true
fi
