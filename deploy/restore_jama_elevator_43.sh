#!/usr/bin/env bash
# إرجاع EL-0043 لمبارك هلال النفيعى على جما (عكس الترحيل إن وُجد)
# Usage:
#   bash deploy/restore_jama_elevator_43.sh --dry-run
#   bash deploy/restore_jama_elevator_43.sh

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

echo "==> Restore EL-0043 → مبارك هلال النفيعى"
python scripts/restore_elevator_43_nafiei.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart liftcore-jama 2>/dev/null || true
  echo "==> Done. Refresh https://jama.liftcoreapp.com/elevators"
fi
