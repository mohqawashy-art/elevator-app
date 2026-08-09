#!/usr/bin/env bash
# ترحيل أرقام مصاعد جما لإفراغ EL-0043 (أو رقم آخر)
# Usage (GCP SSH):
#   cd ~/liftcore/jama-elevator-app && git pull origin main
#   bash deploy/shift_jama_elevator_43.sh --dry-run
#   bash deploy/shift_jama_elevator_43.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
FROM_NUM="${FROM_NUM:-43}"
DRY=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --from=*) FROM_NUM="${arg#--from=}" ;;
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

ARGS=(--slug jama --from "$FROM_NUM")
if [ "$DRY" = "1" ]; then
  ARGS+=(--dry-run)
else
  ARGS+=(--yes)
fi

echo "==> Shift elevator codes from EL-$(printf '%04d' "$FROM_NUM") upward (+1)"
python scripts/shift_elevator_codes.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart liftcore-jama 2>/dev/null || true
  echo "==> Done. Refresh https://jama.liftcoreapp.com/elevators"
fi
