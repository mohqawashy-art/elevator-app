#!/usr/bin/env bash
# نسخة احتياطية PostgreSQL (أو SQLite محلي) — لا تعتمد على قراءة platform.env
set -euo pipefail

APP_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TS="$(date +%Y%m%d-%H%M%S)"
PG_DB="${PGDATABASE:-liftcore}"

if [ -n "${BACKUP_ROOT:-}" ]; then
  DEST="$BACKUP_ROOT/$(basename "$APP_DIR")"
elif [ -d /home/info/liftcore/backups ]; then
  DEST="/home/info/liftcore/backups/$(basename "$APP_DIR")"
else
  DEST="${HOME}/liftcore/backups/$(basename "$APP_DIR")"
fi

mkdir -p "$DEST"
found=0

dump_postgres() {
  local dest="$1"
  command -v pg_dump >/dev/null 2>&1 || return 1
  if [ "$(id -u)" = "0" ]; then
    sudo -u postgres pg_dump -Fc "$PG_DB" >"$dest"
    return $?
  fi
  sudo -n -u postgres pg_dump -Fc "$PG_DB" >"$dest" 2>/dev/null
}

DUMP_FILE="$DEST/liftcore-${TS}.dump"
if dump_postgres "$DUMP_FILE" && [ -s "$DUMP_FILE" ]; then
  found=1
  echo "OK PostgreSQL backup: $DUMP_FILE"
  if id info >/dev/null 2>&1; then
    chown info:info "$DUMP_FILE" 2>/dev/null || true
  fi
else
  rm -f "$DUMP_FILE"
  if [ -r /etc/liftcore/platform.env ]; then
    set -a
    # shellcheck disable=SC1091
    source /etc/liftcore/platform.env
    set +a
  fi
  if [ -f "$APP_DIR/scripts/backup_database.py" ]; then
    export BACKUP_ROOT="$DEST"
    if python3 "$APP_DIR/scripts/backup_database.py"; then
      found=1
    fi
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
