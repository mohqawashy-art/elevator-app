#!/usr/bin/env python3
"""حذف زيارات الصيانة المكررة (نفس المصعد والتاريخ والنوع).

الاستخدام:
  export DATABASE_URL="sqlite:////path/to/jama.db"
  python scripts/remove_duplicate_maintenance_visits.py --dry-run
  python scripts/remove_duplicate_maintenance_visits.py
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402
from visit_cleanup import remove_duplicate_visits  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Remove duplicate maintenance visits')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    with app.app_context():
        result = remove_duplicate_visits(dry_run=args.dry_run)
        if args.dry_run:
            print(f'Would delete {result["found"]} duplicate visit(s): {result["ids"]}')
        else:
            print(f'Deleted {result["deleted"]} duplicate visit(s): {result["ids"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
