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
  exit 1
fi

if [ -d "$APP_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$APP_DIR/.venv/bin/activate"
fi

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

python scripts/migrate_instance_to_tenant.py "${MIGRATE_ARGS[@]}"

if [ "$DRY_RUN" -eq 1 ]; then
  _log "Dry-run complete — re-run without --dry-run to apply"
  exit 0
fi

_log "Verify migration counts"
python scripts/verify_tenant_migration.py --slug "$TENANT_SLUG"

_log "Alembic revision"
python deploy/migrate_db.py

_log "Smoke tests (tenant isolation)"
python -m pytest tests/test_tenant_isolation.py -q --tb=line || true

_log "Next steps (manual):"
echo "  1) Uncomment/set DATABASE_URL in /etc/liftcore/platform.env"
echo "  2) sudo systemctl restart liftcore"
echo "  3) bash deploy/verify_deploy.sh https://app.liftcoreapp.com"
echo "  4) bash deploy/REGRESSION_CHECKLIST.txt (manual QA)"
echo "  5) Optional jama demo: seed_data or second migrate --slug jama --append"
