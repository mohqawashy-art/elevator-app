#!/usr/bin/env bash
# يضمن وجود SECRET_KEY في /etc/liftcore/platform.env (لا يغيّر مفتاحاً موجوداً)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"

sudo mkdir -p /etc/liftcore
if [ ! -f "$PLATFORM_ENV" ]; then
  sudo touch "$PLATFORM_ENV"
fi

_env_has() {
  if [ -r "$PLATFORM_ENV" ]; then
    grep -qE "^${1}=" "$PLATFORM_ENV" 2>/dev/null
  else
    sudo grep -qE "^${1}=" "$PLATFORM_ENV" 2>/dev/null
  fi
}

if ! _env_has SECRET_KEY; then
  NEW_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  echo "SECRET_KEY=${NEW_SECRET}" | sudo tee -a "$PLATFORM_ENV" >/dev/null
  echo "==> أُضيف SECRET_KEY إلى $PLATFORM_ENV"
else
  echo "==> SECRET_KEY موجود في $PLATFORM_ENV"
fi

if ! _env_has LIFTCORE_HTTPS; then
  echo "LIFTCORE_HTTPS=1" | sudo tee -a "$PLATFORM_ENV" >/dev/null
  echo "==> أُضيف LIFTCORE_HTTPS=1"
fi

lc_fix_platform_env_perms "$PLATFORM_ENV"

bash "$SCRIPT_DIR/check_platform_env.sh"
