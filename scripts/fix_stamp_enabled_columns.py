#!/usr/bin/env python3
"""إضافة أعمدة company_stamp_enabled / company_sign_enabled إن غابت."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text

from app import app, db


def main() -> int:
    with app.app_context():
        insp = inspect(db.engine)
        if 'settings' not in insp.get_table_names():
            print('settings table missing')
            return 1
        cols = {c['name'] for c in insp.get_columns('settings')}
        for col_name in ('company_stamp_enabled', 'company_sign_enabled'):
            if col_name in cols:
                print(f'[skip] {col_name}')
                continue
            db.session.execute(text(
                f'ALTER TABLE settings ADD COLUMN {col_name} BOOLEAN DEFAULT TRUE'
            ))
            db.session.commit()
            print(f'[ok] added {col_name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
