#!/usr/bin/env bash
# إصلاح أعمدة الصلاحيات الاختيارية على السيرفر (مرة واحدة عند 500 على /settings?tab=users)
set -euo pipefail
APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
VENV="${VENV:-$HOME/liftcore/venv}"
cd "$APP_DIR"
source "$VENV/bin/activate"
python3 << 'PY'
from app import app, db
from liftcore_permissions import ensure_permissions_schema
with app.app_context():
    if ensure_permissions_schema(db.session, db.engine):
        print('==> added missing permission columns')
    else:
        print('==> permission columns already present')
PY
sudo systemctl restart liftcore
echo "==> done — open /settings?tab=users"
