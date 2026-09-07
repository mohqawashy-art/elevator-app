#!/usr/bin/env bash
# استعادة بيئة الاختبار من نسخة نظيفة قبل نسخ بيانات جما.
set -euo pipefail

BACKUP="${1:-/var/backups/liftcore-staging/pre-c2ef0da0e6e6-20260828111407.dump}"
ENV_FILE="/etc/liftcore/staging.env"
SERVICE="liftcore-staging"
VENV="/opt/liftcore-staging/venv/bin/python"
CURRENT="/opt/liftcore-staging/current"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run with sudo"
  exit 1
fi
if [ ! -f "$BACKUP" ]; then
  echo "ERROR: backup not found: $BACKUP"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "==> stop $SERVICE"
systemctl stop "$SERVICE"

echo "==> restore staging DB from $BACKUP"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PGDATABASE}' AND pid <> pg_backend_pid();" || true
sudo -u postgres dropdb --if-exists "$PGDATABASE"
sudo -u postgres createdb --owner="$PGUSER" "$PGDATABASE"
sudo -u postgres pg_restore -d "$PGDATABASE" --no-owner --role="$PGUSER" "$BACKUP"

echo "==> migrate + seed"
export LIFTCORE_ENV_FILE="$ENV_FILE"
export LIFTCORE_ALEMBIC=1
cd "$CURRENT"
sudo -u liftcore-staging env \
  DATABASE_URL="$DATABASE_URL" \
  LIFTCORE_ENV_FILE="$ENV_FILE" \
  LIFTCORE_ALEMBIC=1 \
  "$VENV" deploy/migrate_db.py
sudo -u liftcore-staging env \
  DATABASE_URL="$DATABASE_URL" \
  LIFTCORE_ENV_FILE="$ENV_FILE" \
  "$VENV" deploy/staging/seed_staging.py

echo "==> set test login (staging DB only)"
sudo -u liftcore-staging env \
  DATABASE_URL="$DATABASE_URL" \
  LIFTCORE_ENV_FILE="$ENV_FILE" \
  "$VENV" scripts/set_user_login.py \
  --username mohammed \
  --full-name 'محمد عبدالعزيز' \
  --email mohammed@test.local \
  --password 'Bf@123456' \
  --org-slug test \
  --apply

systemctl start "$SERVICE"
for _ in $(seq 1 15); do
  if curl --fail --silent --max-time 3 -H "Host: test.liftcoreapp.com" http://127.0.0.1:5003/api/health >/dev/null; then
    echo "==> staging restored and healthy"
    exit 0
  fi
  sleep 2
done
echo "ERROR: health check failed after restore"
exit 1
