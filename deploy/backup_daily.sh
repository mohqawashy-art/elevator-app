#!/usr/bin/env bash
# نسخة احتياطية يومية — SQLite أو PostgreSQL (حسب DATABASE_URL)
set -euo pipefail

APP_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/liftcore/backups}"
TS="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_ROOT/$(basename "$APP_DIR")"

mkdir -p "$DEST"

found=0
if [ -f "$APP_DIR/scripts/backup_database.py" ]; then
  export BACKUP_ROOT="$DEST"
  if [ -f /etc/liftcore/platform.env ]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/liftcore/platform.env
  set +a
  fi
  if python3 "$APP_DIR/scripts/backup_database.py"; then
    found=1
  fi
fi

if [ "$found" -eq 0 ]; then
  for db in "$APP_DIR/instance/liftcore.db" "$APP_DIR/liftcore.db"; do
    if [ -f "$db" ]; then
      cp "$db" "$DEST/liftcore-${TS}.db"
      echo "OK backup: $DEST/liftcore-${TS}.db"
      found=1
      break
    fi
  done
fi

if [ "$found" -eq 0 ]; then
  echo "WARN: no database found under $APP_DIR"
  exit 1
fi

find "$DEST" \( -name 'liftcore-*.db' -o -name 'liftcore-*.dump' \) -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
echo "Retention: ${RETENTION_DAYS} days"
