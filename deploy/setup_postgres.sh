#!/usr/bin/env bash
# LiftCore — تثبيت PostgreSQL للتحضير لـ Multi-Tenant (أسبوع 1)
# لا يغيّر التطبيق إلى PostgreSQL تلقائياً — يجهّز القاعدة فقط.
#
#   bash deploy/setup_postgres.sh
#
# متغيرات:
#   PG_USER=liftcore
#   PG_DB=liftcore
#   PG_PASSWORD=          إن تُركت فارغة يُولَّد مفتاح عشوائي

set -euo pipefail

PG_USER="${PG_USER:-liftcore}"
PG_DB="${PG_DB:-liftcore}"
PG_PASSWORD="${PG_PASSWORD:-}"

if [ -z "$PG_PASSWORD" ]; then
  PG_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  echo "==> Generated PG_PASSWORD (save this): $PG_PASSWORD"
fi

echo "==> 1) Install PostgreSQL"
if ! command -v psql >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y postgresql postgresql-contrib
else
  echo "  postgresql already installed"
fi

echo "==> 2) Create role and database (idempotent)"
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${PG_USER}'" | grep -q 1; then
  echo "  role $PG_USER exists"
else
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE USER ${PG_USER} WITH PASSWORD '${PG_PASSWORD}';
SQL
  echo "  created role $PG_USER"
fi

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1; then
  echo "  database $PG_DB exists"
else
  sudo -u postgres createdb -O "$PG_USER" "$PG_DB"
  echo "  created database $PG_DB"
fi

echo ""
echo "=============================================="
echo "  PostgreSQL ready"
echo ""
echo "  Add to /etc/liftcore/platform.env (DO NOT enable on live app yet):"
echo "  DATABASE_URL=postgresql://${PG_USER}:${PG_PASSWORD}@127.0.0.1:5432/${PG_DB}"
echo ""
echo "  Test connection:"
echo "    PGPASSWORD='...' psql -h 127.0.0.1 -U ${PG_USER} -d ${PG_DB} -c 'SELECT 1'"
echo "=============================================="
