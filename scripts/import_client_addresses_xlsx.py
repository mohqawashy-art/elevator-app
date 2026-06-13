#!/usr/bin/env python3
"""تحديث عناوين العملاء من Excel (مطابقة برقم العميل C-xxxx) + إحداثيات للخريطة.

الاستخدام على سيرفر جما:
  cd ~/liftcore/jama-elevator-app
  source .venv/bin/activate
  export DATABASE_URL="sqlite:////home/USER/liftcore/jama-elevator-app/instance/jama.db"
  python scripts/import_client_addresses_xlsx.py deploy/data/jama_clients_13_6_2026.xlsx

أو من واجهة العملاء: زر «تحديث العناوين» (بدون SSH).

أو:
  bash deploy/import_jama_client_addresses.sh
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from client_address_import import import_client_addresses_file, load_rows_from_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Import client addresses from Excel')
    parser.add_argument('xlsx', help='Path to Excel file')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--no-geocode', action='store_true', help='Skip GPS geocoding')
    parser.add_argument('--force-geocode', action='store_true', help='Re-geocode even if lat/lng exist')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    rows = load_rows_from_path(args.xlsx)
    print(f'Rows with client code: {len(rows)}')

    with app.app_context():
        result = import_client_addresses_file(
            args.xlsx,
            dry_run=args.dry_run,
            no_geocode=args.no_geocode,
            force_geocode=args.force_geocode,
            db_session=None if args.dry_run else db.session,
        )
        if args.dry_run:
            print(f'\nDry run: would update {result["updated"]}, missing in DB {result["missing"]}')
            if result['missing_codes']:
                print('Missing codes (sample):', ', '.join(result['missing_codes'][:10]))
            return 0

        print(
            f'\nDone: updated {result["updated"]} | geocoded {result["geocoded"]} | '
            f'geo failed {result["geo_fail"]} | missing {result["missing"]}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
