#!/usr/bin/env python3
"""إلغاء خطة صيانة شهرية (حذف الزيارات المجدولة/المُرسلة)."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402
from operations import cancel_monthly_plan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Cancel a monthly maintenance plan')
    parser.add_argument(
        'plan_month',
        nargs='?',
        default='2026-07',
        help='Plan month YYYY-MM (default: 2026-07)',
    )
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    args = parser.parse_args()

    with app.app_context():
        result = cancel_monthly_plan(args.plan_month, dry_run=args.dry_run)
        print(f"Plan month: {result['plan_month']}")
        if args.dry_run:
            print(f"Would delete: {result['deleted']}")
        else:
            print(f"Deleted: {result['deleted']}")
        print(f"Kept (completed/other): {result.get('kept_completed', 0)}")
        if not args.dry_run and 'total' in result:
            print(f"Remaining in plan view: {result['total']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
