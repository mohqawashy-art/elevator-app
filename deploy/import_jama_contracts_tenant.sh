#!/usr/bin/env bash
# استيراد عقود جما من Excel إلى المستأجر jama (PostgreSQL)
# Usage (GCP SSH):
#   cd ~/liftcore/elevator-app
#   python3 scripts/delete_jama_contracts.py --slug jama --all --dry-run
#   python3 scripts/delete_jama_contracts.py --slug jama --all --yes
#   bash deploy/import_jama_contracts_tenant.sh --dry-run
#   bash deploy/import_jama_contracts_tenant.sh
#
# ملف مخصص:
#   XLSX=/path/to/file.xlsx bash deploy/import_jama_contracts_tenant.sh

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
DATA_DIR="${DATA_DIR:-$APP_DIR/deploy/data/jama_import}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
SLUG="${SLUG:-jama}"
SERVICE_NAME="${SERVICE_NAME:-liftcore}"
XLSX="${XLSX:-}"

DRY=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
  esac
done

pick_file() {
  local candidate
  for candidate in \
    "$DATA_DIR/jama_handover_contracts_1_11_2025.xlsx" \
    "$DATA_DIR/عقود_تسليم_1_11_2025.xlsx" \
    "$DATA_DIR/العقود 14_8_2026.xlsx" \
    "$DATA_DIR/العقود 10_7_2026.xlsx" \
    "$DATA_DIR/العقود 1_7_2026.xlsx"; do
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  ls -1t "$DATA_DIR"/*عقد*.xlsx "$DATA_DIR"/contracts*.xlsx 2>/dev/null | head -n1 || true
}

if [ -z "$XLSX" ]; then
  XLSX="$(pick_file)"
fi

echo "=============================================="
echo "  LiftCore — عقود (tenant=$SLUG)"
echo "=============================================="

cd "$APP_DIR"
# shellcheck source=_common.sh
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

set -a
# shellcheck source=/dev/null
source "$PLATFORM_ENV"
set +a

VENV="$(lc_resolve_venv "$APP_DIR" "$SERVICE_NAME")"
PY="$VENV/bin/python"
if [ ! -x "$PY" ]; then PY=python3; fi
echo "Python: $PY"
echo "File:   $XLSX"

if [ -z "$XLSX" ] || [ ! -f "$XLSX" ]; then
  echo "ERROR: Excel not found"
  ls -la "$DATA_DIR" || true
  exit 1
fi

"$PY" -m pip install -q openpyxl pandas

if [ "$DRY" = "1" ]; then
  "$PY" scripts/import_jama_contracts.py "$XLSX" --slug "$SLUG" --dry-run
else
  "$PY" scripts/import_jama_contracts.py "$XLSX" --slug "$SLUG" --yes
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  echo ""
  echo "Done — https://${SLUG}.liftcoreapp.com/contracts"
fi
