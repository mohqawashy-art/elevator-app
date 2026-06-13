#!/usr/bin/env bash
# تحديد مواقع عملاء جما على الخريطة (lat/lng) من العناوين الموجودة في القاعدة
# Usage (GCP SSH):
#   bash deploy/geocode_jama_clients.sh
#   bash deploy/geocode_jama_clients.sh --dry-run

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
DRY="${DRY:-0}"
FORCE="${FORCE:-0}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --force) FORCE=1 ;;
  esac
done

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
export DATABASE_URL="sqlite:///${DB_FILE}"

ARGS=()
if [ "$DRY" = "1" ]; then
  ARGS+=(--dry-run)
fi
if [ "$FORCE" = "1" ]; then
  ARGS+=(--force)
fi

echo "==> Geocode Jama clients for map pins"
echo "    DB: $DB_FILE"
python scripts/geocode_customers.py "${ARGS[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart liftcore-jama 2>/dev/null || true
  echo "==> Done. Refresh https://jama.liftcoreapp.com/clients (map tab)"
fi
