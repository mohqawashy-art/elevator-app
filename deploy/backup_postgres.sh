#!/usr/bin/env bash
# نسخ احتياطي PostgreSQL — Multi-Tenant / أسبوع 1
# يتطلب DATABASE_URL في البيئة أو /etc/liftcore/platform.env
#
#   bash deploy/backup_postgres.sh
#   bash deploy/backup_postgres.sh /path/to/app

set -euo pipefail

APP_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/liftcore/backups/postgres}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TS="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_ROOT"
mkdir -p "$DEST"

if [ -f /etc/liftcore/platform.env ]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/liftcore/platform.env
  set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL not set — add PostgreSQL URL to platform.env first"
  echo "  Or: export DATABASE_URL=postgresql://liftcore:PASS@127.0.0.1:5432/liftcore"
  exit 1
fi

export BACKUP_ROOT="$DEST"
cd "$APP_DIR"

if [ -f "$APP_DIR/scripts/backup_database.py" ]; then
  python3 "$APP_DIR/scripts/backup_database.py"
else
  echo "ERROR: scripts/backup_database.py not found"
  exit 1
fi

find "$DEST" -name 'liftcore-*.dump' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
echo "Retention: ${RETENTION_DAYS} days under $DEST"
