#!/usr/bin/env python3
"""استيراد بيان تركيب قطع الغيار من Excel إلى jama.db.

الاستخدام:
  export DATABASE_URL="sqlite:////path/to/jama.db"
  python scripts/import_parts_billing_xlsx.py deploy/data/jama_parts_billing_14_6_2026.xlsx --dry-run
  python scripts/import_parts_billing_xlsx.py deploy/data/jama_parts_billing_14_6_2026.xlsx

أو:
  bash deploy/import_jama_parts_billing.sh
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402
from parts_billing_import import import_parts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Import parts billing from Excel')
    parser.add_argument('xlsx', help='Path to Excel file')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--force', action='store_true', help='Import even if operation number exists')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    with app.app_context():
        result = import_parts(
            args.xlsx,
            dry_run=args.dry_run,
            skip_existing=not args.force,
        )
        print(f"Rows in file: {result['rows']}")
        if args.dry_run:
            print(f"Dry run: would import {result['imported']}")
        else:
            print(f"Imported: {result['imported']}")
        print(f"Skipped (existing): {result['skipped_existing']}")
        print(f"Skipped (missing contract): {result['skipped_missing']}")
        print(f"Errors: {result['errors']}")
        if result.get('missing_samples'):
            print('Missing samples:')
            for line in result['missing_samples']:
                print(' ', line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
