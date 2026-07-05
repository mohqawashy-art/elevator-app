#!/usr/bin/env bash
# cron يومي 02:30 — نسخ احتياطي
set -euo pipefail

APP_DIR="${1:-$HOME/liftcore/elevator-app}"
MARKER="# liftcore-daily-backup"
CRON_LINE="30 2 * * * bash $APP_DIR/deploy/backup_daily.sh $APP_DIR >> $HOME/liftcore/logs/backup.log 2>&1 $MARKER"

mkdir -p "$HOME/liftcore/logs"
chmod +x "$APP_DIR/deploy/backup_daily.sh"

if crontab -l 2>/dev/null | grep -q "$MARKER"; then
  crontab -l 2>/dev/null | grep -v "$MARKER" | crontab -
fi
( crontab -l 2>/dev/null || true; echo "$CRON_LINE" ) | crontab -

echo "==> backup cron installed (02:30 daily)"
echo "    log: ~/liftcore/logs/backup.log"
echo "    test now: bash $APP_DIR/deploy/backup_daily.sh $APP_DIR"
