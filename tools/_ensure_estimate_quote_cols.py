#!/usr/bin/env python3
"""Ensure elevator_estimates.result_* columns exist (Postgres/SQLite)."""
from __future__ import annotations

import os
import sys

# Run from repo root with app venv so DATABASE_URL / .env are available.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text


def main() -> int:
    from app import app
    from models import db

    with app.app_context():
        insp = inspect(db.engine)
        if 'elevator_estimates' not in insp.get_table_names():
            print('elevator_estimates missing')
            return 1
        cols = {c['name'] for c in insp.get_columns('elevator_estimates')}
        added = []
        for col in ('result_project_id', 'result_quotation_id'):
            if col in cols:
                continue
            db.session.execute(text(f'ALTER TABLE elevator_estimates ADD COLUMN {col} INTEGER'))
            db.session.commit()
            added.append(col)
        print('ok added=', added or 'none')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
