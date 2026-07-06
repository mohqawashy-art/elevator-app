#!/usr/bin/env bash
# فحص النواقص التشغيلية على السيرفر (backup cron، Sentry، آخر نسخة)
#   bash deploy/check_production_ops.sh [APP_DIR]

set -euo pipefail

APP_DIR="${1:-${APP_DIR:-$HOME/liftcore/elevator-app}}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/liftcore/backups}"
FAIL=0
WARN=0

warn() { echo "  WARN: $*"; WARN=$((WARN + 1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL + 1)); }
ok() { echo "  OK: $*"; }

echo "==> LiftCore production ops check"
echo "    APP_DIR=$APP_DIR"

if crontab -l 2>/dev/null | grep -q 'liftcore-daily-backup'; then
  ok 'backup cron مفعّل'
else
  warn 'backup cron غير مفعّل — شغّل: bash deploy/install_backup_cron.sh'
fi

if crontab -l 2>/dev/null | grep -q 'liftcore-auto-update'; then
  ok 'auto-update cron مفعّل'
else
  warn 'auto-update cron غير مفعّل — شغّل: bash deploy/install_auto_update_cron.sh'
fi

BACKUP_DIR="$BACKUP_ROOT/$(basename "$APP_DIR")"
if [ -d "$BACKUP_DIR" ]; then
  latest="$(find "$BACKUP_DIR" \( -name 'liftcore-*.db' -o -name 'liftcore-*.dump' \) -type f 2>/dev/null | sort | tail -n1)"
  if [ -n "$latest" ]; then
    ok "آخر نسخة: $latest"
  else
    warn "لا توجد نسخ في $BACKUP_DIR — شغّل: bash deploy/backup_daily.sh $APP_DIR"
  fi
else
  warn "مجلد النسخ غير موجود: $BACKUP_DIR"
fi

if [ -f "$PLATFORM_ENV" ]; then
  sentry_line=""
  if [ -r "$PLATFORM_ENV" ]; then
    sentry_line="$(grep -E '^SENTRY_DSN=' "$PLATFORM_ENV" 2>/dev/null | tail -n1 || true)"
  else
    sentry_line="$(sudo grep -E '^SENTRY_DSN=' "$PLATFORM_ENV" 2>/dev/null | tail -n1 || true)"
  fi
  sentry_val="$(printf '%s' "$sentry_line" | cut -d= -f2- | tr -d '\r' | sed 's/^["'\'']//;s/["'\'']$//')"
  if [ -n "$sentry_val" ] && [ "$sentry_val" != "https://examplePublicKey@o0.ingest.sentry.io/0" ]; then
    ok 'SENTRY_DSN مضبوط في platform.env'
  else
    warn 'SENTRY_DSN غير مضبوط — أضفه إلى /etc/liftcore/platform.env ثم restart liftcore'
  fi
else
  warn "platform.env غير موجود: $PLATFORM_ENV"
fi

if [ -f "$HOME/liftcore/logs/backup.log" ]; then
  echo "  backup.log (آخر 3 أسطر):"
  tail -n 3 "$HOME/liftcore/logs/backup.log" | sed 's/^/    /'
fi

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "==> ops check FAILED ($FAIL fail, $WARN warn)"
  exit 1
fi
if [ "$WARN" -gt 0 ]; then
  echo "==> ops check OK with $WARN warning(s)"
  exit 0
fi
echo "==> ops check OK"
exit 0
