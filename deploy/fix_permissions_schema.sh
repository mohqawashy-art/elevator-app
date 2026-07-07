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
    from models import Settings
    s = Settings.query.first()
    if s and getattr(s, 'custom_permissions_enabled', False):
        print('==> disabling custom_permissions_enabled (safe default)')
        s.custom_permissions_enabled = False
        db.session.commit()
PY
sudo systemctl restart liftcore
echo "==> done — open /settings?tab=users"
