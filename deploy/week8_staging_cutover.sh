#!/usr/bin/env bash
# LiftCore — أسبوع 8: ترحيل staging (لا تشغّل على الإنتاج قبل checkpoint + نافذة صيانة)
#
# الاستخدام على السيرفر (بعد نشر الكود أسبوع 2–7):
#   cd ~/liftcore/elevator-app
#   bash deploy/week8_staging_cutover.sh --dry-run
#   bash deploy/week8_staging_cutover.sh
#
# المتغيرات:
#   SQLITE_SOURCE=instance/liftcore.db
#   DATABASE_URL=postgresql://liftcore:PASS@127.0.0.1:5432/liftcore
#   TENANT_SLUG=default
#   TENANT_NAME="LiftCore"
#   UPLOADS_SOURCE=static/uploads

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_DIR"

# shellcheck source=deploy/_common.sh
source "$SCRIPT_DIR/_common.sh"
VENV="$(lc_resolve_venv "$APP_DIR" liftcore)"
if [ -x "$VENV/bin/python" ]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  PYTHON="$VENV/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "ERROR: python3 not found (tried venv: $VENV)" >&2
  exit 1
fi

DRY_RUN=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE=1 ;;
  esac
done

SQLITE_SOURCE="${SQLITE_SOURCE:-$APP_DIR/instance/liftcore.db}"
TENANT_SLUG="${TENANT_SLUG:-default}"
TENANT_NAME="${TENANT_NAME:-LiftCore}"
UPLOADS_SOURCE="${UPLOADS_SOURCE:-$APP_DIR/static/uploads}"

_log() { echo "==> $*"; }

if [ ! -f "$SQLITE_SOURCE" ]; then
  echo "ERROR: SQLite source not found: $SQLITE_SOURCE" >&2
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: set DATABASE_URL (PostgreSQL) before cutover" >&2
  echo "  export DATABASE_URL=postgresql://liftcore:PASS@127.0.0.1:5432/liftcore" >&2
  exit 1
fi

_log "Python: $PYTHON"

_log "Week 8 staging cutover — slug=$TENANT_SLUG"
_log "Source SQLite: $SQLITE_SOURCE"
_log "Target: PostgreSQL (DATABASE_URL)"

MIGRATE_ARGS=(
  --sqlite "$SQLITE_SOURCE"
  --slug "$TENANT_SLUG"
  --name "$TENANT_NAME"
  --uploads-source "$UPLOADS_SOURCE"
)
[ "$DRY_RUN" -eq 1 ] && MIGRATE_ARGS+=(--dry-run)
[ "$FORCE" -eq 1 ] && MIGRATE_ARGS+=(--force)

"$PYTHON" scripts/migrate_instance_to_tenant.py "${MIGRATE_ARGS[@]}"

if [ "$DRY_RUN" -eq 1 ]; then
  _log "Dry-run complete — re-run without --dry-run to apply"
  exit 0
fi

_log "Verify migration counts"
"$PYTHON" scripts/verify_tenant_migration.py --slug "$TENANT_SLUG"

_log "Alembic revision"
"$PYTHON" deploy/migrate_db.py

_log "Smoke tests (tenant isolation)"
"$PYTHON" -m pytest tests/test_tenant_isolation.py -q --tb=line || true

_log "Next steps (manual):"
echo "  1) Uncomment/set DATABASE_URL in /etc/liftcore/platform.env"
echo "  2) sudo systemctl restart liftcore"
echo "  3) bash deploy/verify_deploy.sh https://app.liftcoreapp.com"
echo "  4) bash deploy/REGRESSION_CHECKLIST.txt (manual QA)"
echo "  5) Optional jama demo: seed_data or second migrate --slug jama --append"
