#!/usr/bin/env python3
"""استيراد بيان تركيب قطع الغيار من Excel إلى jama.db."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db  # noqa: E402
from models import PartsBilling  # noqa: E402
from parts_billing_import import import_parts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Import parts billing from Excel')
    parser.add_argument('xlsx', help='Path to Excel file')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--force', action='store_true', help='Import even if operation number exists')
    parser.add_argument(
        '--uncollected-only',
        action='store_true',
        help='Import only rows with status غير محصل',
    )
    parser.add_argument(
        '--replace',
        action='store_true',
        help='Delete all existing parts billing records before import',
    )
    parser.add_argument(
        '--force-uncollected',
        action='store_true',
        help='Import all rows as غير محصل regardless of Excel status',
    )
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    with app.app_context():
        if args.replace and not args.dry_run:
            deleted = PartsBilling.query.delete()
            db.session.commit()
            print(f'Cleared existing parts billing records: {deleted}')

        result = import_parts(
            args.xlsx,
            dry_run=args.dry_run,
            skip_existing=not args.force,
            uncollected_only=args.uncollected_only,
            force_uncollected=args.force_uncollected,
        )
        print(f"Rows in file: {result['rows']}")
        if args.dry_run:
            print(f"Dry run: would import {result['imported']}")
        else:
            print(f"Imported: {result['imported']}")
        print(f"Skipped (existing): {result['skipped_existing']}")
        print(f"Skipped (missing contract): {result['skipped_missing']}")
        print(f"Skipped (collected / محصل): {result.get('skipped_collected', 0)}")
        print(f"Errors: {result['errors']}")
        if result.get('missing_samples'):
            print('Missing samples:')
            for line in result['missing_samples']:
                print(' ', line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
