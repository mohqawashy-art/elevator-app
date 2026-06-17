#!/usr/bin/env bash
# LiftCore — تحديث تلقائي من GitHub (يُشغَّل عبر cron كل 5 دقائق)
#   bash deploy/auto_update.sh
#   bash deploy/auto_update.sh --force   # تحديث حتى لو لا يوجد commit جديد

set -euo pipefail

FORCE=0
if [ "${1:-}" = "--force" ]; then FORCE=1; fi

LOG_DIR="${HOME}/liftcore/logs"
LOG_FILE="${LOG_DIR}/auto_update.log"
LOCK_FILE="/tmp/liftcore-auto-update.lock"
mkdir -p "$LOG_DIR"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"
}

if ! command -v flock >/dev/null 2>&1; then
  log "ERROR: flock not found — install util-linux"
  exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "skip: update already running"
  exit 0
fi

update_app() {
  local service="$1"
  local app_dir="$2"

  if [ ! -d "$app_dir/.git" ]; then
    log "skip $service: no git repo at $app_dir"
    return 0
  fi

  cd "$app_dir"

  if ! git fetch origin main -q 2>>"$LOG_FILE"; then
    log "ERROR $service: git fetch failed"
    return 1
  fi

  local local_rev remote_rev
  local_rev="$(git rev-parse HEAD)"
  remote_rev="$(git rev-parse origin/main)"

  if [ "$FORCE" = 0 ] && [ "$local_rev" = "$remote_rev" ]; then
    log "ok $service: up to date (${local_rev:0:7})"
    return 0
  fi

  log "update $service: ${local_rev:0:7} -> ${remote_rev:0:7}"
  export SERVICE_NAME="$service"
  export APP_DIR="$app_dir"

  if bash "$app_dir/deploy/gcp_update.sh" >>"$LOG_FILE" 2>&1; then
    log "done $service"
    if [ "$service" = "liftcore-jama" ] && [ -f "$app_dir/deploy/fix_jama_maps.sh" ]; then
      bash "$app_dir/deploy/fix_jama_maps.sh" >>"$LOG_FILE" 2>&1 || log "WARN $service: fix_jama_maps failed"
    fi
  else
    log "ERROR $service: gcp_update.sh failed — see log above"
    return 1
  fi
}

log "==> auto update start (force=$FORCE)"
ERR=0
update_app liftcore "$HOME/liftcore/elevator-app" || ERR=1
update_app liftcore-jama "$HOME/liftcore/jama-elevator-app" || ERR=1
log "==> auto update end (exit=$ERR)"
exit "$ERR"
