#!/usr/bin/env bash
# LiftCore — استيراد حزمة النقل على السيرفر الجديد
#   sudo bash deploy/hetzner/import_to_new.sh /home/info/migration-export-YYYYMMDD.tar.gz
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: شغّل كـ root"
  exit 1
fi

BUNDLE="${1:?path to migration-export-*.tar.gz or extracted directory}"
APP_USER="${APP_USER:-info}"
APP_DIR="${APP_DIR:-/home/${APP_USER}/liftcore/elevator-app}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
WORK="$(mktemp -d /tmp/liftcore-import.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

_log() { echo "==> $*"; }

if [ -f "$BUNDLE" ]; then
  tar -xzf "$BUNDLE" -C "$WORK"
  SRC="$(find "$WORK" -maxdepth 1 -type d -name 'migration-export-*' | head -1)"
  SRC="${SRC:-$WORK}"
elif [ -d "$BUNDLE" ]; then
  SRC="$BUNDLE"
else
  echo "ERROR: $BUNDLE غير موجود"
  exit 1
fi

if [ ! -f "$PLATFORM_ENV" ]; then
  echo "ERROR: شغّل bootstrap.sh أولاً"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$PLATFORM_ENV"
set +a
NEW_DATABASE_URL="$DATABASE_URL"
NEW_PGPASSWORD="${PGPASSWORD:-}"
NEW_PGUSER="${PGUSER:-liftcore}"
NEW_PGDB="${PGDATABASE:-liftcore}"

merge_env_key() {
  local key="$1"
  local src_file="$2"
  local line val
  line="$(grep -E "^${key}=" "$src_file" 2>/dev/null | tail -n1 || true)"
  [ -n "$line" ] || return 0
  val="${line#*=}"
  [ -n "$val" ] || return 0
  if grep -qE "^${key}=" "$PLATFORM_ENV"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$PLATFORM_ENV"
  else
    printf '%s\n' "${key}=${val}" >>"$PLATFORM_ENV"
  fi
}

if [ -f "$SRC/platform.env" ]; then
  _log "دمج أسرار الإنتاج (بدون DATABASE_URL القديم)"
  for key in SECRET_KEY GOOGLE_MAPS_API_KEY MAIL_API_KEY MAIL_FROM \
    LIFTCORE_SALES_EMAIL LIFTCORE_SUPPORT_EMAIL LIFTCORE_PUBLIC_BASE \
    LIFTCORE_OPERATOR_ORGS MOYASAR_SECRET_KEY MOYASAR_PUBLISHABLE_KEY \
    SENTRY_DSN SENTRY_ENVIRONMENT WHATSAPP_VERIFY_TOKEN LIFTCORE_GTAG_ID \
    LIFTCORE_SIGNUP_ENABLED LIFTCORE_COMING_SOON; do
    merge_env_key "$key" "$SRC/platform.env"
  done
  if grep -qE '^DATABASE_URL=' "$PLATFORM_ENV"; then
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${NEW_DATABASE_URL}|" "$PLATFORM_ENV"
  fi
  chown "root:${APP_USER}" "$PLATFORM_ENV"
  chmod 640 "$PLATFORM_ENV"
fi

set -a
# shellcheck disable=SC1090
source "$PLATFORM_ENV"
set +a

restore_uploads() {
  local archive="$1"
  local dest="$2"
  [ -f "$archive" ] || return 0
  mkdir -p "$dest"
  tar -xzf "$archive" -C "$dest"
  _log "uploads → $dest"
}

restore_uploads "$SRC/uploads-main.tar.gz" "${APP_DIR}/static"
restore_uploads "$SRC/uploads-root.tar.gz" "${APP_DIR}"
chown -R "${APP_USER}:${APP_USER}" \
  "${APP_DIR}/static/uploads" \
  "${APP_DIR}/uploads" \
  "${APP_DIR}/instance" 2>/dev/null || true

KIND="$(tr -d '\r\n' < "$SRC/db-kind.txt" 2>/dev/null || echo sqlite)"
_log "قاعدة: $KIND"
MIGRATE_URL="$(printf '%s' "$NEW_DATABASE_URL" | sed -E 's/postgresql\+psycopg[0-9]*:/postgresql:/')"

systemctl stop liftcore || true
sleep 1
sudo -u postgres psql -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${NEW_PGDB}' AND pid <> pg_backend_pid();" >/dev/null || true

if [ -f "$SRC/liftcore.dump" ]; then
  _log "pg_restore"
  install -m 0640 -o postgres -g postgres "$SRC/liftcore.dump" /tmp/liftcore.dump
  sudo -u postgres dropdb --if-exists "$NEW_PGDB"
  sudo -u postgres createdb -O "$NEW_PGUSER" "$NEW_PGDB"
  sudo -u postgres pg_restore -d "$NEW_PGDB" --no-owner --role="$NEW_PGUSER" \
    /tmp/liftcore.dump || true
  rm -f /tmp/liftcore.dump
elif ls "$SRC"/*.db >/dev/null 2>&1; then
  SQLITE_FILE="$(ls "$SRC"/*liftcore.db "$SRC"/instance-liftcore.db 2>/dev/null | head -1 || true)"
  if [ -z "$SQLITE_FILE" ]; then
    SQLITE_FILE="$(ls "$SRC"/*.db | head -1)"
  fi
  _log "SQLite → PostgreSQL: $SQLITE_FILE"
  sudo -u postgres dropdb --if-exists "$NEW_PGDB"
  sudo -u postgres createdb -O "$NEW_PGUSER" "$NEW_PGDB"
  install -m 0644 "$SQLITE_FILE" "${APP_DIR}/instance/import-source.db"
  chown "${APP_USER}:${APP_USER}" "${APP_DIR}/instance/import-source.db"
  sudo -u "$APP_USER" env \
    DATABASE_URL="$MIGRATE_URL" \
    SECRET_KEY="${SECRET_KEY}" \
    SQLITE_SOURCE="${APP_DIR}/instance/import-source.db" \
    MIGRATE_FORCE=1 \
    "${APP_DIR}/.venv/bin/python" "${APP_DIR}/scripts/migrate_sqlite_to_postgres.py"
else
  echo "ERROR: لا dump ولا sqlite في الحزمة"
  exit 1
fi

systemctl restart liftcore
sleep 3
if ! systemctl is-active --quiet liftcore; then
  journalctl -u liftcore -n 40 --no-pager
  exit 1
fi

HEALTH="$(curl -fsS http://127.0.0.1/api/health || true)"
echo ""
echo "=============================================="
echo "  الاستيراد اكتمل"
echo "  health: $HEALTH"
echo "  سجّل الدخول عبر hosts أو IP ثم فعّل النسخ الاحتياطي:"
echo "    sudo -u ${APP_USER} bash ${APP_DIR}/deploy/install_backup_cron.sh ${APP_DIR}"
echo "=============================================="
