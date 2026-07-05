#!/usr/bin/env bash
# تحقق من /etc/liftcore/platform.env قبل إعادة تشغيل الخدمة
set -euo pipefail

PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"

if [ ! -f "$PLATFORM_ENV" ]; then
  echo "ERROR: ملف الإعدادات غير موجود: $PLATFORM_ENV"
  echo "  أنشئه مثلاً:"
  echo "    sudo mkdir -p /etc/liftcore"
  echo "    sudo nano $PLATFORM_ENV"
  exit 1
fi

_env_val() {
  local key="$1"
  grep -E "^${key}=" "$PLATFORM_ENV" 2>/dev/null | tail -n1 | cut -d= -f2- | sed 's/^["'\'']//;s/["'\'']$//' | tr -d '\r' || true
}

SECRET_KEY="$(_env_val SECRET_KEY)"
HTTPS="$(_env_val LIFTCORE_HTTPS)"
MAPS_KEY="$(_env_val GOOGLE_MAPS_API_KEY)"

echo "==> platform env: $PLATFORM_ENV"

if [ -z "$HTTPS" ]; then
  echo "  WARN: LIFTCORE_HTTPS غير مضبوط"
fi

if [ -z "$SECRET_KEY" ]; then
  echo "ERROR: SECRET_KEY مفقود في $PLATFORM_ENV"
  echo "  ولّد مفتاحاً:"
  echo "    python3 -c \"import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))\""
  echo "  ثم أضف السطر للملف وأعد: sudo systemctl restart liftcore"
  exit 1
fi

case "$SECRET_KEY" in
  liftcore-secret-2025|dev-secret|change-me|generate-a-long-random-string-here)
    echo "ERROR: SECRET_KEY ضعيف/افتراضي — غيّره في $PLATFORM_ENV"
    exit 1
    ;;
esac

if [ "${#SECRET_KEY}" -lt 24 ]; then
  echo "ERROR: SECRET_KEY قصير جداً (${#SECRET_KEY} حرف) — استخدم 32+ حرف"
  exit 1
fi

echo "  SECRET_KEY: OK (${#SECRET_KEY} chars)"
if [ -n "$MAPS_KEY" ]; then
  echo "  GOOGLE_MAPS_API_KEY: OK"
else
  echo "  WARN: GOOGLE_MAPS_API_KEY فارغ — الخرائط ستستخدم OSM"
fi

echo "==> platform env OK"
