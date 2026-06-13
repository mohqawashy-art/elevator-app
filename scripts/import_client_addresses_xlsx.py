#!/usr/bin/env python3
"""تحديث عناوين العملاء من Excel (مطابقة برقم العميل C-xxxx) + إحداثيات للخريطة.

الاستخدام على سيرفر جما:
  cd ~/liftcore/jama-elevator-app
  source .venv/bin/activate
  export DATABASE_URL="sqlite:////home/USER/liftcore/jama-elevator-app/instance/jama.db"
  python scripts/import_client_addresses_xlsx.py deploy/data/jama_clients_13_6_2026.xlsx

أو:
  bash deploy/import_jama_client_addresses.sh
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import openpyxl
except ImportError as exc:
    raise SystemExit('pip install openpyxl') from exc

from app import app, db
from geocode import geocode_customer
from models import Customer


def _str(val) -> str:
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s


def _extract_code(text: str) -> str | None:
    m = re.search(r'C-\d+', _str(text), re.I)
    return m.group(0).upper() if m else None


def _row_dict(headers: list[str], values: tuple) -> dict[str, str]:
    row = {}
    for i, h in enumerate(headers):
        key = _str(h)
        if not key:
            continue
        row[key] = _str(values[i]) if i < len(values) else ''
    return row


def _cell(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row and row[name]:
            return row[name]
    return ''


def _find_header_row(rows: list[tuple]) -> int:
    for i, values in enumerate(rows):
        text = ' '.join(_str(v) for v in values)
        if 'رقم العميل' in text or 'C-' in text:
            if 'العنوان' in text or 'المدينة' in text:
                return i
    return 0


def load_rows(path: str) -> list[dict[str, str]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    raw = [tuple(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    if not raw:
        return []
    hi = _find_header_row(raw)
    headers = [_str(h) for h in raw[hi]]
    out = []
    for values in raw[hi + 1:]:
        if not any(_str(v) for v in values):
            continue
        row = _row_dict(headers, values)
        code = _cell(row, 'رقم العميل', 'كود العميل', 'customer_code', 'Code')
        if not code:
            code = _extract_code(_cell(row, 'اسم العميل | رقم العميل', 'اسم العميل', 'name')) or ''
        if not code:
            for v in values:
                code = _extract_code(_str(v))
                if code:
                    break
        if not code:
            continue
        row['_code'] = code.upper()
        out.append(row)
    return out


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

    rows = load_rows(args.xlsx)
    print(f'Rows with client code: {len(rows)}')

    updated = missing = geocoded = geo_fail = 0

    with app.app_context():
        by_code = {c.code.upper(): c for c in Customer.query.all() if c.code}

        for row in rows:
            code = row['_code']
            customer = by_code.get(code)
            if not customer:
                print(f'  SKIP (not in DB): {code}')
                missing += 1
                continue

            city = _cell(row, 'المدينة', 'city')
            district = _cell(row, 'الحي أو المنطقة', 'الحي', 'district')
            address = _cell(row, 'العنوان', 'address', 'العنوان التفصيلي')

            if not address and not city and not district:
                print(f'  SKIP (no address): {code}')
                continue

            changed = False
            if city and customer.city != city:
                customer.city = city
                changed = True
            if district and customer.district != district:
                customer.district = district
                changed = True
            if address and customer.address != address:
                customer.address = address
                changed = True

            need_geo = not args.no_geocode and (
                args.force_geocode
                or changed
                or not (customer.lat and customer.lng)
            )
            if need_geo:
                has_gps = False
                if customer.lat and customer.lng and not args.force_geocode:
                    try:
                        float(customer.lat)
                        float(customer.lng)
                        has_gps = True
                    except (TypeError, ValueError):
                        pass
                if not has_gps or args.force_geocode:
                    if args.dry_run:
                        print(f'  WOULD UPDATE {code}: {city} / {district} / {address[:60]}...')
                    else:
                        if geocode_customer(customer, delay=1.05):
                            geocoded += 1
                        else:
                            geo_fail += 1
                            print(f'  GEO FAIL: {code} — {address[:80]}')
                    changed = True

            if changed:
                updated += 1
                if args.dry_run and args.no_geocode:
                    print(f'  WOULD UPDATE {code}: {city} | {district} | {address[:70]}')
            elif not args.dry_run:
                pass

        if args.dry_run:
            print(f'\nDry run: would update {updated}, missing in DB {missing}')
            return 0

        db.session.commit()
        print(f'\nDone: updated {updated} | geocoded {geocoded} | geo failed {geo_fail} | missing {missing}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
