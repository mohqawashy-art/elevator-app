#!/usr/bin/env bash
# استعادة كاملة لبيئة الاختبار فقط — قاعدة + كود + واجهات (أواخر أغسطس قبل نسخ جما).
# لا يلمس الإنتاج (liftcore / jama / app).
set -euo pipefail

BACKUP="${1:-/var/backups/liftcore-staging/pre-f9e4516ba726-20260830211651.dump}"
RELEASE_DIR="${2:-/opt/liftcore-staging/releases/20260830211647-f9e4516ba726}"
ENV_FILE="/etc/liftcore/staging.env"
SERVICE="liftcore-staging"
CURRENT="/opt/liftcore-staging/current"
VENV="/opt/liftcore-staging/venv/bin/python"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run with sudo"
  exit 1
fi
if [ ! -f "$BACKUP" ]; then
  echo "ERROR: backup not found: $BACKUP"
  exit 1
fi
if [ ! -d "$RELEASE_DIR" ]; then
  echo "ERROR: release not found: $RELEASE_DIR"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "==> TEST ONLY: restore DB from $(basename "$BACKUP")"
echo "==> TEST ONLY: activate code $(basename "$RELEASE_DIR")"
systemctl stop "$SERVICE"

sudo -u postgres psql -v ON_ERROR_STOP=1 -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PGDATABASE}' AND pid <> pg_backend_pid();" || true
sudo -u postgres dropdb --if-exists "$PGDATABASE"
sudo -u postgres createdb --owner="$PGUSER" "$PGDATABASE"
sudo -u postgres pg_restore -d "$PGDATABASE" --no-owner --role="$PGUSER" "$BACKUP"

ln -sfn "$RELEASE_DIR" "$CURRENT"
chown -h liftcore-staging:liftcore-staging "$CURRENT"

echo "==> migrate (staging DB only)"
sudo -u liftcore-staging env \
  DATABASE_URL="$DATABASE_URL" \
  LIFTCORE_ENV_FILE="$ENV_FILE" \
  LIFTCORE_ALEMBIC=1 \
  bash -lc "cd '$RELEASE_DIR' && '$VENV' deploy/migrate_db.py"

if [ -f "$RELEASE_DIR/scripts/init_install_module.py" ]; then
  sudo -u liftcore-staging env \
    DATABASE_URL="$DATABASE_URL" \
    LIFTCORE_ENV_FILE="$ENV_FILE" \
    bash -lc "cd '$RELEASE_DIR' && '$VENV' scripts/init_install_module.py"
fi

if [ -f "$RELEASE_DIR/deploy/staging/seed_staging.py" ]; then
  sudo -u liftcore-staging env \
    DATABASE_URL="$DATABASE_URL" \
    LIFTCORE_ENV_FILE="$ENV_FILE" \
    bash -lc "cd '$RELEASE_DIR' && '$VENV' deploy/staging/seed_staging.py"
fi

echo "==> set staging login"
if [ -f "$RELEASE_DIR/scripts/set_user_login.py" ]; then
  sudo -u liftcore-staging env \
    DATABASE_URL="$DATABASE_URL" \
    LIFTCORE_ENV_FILE="$ENV_FILE" \
    bash -lc "cd '$RELEASE_DIR' && '$VENV' scripts/set_user_login.py \
    --username mohammed \
    --full-name 'محمد عبدالعزيز' \
    --email mohammed@test.local \
    --password 'Bf@123456' \
    --org-slug test \
    --apply"
else
  sudo -u liftcore-staging env \
    DATABASE_URL="$DATABASE_URL" \
    LIFTCORE_ENV_FILE="$ENV_FILE" \
    RELEASE_DIR="$RELEASE_DIR" \
    bash -lc "cd '$RELEASE_DIR' && '$VENV' -" <<'PY'
import os, sys
sys.path.insert(0, os.environ.get('RELEASE_DIR', '.'))
release = os.environ['RELEASE_DIR']
sys.path.insert(0, release)
os.chdir(release)
from app import app, db, hash_password, verify_password
from models import Organization, User, RateLimitEvent
with app.app_context():
    RateLimitEvent.query.filter_by(scope='login').delete(synchronize_session=False)
    org = Organization.query.filter_by(slug='test').first()
    pwd = 'Bf@123456'
    h = hash_password(pwd)
    user = User.query.filter_by(organization_id=org.id, username='mohammed').first()
    if not user:
        user = User.query.filter(User.organization_id == org.id, User.full_name == 'محمد عبدالعزيز').first()
    if not user:
        user = User(organization_id=org.id, username='mohammed', full_name='محمد عبدالعزيز', email='mohammed@test.local', role='admin', is_active=True)
        db.session.add(user)
    user.username = 'mohammed'
    user.full_name = 'محمد عبدالعزيز'
    user.password_hash = h
    user.is_active = True
    user.role = 'admin'
    db.session.commit()
    print('login_ok', verify_password(user.password_hash, pwd))
PY
fi

systemctl start "$SERVICE"
for _ in $(seq 1 20); do
  if curl --fail --silent --max-time 3 \
    -H "Host: test.liftcoreapp.com" http://127.0.0.1:5003/api/health >/dev/null; then
    echo "==> staging restored: code=$(basename "$RELEASE_DIR")"
    basename "$RELEASE_DIR" | sed 's/.*-//' > /var/lib/liftcore-staging/deployed_commit
    sudo -u postgres psql -d "$PGDATABASE" -tAc \
      "SELECT 'org='||slug||' customers='||(SELECT count(*) FROM customers)||' contracts='||(SELECT count(*) FROM contracts) FROM organizations WHERE slug='test';"
    exit 0
  fi
  sleep 2
done

echo "ERROR: staging health check failed"
exit 1
