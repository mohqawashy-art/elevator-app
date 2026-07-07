#!/usr/bin/env bash
# LiftCore — نقطة حفظ كاملة قبل تحويل Multi-Tenant (رجوع آمن)
#
# شغّل على السيرفر (GCP SSH):
#   cd ~/liftcore/elevator-app && bash deploy/checkpoint_pre_multitenant.sh
#
# متغيرات:
#   CHECKPOINT_ROOT=~/liftcore/checkpoints   مجلد الحفظ
#   LABEL=before-dns                         وسم اختياري في اسم المجلد
#   INCLUDE_PLATFORM_ENV=1                   نسخ /etc/liftcore/platform.env (يحتوي أسراراً)
#
# استعادة: bash deploy/restore_checkpoint.sh ~/liftcore/checkpoints/pre-multitenant-YYYYMMDD-HHMMSS

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAIN_APP="${MAIN_APP:-$HOME/liftcore/elevator-app}"
JAMA_APP="${JAMA_APP:-$HOME/liftcore/jama-elevator-app}"
CHECKPOINT_ROOT="${CHECKPOINT_ROOT:-$HOME/liftcore/checkpoints}"
TS="$(date +%Y%m%d-%H%M%S)"
LABEL="${LABEL:-}"
INCLUDE_PLATFORM_ENV="${INCLUDE_PLATFORM_ENV:-1}"

if [ -n "$LABEL" ]; then
  DEST="$CHECKPOINT_ROOT/pre-multitenant-${TS}-${LABEL}"
else
  DEST="$CHECKPOINT_ROOT/pre-multitenant-${TS}"
fi

mkdir -p "$DEST"

_log() { echo "==> $*"; }

_copy_db() {
  local app_dir="$1"
  local name="$2"
  local found=0
  for db in "$app_dir/instance/liftcore.db" "$app_dir/instance/jama.db" "$app_dir/liftcore.db" "$app_dir/jama.db"; do
    if [ -f "$db" ]; then
      cp "$db" "$DEST/${name}-$(basename "$db")"
      _log "DB: $db → $DEST/${name}-$(basename "$db")"
      found=1
      break
    fi
  done
  if [ "$found" -eq 0 ]; then
    echo "  WARN: no .db under $app_dir"
  fi
}

_tar_uploads() {
  local app_dir="$1"
  local archive="$2"
  if [ -d "$app_dir/static/uploads" ]; then
    tar -czf "$DEST/$archive" -C "$app_dir/static" uploads
    _log "uploads: $app_dir/static/uploads → $DEST/$archive"
  else
    echo "  WARN: no uploads at $app_dir/static/uploads"
  fi
}

_git_info() {
  local app_dir="$1"
  local out="$2"
  if [ -d "$app_dir/.git" ]; then
    (
      cd "$app_dir"
      echo "path=$app_dir"
      echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
      echo "commit=$(git rev-parse HEAD 2>/dev/null || echo '?')"
      echo "describe=$(git describe --tags --always 2>/dev/null || true)"
      git status -sb 2>/dev/null || true
    ) >"$DEST/$out"
    _log "git: $out"
  fi
}

_log "LiftCore checkpoint → $DEST"
mkdir -p "$CHECKPOINT_ROOT"

# --- تطبيقات ---
if [ -d "$MAIN_APP" ]; then
  _copy_db "$MAIN_APP" "main"
  _tar_uploads "$MAIN_APP" "uploads-main.tar.gz"
  _git_info "$MAIN_APP" "git-main.txt"
else
  echo "WARN: MAIN_APP not found: $MAIN_APP"
fi

if [ -d "$JAMA_APP" ]; then
  _copy_db "$JAMA_APP" "jama"
  _tar_uploads "$JAMA_APP" "uploads-jama.tar.gz"
  _git_info "$JAMA_APP" "git-jama.txt"
else
  echo "WARN: JAMA_APP not found: $JAMA_APP"
fi

# --- systemd ---
for unit in liftcore liftcore-jama; do
  if [ -f "/etc/systemd/system/${unit}.service" ]; then
    if cp "/etc/systemd/system/${unit}.service" "$DEST/${unit}.service" 2>/dev/null; then
      _log "systemd: ${unit}.service"
    elif sudo cp "/etc/systemd/system/${unit}.service" "$DEST/${unit}.service"; then
      _log "systemd: ${unit}.service (sudo)"
    fi
  fi
done

# --- nginx ---
NGINX_COPIED=0
for pattern in liftcore jama liftcoreapp; do
  for f in /etc/nginx/sites-available/*"$pattern"* /etc/nginx/sites-enabled/*"$pattern"*; do
    [ -f "$f" ] || continue
    base="$(basename "$f")"
    if cp "$f" "$DEST/nginx-${base}" 2>/dev/null || sudo cp "$f" "$DEST/nginx-${base}"; then
      _log "nginx: $f"
      NGINX_COPIED=1
    fi
  done
done
[ "$NGINX_COPIED" -eq 1 ] || echo "  WARN: no nginx site files matched"

# --- platform.env (أسرار — لا ترفع لـ git) ---
if [ "$INCLUDE_PLATFORM_ENV" = "1" ] && [ -f /etc/liftcore/platform.env ]; then
  if cp /etc/liftcore/platform.env "$DEST/platform.env" 2>/dev/null || \
     sudo cp /etc/liftcore/platform.env "$DEST/platform.env"; then
    chmod 600 "$DEST/platform.env" 2>/dev/null || true
    _log "platform.env (chmod 600) — احفظ نسخة خارج السيرفر في مكان آمن"
  fi
fi

# --- manifest ---
cat >"$DEST/MANIFEST.txt" <<EOF
LiftCore pre-Multi-Tenant checkpoint
Created: $(date -Iseconds 2>/dev/null || date)
Host: $(hostname 2>/dev/null || echo unknown)
User: $(whoami)
Destination: $DEST

Restore database (example jama):
  sudo systemctl stop liftcore-jama
  cp $DEST/jama-jama.db $JAMA_APP/instance/jama.db
  sudo systemctl start liftcore-jama

Restore uploads (example main):
  tar -xzf $DEST/uploads-main.tar.gz -C $MAIN_APP/static

Full restore script:
  bash $MAIN_APP/deploy/restore_checkpoint.sh $DEST

GCP: أنشئ Disk Snapshot من Console باسم liftcore-pre-multitenant-${TS}
Git tag (محلياً): git tag -a pre-multitenant-${TS} && git push origin pre-multitenant-${TS}
EOF

_log "MANIFEST: $DEST/MANIFEST.txt"
echo ""
echo "=============================================="
echo "  تم الحفظ: $DEST"
echo "  الخطوة التالية (موصى بها):"
echo "    1) GCP Console → Disk → Create snapshot"
echo "    2) git tag pre-multitenant-${TS} على جهازك"
echo "  استعادة:"
echo "    bash deploy/restore_checkpoint.sh $DEST"
echo "=============================================="
