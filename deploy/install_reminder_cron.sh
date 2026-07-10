#!/usr/bin/env bash
# cron يومي 08:00 — تذكيرات العقود (روابط wa.me في السجل)
set -euo pipefail

APP_DIR="${1:-$HOME/liftcore/elevator-app}"
MARKER="# liftcore-contract-reminders"
LOG_DIR="$HOME/liftcore/logs"
CRON_LINE="0 8 * * * cd $APP_DIR && set -a && [ -f /etc/liftcore/platform.env ] && . /etc/liftcore/platform.env; set +a; python3 scripts/send_contract_reminders.py --days-ahead 3 >> $LOG_DIR/reminders.log 2>&1 $MARKER"

mkdir -p "$LOG_DIR"
chmod +x "$APP_DIR/scripts/send_contract_reminders.py" 2>/dev/null || true

if crontab -l 2>/dev/null | grep -q "$MARKER"; then
  crontab -l 2>/dev/null | grep -v "$MARKER" | crontab -
fi
( crontab -l 2>/dev/null || true; echo "$CRON_LINE" ) | crontab -

echo "==> contract reminder cron installed (08:00 daily, +3 days ahead)"
echo "    log: $LOG_DIR/reminders.log"
echo "    test: cd $APP_DIR && python3 scripts/send_contract_reminders.py --days-ahead 3"
