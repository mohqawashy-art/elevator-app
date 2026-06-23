#!/usr/bin/env python3
"""
إفراغ قاعدة جما وتحميل سيناريو 10 عملاء (تجربة كاملة للبرنامج).

محلياً:
  python scripts/reset_jama_demo.py

على سيرفر جما:
  cd ~/liftcore/jama-elevator-app
  bash deploy/reset_jama_demo.sh
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DEFAULT_JAMA_DBS = (
    os.path.expanduser('~/liftcore/jama-elevator-app/instance/jama.db'),
    os.path.expanduser('~/jama-elevator-app/instance/jama.db'),
)


def _resolve_database_url() -> str:
    explicit = (os.environ.get('DATABASE_URL') or '').strip()
    if explicit:
        return explicit
    for path in DEFAULT_JAMA_DBS:
        if os.path.isfile(path):
            abs_path = os.path.abspath(path).replace('\\', '/')
            return f'sqlite:////{abs_path}'
    return ''


def verify_credentials() -> bool:
    from app import app, db, verify_password
    from field_auth import find_technician_by_login, verify_technician_pin, technician_has_field_pin
    from models import User, Customer

    ok = True
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        admin_ok = bool(admin and verify_password(admin.password_hash, 'admin123') and admin.is_active)
        print(f'  admin / admin123 ........... {"OK" if admin_ok else "FAIL"}')
        ok = ok and admin_ok

        tech = find_technician_by_login('Tech-001')
        tech_ok = bool(
            tech
            and technician_has_field_pin(tech)
            and verify_technician_pin(tech, '123456')
        )
        print(f'  Tech-001 / 123456 .......... {"OK" if tech_ok else "FAIL"}')
        ok = ok and tech_ok

        customers = Customer.query.count()
        print(f'  عملاء في القاعدة .......... {customers}')
        ok = ok and customers >= 10

        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print(f'  قاعدة البيانات ............. {db_uri}')
    return ok


def main() -> int:
    db_url = _resolve_database_url()
    if db_url:
        os.environ['DATABASE_URL'] = db_url
        print(f'DATABASE_URL = {db_url}')
    else:
        print('تحذير: DATABASE_URL غير مضبوط — سيُستخدم مسار التطبيق الافتراضي')
        print('  على سيرفر جما استخدم: bash deploy/reset_jama_demo.sh')

    from seed_data import reset_jama_demo

    try:
        if not reset_jama_demo():
            return 1
        print('')
        print('==> التحقق من الأكواد:')
        if not verify_credentials():
            print('')
            print('فشل التحقق — راجع مسار قاعدة البيانات أو أعد تشغيل الخدمة')
            return 1
        return 0
    except Exception as exc:
        print(f'فشل: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
