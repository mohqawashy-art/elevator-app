#!/usr/bin/env bash
# استيراد سجل الزيارات لجما: زيارات دورية → visits ، أعطال → faults
# Usage (GCP SSH):
#   cd ~/liftcore/elevator-app && git pull --ff-only origin main
#   bash deploy/import_jama_visits_faults_tenant.sh
#   bash deploy/import_jama_visits_faults_tenant.sh --dry-run
#   bash deploy/import_jama_visits_faults_tenant.sh --visits-only
#   bash deploy/import_jama_visits_faults_tenant.sh --faults-only

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
DATA_DIR="${DATA_DIR:-$APP_DIR/deploy/data/jama_import}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
SLUG="${SLUG:-jama}"
SERVICE_NAME="${SERVICE_NAME:-liftcore}"
XLSX="${XLSX:-}"

DRY=0
RUN_VISITS=1
RUN_FAULTS=1
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1; EXTRA+=(--dry-run) ;;
    --visits-only) RUN_FAULTS=0 ;;
    --faults-only) RUN_VISITS=0 ;;
  esac
done

pick_latest() {
  ls -1t "$DATA_DIR"/سجل\ الزيارات*.xlsx 2>/dev/null | head -n1 || true
}

if [ -z "$XLSX" ]; then
  XLSX="$(pick_latest)"
fi

echo "=============================================="
echo "  LiftCore — زيارات + أعطال (tenant=$SLUG)"
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

if [ "$RUN_VISITS" = "1" ]; then
  echo ""
  echo "==> [1/2] زيارات الصيانة (صيانة دورية + متابعة)"
  "$PY" scripts/import_maintenance_visits_xlsx.py "$XLSX" --slug "$SLUG" "${EXTRA[@]}"
fi

if [ "$RUN_FAULTS" = "1" ]; then
  echo ""
  echo "==> [2/2] الأعطال (صفوف نوع الزيارة = عطل)"
  "$PY" scripts/import_faults_from_visits_xlsx.py "$XLSX" --slug "$SLUG" "${EXTRA[@]}"
fi

if [ "$DRY" != "1" ]; then
  sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
  echo ""
  echo "Done"
  [ "$RUN_VISITS" = "1" ] && echo "  Visits: https://${SLUG}.liftcoreapp.com/maintenance-visits"
  [ "$RUN_FAULTS" = "1" ] && echo "  Faults: https://${SLUG}.liftcoreapp.com/faults"
fi
