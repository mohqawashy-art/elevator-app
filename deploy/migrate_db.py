#!/usr/bin/env python3
"""تشغيل ترقيات Alembic — نشر وبيئة جديدة (G6).

  python deploy/migrate_db.py

قواعد موجودة (من create_all سابقاً): stamp head بدون إعادة إنشاء الجداول.
قواعد جديدة: flask db upgrade.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('LIFTCORE_ALEMBIC', '1')


def main() -> int:
    from sqlalchemy import inspect
    from flask_migrate import current, stamp, upgrade

    from app import app, db
    from liftcore_database import is_postgresql, normalize_database_url

    with app.app_context():
        uri = normalize_database_url(app.config.get('SQLALCHEMY_DATABASE_URI', ''))
        tables = set(inspect(db.engine).get_table_names())
        has_app_tables = bool(tables & {'users', 'customers', 'settings'})
        has_alembic = 'alembic_version' in tables
        pg = is_postgresql(uri)
        force = os.environ.get('LIFTCORE_FORCE_UPGRADE', '').strip().lower() in (
            '1', 'true', 'yes',
        )

        if force or pg:
            print('[migrate] running flask db upgrade (postgresql)')
            upgrade()
            print(f'[migrate] revision: {current() or "head"}')
            return 0

        if not has_alembic and has_app_tables:
            print('[migrate] existing sqlite database — stamping Alembic head')
            stamp(revision='head')
            print(f'[migrate] revision: {current() or "head"}')
            return 0

        print('[migrate] running flask db upgrade')
        upgrade()
        print(f'[migrate] revision: {current() or "head"}')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
