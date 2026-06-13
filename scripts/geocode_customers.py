#!/usr/bin/env python3
"""تحديد مواقع العملاء على الخريطة (lat/lng) من العناوين المحفوظة.

الاستخدام على جما (بعد استيراد العناوين بـ --no-geocode):
  cd ~/liftcore/jama-elevator-app
  source .venv/bin/activate
  export DATABASE_URL="sqlite:////home/info/liftcore/jama-elevator-app/instance/jama.db"
  python scripts/geocode_customers.py

أو:
  bash deploy/geocode_jama_clients.sh
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from client_address_import import geocode_customers_missing


def main() -> int:
    parser = argparse.ArgumentParser(description='Geocode customers missing GPS')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--force', action='store_true', help='Re-geocode even if lat/lng exist')
    args = parser.parse_args()

    with app.app_context():
        result = geocode_customers_missing(
            dry_run=args.dry_run,
            force=args.force,
            db_session=None if args.dry_run else db.session,
        )
        if args.dry_run:
            print(f'Dry run: would geocode {result["geocoded"]} | skipped {result["skipped"]}')
            return 0
        print(
            f'Done: geocoded {result["geocoded"]} | failed {result["geo_fail"]} | '
            f'skipped {result["skipped"]}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
