#!/usr/bin/env bash
# cron كل ساعتين — pg_dump على نفس السيرفر (بدون snapshot Hetzner)
set -euo pipefail

APP_DIR="${1:-${APP_DIR:-/home/info/liftcore/elevator-app}}"
if [ ! -d "$APP_DIR" ]; then
  APP_DIR="${1:-$HOME/liftcore/elevator-app}"
fi
MARKER="# liftcore-daily-backup"
LOG="${BACKUP_LOG:-/home/info/liftcore/logs/backup.log}"
BACKUP_ROOT="${BACKUP_ROOT:-/home/info/liftcore/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

mkdir -p "$(dirname "$LOG")" "$BACKUP_ROOT"
chmod +x "$APP_DIR/deploy/backup_daily.sh"

CRON_LINE="0 */2 * * * BACKUP_ROOT=$BACKUP_ROOT BACKUP_RETENTION_DAYS=$RETENTION_DAYS bash $APP_DIR/deploy/backup_daily.sh $APP_DIR >> $LOG 2>&1 $MARKER"

remove_marker_from() {
  local user="${1:-}"
  local tmp
  tmp="$(mktemp)"
  if [ -n "$user" ]; then
    crontab -u "$user" -l 2>/dev/null | grep -v "$MARKER" >"$tmp" || true
    if [ -s "$tmp" ]; then
      crontab -u "$user" "$tmp"
    else
      crontab -u "$user" -r 2>/dev/null || true
    fi
  else
    crontab -l 2>/dev/null | grep -v "$MARKER" >"$tmp" || true
    if [ -s "$tmp" ]; then
      crontab "$tmp"
    else
      crontab -r 2>/dev/null || true
    fi
  fi
  rm -f "$tmp"
}

add_marker_to() {
  local user="${1:-}"
  local tmp
  tmp="$(mktemp)"
  if [ -n "$user" ]; then
    crontab -u "$user" -l 2>/dev/null | grep -v "$MARKER" >"$tmp" || true
    echo "$CRON_LINE" >>"$tmp"
    crontab -u "$user" "$tmp"
  else
    crontab -l 2>/dev/null | grep -v "$MARKER" >"$tmp" || true
    echo "$CRON_LINE" >>"$tmp"
    crontab "$tmp"
  fi
  rm -f "$tmp"
}

if [ "$(id -u)" = "0" ]; then
  remove_marker_from info
  add_marker_to
else
  add_marker_to
fi

echo "==> backup cron installed (every 2 hours)"
echo "    log: $LOG"
echo "    dest: $BACKUP_ROOT"
echo "    keep: ${RETENTION_DAYS} days"
echo "    test now: bash $APP_DIR/deploy/backup_daily.sh $APP_DIR"
