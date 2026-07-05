#!/usr/bin/env python3
"""إنشاء جداول legacy عبر create_all (لاختبارات Alembic stamp)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('LIFTCORE_ALEMBIC', '0')

from app import app, db  # noqa: E402


def main() -> int:
    with app.app_context():
        db.create_all()
    print('[bootstrap] legacy tables created')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
