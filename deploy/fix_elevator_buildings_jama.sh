#!/usr/bin/env bash
# تصحيح أسماء المباني للمصاعد — قاعدة jama.db
# Usage (GCP SSH):
#   cd ~/liftcore/jama-elevator-app && git pull origin main
#   bash deploy/fix_elevator_buildings_jama.sh --dry-run
#   bash deploy/fix_elevator_buildings_jama.sh --customer "حمدي حمدان الوافي"
#   bash deploy/fix_elevator_buildings_jama.sh --customer-code C-0051

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
SERVICE="${SERVICE:-liftcore-jama}"

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: Jama app dir not found: $JAMA_DIR"
  exit 1
fi

if [ ! -f "$DB_FILE" ]; then
  echo "ERROR: Database not found: $DB_FILE"
  exit 1
fi

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

export DATABASE_URL="sqlite:///${DB_FILE}"

ARGS=()
while [ $# -gt 0 ]; do
  ARGS+=("$1")
  shift
done

echo "==> Fix elevator building labels (Jama)"
echo "    DB: $DB_FILE"
python scripts/fix_elevator_building_labels.py "${ARGS[@]}"

echo ""
echo "==> تحقق (عينة)"
export DATABASE_URL="sqlite:///${DB_FILE}"
python scripts/verify_elevator_buildings.py --customer "حمدي" --limit 12 2>/dev/null || true

if printf '%s\n' "${ARGS[@]}" | grep -qx -- '--dry-run'; then
  exit 0
fi

sudo systemctl restart "$SERVICE" 2>/dev/null || true
echo "==> Done — https://jama.liftcoreapp.com/elevators"
