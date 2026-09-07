#!/usr/bin/env bash
# تشغيل سكربتات الصيانة على قاعدة staging فقط — لا يلمس الإنتاج.
set -euo pipefail
ENV_FILE="/etc/liftcore/staging.env"
CURRENT="/opt/liftcore-staging/current"
PY="/opt/liftcore-staging/venv/bin/python"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run with sudo"
  exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: missing $ENV_FILE"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
export LIFTCORE_ENV_FILE="$ENV_FILE"
export LIFTCORE_ALEMBIC=1

cd "$CURRENT"
exec sudo -u liftcore-staging env \
  DATABASE_URL="$DATABASE_URL" \
  LIFTCORE_ENV_FILE="$ENV_FILE" \
  LIFTCORE_ALEMBIC=1 \
  "$PY" "$@"
