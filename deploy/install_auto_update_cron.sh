#!/usr/bin/env bash
# تفعيل التحديث التلقائي على السيرفر (مرة واحدة)
#   cd ~/liftcore/elevator-app && git pull --ff-only origin main
#   bash deploy/install_auto_update_cron.sh

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
INTERVAL="${AUTO_UPDATE_INTERVAL:-5}"

if [ ! -f "$APP_DIR/deploy/auto_update.sh" ]; then
  echo "ERROR: $APP_DIR/deploy/auto_update.sh not found"
  echo "Run: cd ~/liftcore/elevator-app && git pull --ff-only origin main"
  exit 1
fi

chmod +x "$APP_DIR/deploy/auto_update.sh"
mkdir -p "$HOME/liftcore/logs"

MARKER="# liftcore-auto-update"
CRON_CMD="$APP_DIR/deploy/auto_update.sh"
CRON_LINE="*/${INTERVAL} * * * * $CRON_CMD >> $HOME/liftcore/logs/auto_update.log 2>&1 $MARKER"

if crontab -l 2>/dev/null | grep -q "$MARKER"; then
  crontab -l 2>/dev/null | grep -v "$MARKER" | crontab -
fi

( crontab -l 2>/dev/null || true; echo "$CRON_LINE" ) | crontab -

echo "==> تم تفعيل التحديث التلقائي كل ${INTERVAL} دقائق"
echo "    السجل: ~/liftcore/logs/auto_update.log"
echo "    اختبار الآن: bash $APP_DIR/deploy/auto_update.sh"
echo ""
echo "    لإلغاء التفعيل:"
echo "    crontab -l | grep -v '$MARKER' | crontab -"
