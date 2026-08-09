#!/usr/bin/env bash
# إضافة EL-0043 لعبد الرحمن باقيس على جما
# Usage:
#   bash deploy/add_jama_elevator_43_baqees.sh --dry-run
#   bash deploy/add_jama_elevator_43_baqees.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DRY=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
  esac
done

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

if [ -f /etc/liftcore/platform.env ]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/liftcore/platform.env
  set +a
elif [ -f "$JAMA_DIR/instance/jama.db" ]; then
  export DATABASE_URL="sqlite:///${JAMA_DIR}/instance/jama.db"
fi

ARGS=(--slug jama)
if [ "$DRY" = "1" ]; then
  ARGS+=(--dry-run)
else
  ARGS+=(--yes)
fi

echo "==> Add EL-0043 for عبد الرحمن باقيس"
python scripts/add_elevator_baqees_43.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart liftcore-jama 2>/dev/null || true
  echo "==> Done. Refresh https://jama.liftcoreapp.com/elevators"
fi
