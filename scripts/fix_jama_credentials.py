#!/usr/bin/env python3
"""إصلاح أكواد الدخول دون مسح البيانات — admin + رموز الفنيين."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.reset_jama_demo import _resolve_database_url, verify_credentials


def fix_credentials() -> None:
    from app import app, db, hash_password
    from models import User, Technician

    demo_pin = hash_password('123456')
    active = frozenset({'نشط', 'متاح', 'مشغول'})

    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                password_hash=hash_password('admin123'),
                full_name='مدير جما (تجريبي)',
                email='admin@jama.liftcore.sa',
                role='admin',
                is_active=True,
            )
            db.session.add(admin)
        else:
            admin.password_hash = hash_password('admin123')
            admin.is_active = True

        for tech in Technician.query.all():
            if (tech.status or 'متاح') in active:
                tech.sign_pin_hash = demo_pin

        db.session.commit()


def main() -> int:
    url = _resolve_database_url()
    if url:
        os.environ['DATABASE_URL'] = url
        print(f'DATABASE_URL = {url}')
    fix_credentials()
    print('==> تم ضبط الأكواد')
    return 0 if verify_credentials() else 1


if __name__ == '__main__':
    raise SystemExit(main())
