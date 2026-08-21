#!/usr/bin/env bash
# LiftCore — تصدير بيانات الإنتاج من GCP قبل النقل
# على سيرفر GCP:
#   cd ~/liftcore/elevator-app && bash deploy/hetzner/export_from_gcp.sh
#
# INCLUDE_PLATFORM_ENV=1  ينسخ الأسرار (مطلوب للنقل — لا ترفع الملف لـ git)
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
JAMA_APP="${JAMA_APP:-$HOME/liftcore/jama-elevator-app}"
INCLUDE_PLATFORM_ENV="${INCLUDE_PLATFORM_ENV:-1}"
TS="$(date +%Y%m%d-%H%M%S)"
DEST="${DEST:-$HOME/liftcore/migration-export-${TS}}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"

mkdir -p "$DEST"
cd "$APP_DIR"

_log() { echo "==> $*"; }

if [ -f "$PLATFORM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$PLATFORM_ENV"
  set +a
fi

_log "git"
{
  echo "path=$APP_DIR"
  echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  echo "commit=$(git rev-parse HEAD 2>/dev/null || echo '?')"
  git status -sb 2>/dev/null || true
} >"$DEST/git.txt"

_log "systemd / nginx (مرجع)"
systemctl cat liftcore >"$DEST/liftcore.service.txt" 2>/dev/null || true
sudo nginx -T >"$DEST/nginx-full.txt" 2>/dev/null || true

_log "قاعدة البيانات"
FOUND_DB=0
if [ -n "${DATABASE_URL:-}" ] && echo "$DATABASE_URL" | grep -qi postgres; then
  DEST="$DEST" DATABASE_URL="$DATABASE_URL" python3 - <<'PY'
import os, subprocess, sys
from urllib.parse import urlparse, unquote
url = os.environ['DATABASE_URL']
for old, new in (
    ('postgresql+psycopg2://', 'postgresql://'),
    ('postgresql+psycopg://', 'postgresql://'),
):
    url = url.replace(old, new)
u = urlparse(url)
dest = os.path.join(os.environ['DEST'], 'liftcore.dump')
env = os.environ.copy()
env['PGPASSWORD'] = unquote(u.password or env.get('PGPASSWORD', ''))
cmd = [
    'pg_dump', '-Fc',
    '-h', u.hostname or '127.0.0.1',
    '-p', str(u.port or 5432),
    '-U', unquote(u.username or 'liftcore'),
    '-d', (u.path or '/liftcore').lstrip('/'),
    '-f', dest,
]
subprocess.check_call(cmd, env=env)
print('pg_dump ok', dest, file=sys.stderr)
PY
  echo "kind=postgres" >"$DEST/db-kind.txt"
  FOUND_DB=1
  _log "pg_dump → liftcore.dump"
fi
for db in \
  "$APP_DIR/instance/liftcore.db" \
  "$APP_DIR/liftcore.db" \
  "$JAMA_APP/instance/jama.db" \
  "$JAMA_APP/instance/liftcore.db"; do
  if [ -f "$db" ]; then
    cp -a "$db" "$DEST/$(basename "$(dirname "$db")")-$(basename "$db")"
    _log "sqlite: $db"
    if [ "$FOUND_DB" -eq 0 ]; then
      echo "kind=sqlite" >"$DEST/db-kind.txt"
    fi
    FOUND_DB=1
  fi
done
if [ "$FOUND_DB" -eq 0 ]; then
  echo "ERROR: لم تُوجد قاعدة بيانات" >&2
  exit 1
fi

_tar_dir() {
  local src="$1"
  local name="$2"
  if [ -d "$src" ]; then
    tar -czf "$DEST/$name" -C "$(dirname "$src")" "$(basename "$src")"
    _log "archive: $name"
  fi
}

_tar_dir "$APP_DIR/static/uploads" "uploads-main.tar.gz"
_tar_dir "$APP_DIR/uploads" "uploads-root.tar.gz"
_tar_dir "$JAMA_APP/static/uploads" "uploads-jama.tar.gz"

if [ "$INCLUDE_PLATFORM_ENV" = "1" ] && [ -f "$PLATFORM_ENV" ]; then
  sudo cp "$PLATFORM_ENV" "$DEST/platform.env"
  sudo chown "$USER:$USER" "$DEST/platform.env"
  chmod 600 "$DEST/platform.env"
  _log "platform.env (أسرار — لا ترفعه لـ GitHub)"
fi

BUNDLE="${DEST}.tar.gz"
tar -czf "$BUNDLE" -C "$(dirname "$DEST")" "$(basename "$DEST")"
chmod 600 "$BUNDLE"

echo ""
echo "=============================================="
echo "  حزمة النقل: $BUNDLE"
echo "  الحجم: $(du -h "$BUNDLE" | awk '{print $1}')"
echo ""
echo "  انقلها للسيرفر الجديد (من جهازك أو من GCP):"
echo "    scp $BUNDLE ${APP_USER:-info}@NEW_IP:/home/${APP_USER:-info}/"
echo "=============================================="
