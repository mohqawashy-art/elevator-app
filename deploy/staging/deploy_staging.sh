#!/usr/bin/env bash
# نشر فرع التجربة فقط. لا يلمس checkout أو خدمة أو قاعدة الإنتاج.
set -euo pipefail

BRANCH="staging/department-hubs"
REPO_URL="${REPO_URL:-https://github.com/mohqawashy-art/elevator-app.git}"
ROOT="/opt/liftcore-staging"
MIRROR="$ROOT/repository.git"
RELEASES="$ROOT/releases"
CURRENT="$ROOT/current"
VENV="$ROOT/venv"
STATE="/var/lib/liftcore-staging"
BACKUPS="/var/backups/liftcore-staging"
ENV_FILE="/etc/liftcore/staging.env"
SERVICE="liftcore-staging"
LOCK="/var/lock/liftcore-staging-deploy.lock"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run with sudo"
  exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: missing $ENV_FILE"
  exit 1
fi

exec 9>"$LOCK"
flock -n 9 || { echo "ERROR: another staging deploy is running"; exit 1; }

mkdir -p "$ROOT" "$RELEASES" "$STATE/uploads" "$STATE/instance" "$BACKUPS"
if [ ! -d "$MIRROR" ]; then
  git clone --mirror "$REPO_URL" "$MIRROR"
fi

git --git-dir="$MIRROR" fetch --prune origin \
  "+refs/heads/$BRANCH:refs/heads/$BRANCH"
SHA="$(git --git-dir="$MIRROR" rev-parse "$BRANCH")"
SHORT_SHA="${SHA:0:12}"
RELEASE="$RELEASES/$(date +%Y%m%d%H%M%S)-$SHORT_SHA"
PREVIOUS="$(readlink -f "$CURRENT" 2>/dev/null || true)"

echo "==> staging release $SHORT_SHA"
mkdir -p "$RELEASE"
git --git-dir="$MIRROR" archive "$SHA" | tar -x -C "$RELEASE"

rm -rf "$RELEASE/static/uploads" "$RELEASE/instance"
ln -s "$STATE/uploads" "$RELEASE/static/uploads"
ln -s "$STATE/instance" "$RELEASE/instance"

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/pip" install -r "$RELEASE/requirements.txt"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
export LIFTCORE_ENV_FILE="$ENV_FILE"
export LIFTCORE_ALEMBIC=1

BACKUP="$BACKUPS/pre-${SHORT_SHA}-$(date +%Y%m%d%H%M%S).dump"
PGPASSWORD="${PGPASSWORD:?PGPASSWORD missing}" pg_dump \
  --host="${PGHOST:-127.0.0.1}" --port="${PGPORT:-5432}" \
  --username="${PGUSER:?PGUSER missing}" --dbname="${PGDATABASE:?PGDATABASE missing}" \
  --format=custom --file="$BACKUP"

cd "$RELEASE"
"$VENV/bin/python" deploy/migrate_db.py
if [ -f scripts/init_install_module.py ]; then
  "$VENV/bin/python" scripts/init_install_module.py
fi
if [ -f "$SCRIPT_DIR/seed_staging.py" ]; then
  "$VENV/bin/python" "$SCRIPT_DIR/seed_staging.py"
fi

ln -sfn "$RELEASE" "$CURRENT"
chown -h liftcore-staging:liftcore-staging "$CURRENT"
chown -R liftcore-staging:liftcore-staging "$RELEASE" "$STATE" "$BACKUPS"

systemctl restart "$SERVICE"
for _ in $(seq 1 20); do
  if curl --fail --silent --max-time 3 \
    -H "Host: test.liftcoreapp.com" http://127.0.0.1:5003/api/health >/dev/null; then
    echo "==> staging healthy: $SHORT_SHA"
    printf '%s\n' "$SHA" >"$STATE/deployed_commit"
    exit 0
  fi
  sleep 2
done

echo "ERROR: staging health check failed"
if [ -n "$PREVIOUS" ] && [ -d "$PREVIOUS" ]; then
  ln -sfn "$PREVIOUS" "$CURRENT"
  systemctl restart "$SERVICE" || true
  echo "Rolled application symlink back to $PREVIOUS"
fi
echo "Database backup: $BACKUP"
exit 1
