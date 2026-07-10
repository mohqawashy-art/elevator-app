#!/usr/bin/env bash
# استيراد حزمة جما (عملاء/فنيين/مصاعد/عقود) إلى tenant jama على PostgreSQL
# Usage (GCP SSH):
#   cd ~/liftcore/elevator-app && git pull --ff-only origin main
#   bash deploy/import_jama_tenant_bundle.sh
#   bash deploy/import_jama_tenant_bundle.sh --dry-run
#   bash deploy/import_jama_tenant_bundle.sh --geocode

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
DATA_DIR="${DATA_DIR:-$APP_DIR/deploy/data/jama_import}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
SLUG="${SLUG:-jama}"
SERVICE_NAME="${SERVICE_NAME:-liftcore}"

CLIENTS="${CLIENTS:-}"
TECHS="${TECHS:-}"
ELEVS="${ELEVS:-}"
CONTRACTS="${CONTRACTS:-}"

EXTRA=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) EXTRA+=(--dry-run) ;;
    --geocode) EXTRA+=(--geocode) ;;
  esac
done

pick_latest() {
  local pattern="$1"
  local f
  f="$(ls -1t "$DATA_DIR"/$pattern 2>/dev/null | head -n1 || true)"
  echo "$f"
}

if [ -z "$CLIENTS" ]; then CLIENTS="$(pick_latest 'العملاء*.xlsx')"; fi
if [ -z "$TECHS" ]; then TECHS="$(pick_latest 'الفنيين*.xlsx')"; fi
if [ -z "$ELEVS" ]; then ELEVS="$(pick_latest 'المصاعد*.xlsx')"; fi
if [ -z "$CONTRACTS" ]; then CONTRACTS="$(pick_latest 'العقود*.xlsx')"; fi

echo "=============================================="
echo "  LiftCore — استيراد جما (tenant=$SLUG)"
echo "  $APP_DIR"
echo "=============================================="

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: app dir not found: $APP_DIR"
  exit 1
fi
cd "$APP_DIR"

if [ ! -f "$PLATFORM_ENV" ]; then
  echo "ERROR: missing $PLATFORM_ENV"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$PLATFORM_ENV"
set +a

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL empty in $PLATFORM_ENV"
  exit 1
fi

# shellcheck source=_common.sh
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
VENV="$(lc_resolve_venv "$APP_DIR" "$SERVICE_NAME")"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
if [ ! -x "$PY" ]; then
  echo "WARN: venv python not found at $VENV — using python3"
  PY=python3
  PIP=pip3
fi
echo "Python: $PY"

if ! "$PY" -c "import openpyxl" 2>/dev/null; then
  echo "==> installing openpyxl"
  "$PIP" install 'openpyxl>=3.1' || "$PY" -m pip install 'openpyxl>=3.1'
fi

echo "clients:      $CLIENTS"
echo "technicians:  $TECHS"
echo "elevators:    $ELEVS"
echo "contracts:    $CONTRACTS"

for f in "$CLIENTS" "$TECHS" "$ELEVS" "$CONTRACTS"; do
  if [ -z "$f" ] || [ ! -f "$f" ]; then
    echo "ERROR: missing Excel file: ${f:-<empty>}"
    echo "ضع الملفات في: $DATA_DIR"
    ls -la "$DATA_DIR" || true
    exit 1
  fi
done

echo "==> flask db upgrade (tenant code unique)"
"$PY" -m flask db upgrade || true

echo "==> import bundle"
"$PY" scripts/import_jama_tenant_bundle.py \
  --slug "$SLUG" \
  --clients "$CLIENTS" \
  --technicians "$TECHS" \
  --elevators "$ELEVS" \
  --contracts "$CONTRACTS" \
  "${EXTRA[@]}"

if [[ " ${EXTRA[*]} " != *" --dry-run "* ]]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  echo "Done — https://${SLUG}.liftcoreapp.com/clients"
fi
