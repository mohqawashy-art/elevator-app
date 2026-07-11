#!/usr/bin/env bash
# استيراد مصروفات جما من Excel إلى المستأجر jama (PostgreSQL)
# Usage (GCP SSH):
#   cd ~/liftcore/elevator-app && git pull --ff-only origin main
#   bash deploy/import_jama_expenses_tenant.sh --dry-run
#   bash deploy/import_jama_expenses_tenant.sh
#   bash deploy/import_jama_expenses_tenant.sh --sync
#
# ملف مخصص:
#   XLSX=/path/to/file.xlsx bash deploy/import_jama_expenses_tenant.sh

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
DATA_DIR="${DATA_DIR:-$APP_DIR/deploy/data/jama_import}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
SLUG="${SLUG:-jama}"
SERVICE_NAME="${SERVICE_NAME:-liftcore}"
XLSX="${XLSX:-}"

DRY=0
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1; EXTRA+=(--dry-run) ;;
    --force) EXTRA+=(--force) ;;
    --sync) EXTRA+=(--sync) ;;
  esac
done

pick_file() {
  local candidate
  for candidate in \
    "$DATA_DIR/expenses_11_7_2026.xlsx" \
    "$DATA_DIR/المصروفات 11_7_2026.xlsx" \
    "$DATA_DIR/expenses_27_6_2026.xlsx" \
    "$DATA_DIR/المصروفات 1_7_2026.xlsx"; do
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  ls -1t "$DATA_DIR"/المصروفات*.xlsx "$DATA_DIR"/expenses*.xlsx 2>/dev/null | head -n1 || true
}

if [ -z "$XLSX" ]; then
  XLSX="$(pick_file)"
fi

echo "=============================================="
echo "  LiftCore — مصروفات (tenant=$SLUG)"
echo "=============================================="

cd "$APP_DIR"
# shellcheck source=_common.sh
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

set -a
# shellcheck disable=SC1090
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

"$PY" scripts/import_jama_expenses.py "$XLSX" --slug "$SLUG" "${EXTRA[@]}"

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  echo ""
  echo "Done — https://${SLUG}.liftcoreapp.com/expenses"
fi
