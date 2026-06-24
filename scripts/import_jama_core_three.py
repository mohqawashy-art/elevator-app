#!/usr/bin/env python3
"""استيراد العملاء + الفنيين + المصاعد لجما (بالترتيب) مع تحديد الخريطة.

الاستخدام:
  export DATABASE_URL="sqlite:////path/to/jama.db"
  python scripts/import_jama_core_three.py \\
    --clients "deploy/data/jama_import/العملاء 24_6_2026.xlsx" \\
    --technicians "deploy/data/jama_import/الفنيين 24_6_2026.xlsx" \\
    --elevators "deploy/data/jama_import/المصاعد 24_6_2026.xlsx"

  python scripts/import_jama_core_three.py --dry-run ...
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

from app import app, db
from client_address_import import geocode_customers_missing
from import_real_data import (
    _cell,
    _extract_cn,
    _extract_tech,
    _f,
    _i,
    _norm_city,
    _norm_id,
    _str,
)
from models import Customer, Technician
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from import_elevators_xlsx import import_elevators


def _norm_client_code(code: str) -> str:
    s = _str(code)
    m = re.match(r'C-(\d+)', s, re.I)
    if m:
        return f'C-{int(m.group(1)):04d}'
    return s.upper()


def _norm_tech_status(raw: str) -> str:
    s = _str(raw).lower()
    if 'on duty' in s or 'نشط' in s or 'متاح' in s or 'مشغول' in s:
        return 'متاح'
    if 'off' in s or 'غير' in s:
        return 'غير نشط'
    return 'متاح'


def import_customers(path: str, *, dry_run: bool = False) -> dict[str, int]:
    df = pd.read_excel(path)
    stats = {'rows': len(df), 'added': 0, 'updated': 0, 'skipped': 0}
    existing = {_norm_client_code(c.code): c for c in Customer.query.all() if c.code}

    for _, row in df.iterrows():
        r = row.to_dict()
        code = _norm_client_code(_cell(r, 'رقم العميل'))
        name = _str(_cell(r, 'اسم العميل')) or _str(_cell(r, 'اسم العميل | رقم العميل'))
        if '|' in name:
            name = name.split('|', 1)[0].strip()
        if not code or not name:
            stats['skipped'] += 1
            continue

        city = _norm_city(_cell(r, 'المدينة'))
        district = _str(_cell(r, 'الحي أو المنطقة', 'الحي'))
        address = _str(_cell(r, 'العنوان'))
        phone = _norm_id(_cell(r, 'الجوال', 'الهاتف'))

        if code in existing:
            c = existing[code]
            changed = False
            for attr, val in (
                ('name', name), ('city', city), ('district', district),
                ('address', address or c.address), ('phone', phone or c.phone),
            ):
                if val and getattr(c, attr) != val:
                    setattr(c, attr, val)
                    changed = True
            if changed:
                stats['updated'] += 1
            else:
                stats['skipped'] += 1
            continue

        c = Customer(
            code=code,
            name=name,
            city=city,
            district=district,
            address=address,
            phone=phone,
            national_id=_norm_id(_cell(r, 'رقم الهوية')),
            email=_str(_cell(r, 'البريد الالكتروني', 'البريد الإلكتروني')),
            status=_str(_cell(r, 'حالة العميل')) or 'نشط',
            notes=_str(_cell(r, 'ملاحظات')),
        )
        if dry_run:
            stats['added'] += 1
            existing[code] = c
            continue
        db.session.add(c)
        existing[code] = c
        stats['added'] += 1

    if not dry_run:
        db.session.commit()
    return stats


def import_technicians(path: str, *, dry_run: bool = False) -> dict[str, int]:
    df = pd.read_excel(path)
    stats = {'rows': len(df), 'added': 0, 'skipped': 0}
    existing = {t.code.upper(): t for t in Technician.query.all() if t.code}

    for _, row in df.iterrows():
        r = row.to_dict()
        code = _extract_tech(_cell(r, 'Technical ID | رقم الفني', 'رقم واسم الفني', 'رقم الفني'))
        name = _str(_cell(r, 'Technical Name | اسم الفني', 'اسم الفني'))
        if not code or not name:
            stats['skipped'] += 1
            continue
        if code in existing:
            stats['skipped'] += 1
            continue
        job = _str(_cell(r, 'Job Title | المسمى الوظيفي', 'المسمى الوظيفي'))
        if '|' in job:
            job = job.split('|')[-1].strip()
        t = Technician(
            code=code,
            name=name,
            job_title=job or 'فني مصاعد',
            status=_norm_tech_status(_cell(r, 'Status | الحالة', 'الحالة')),
            city='مكة',
            emergency=True,
            notes=_str(_cell(r, 'Notes | ملاحظات', 'ملاحظات')),
        )
        if dry_run:
            stats['added'] += 1
            continue
        db.session.add(t)
        stats['added'] += 1

    if not dry_run:
        db.session.commit()
    return stats


def geocode_all_clients(*, dry_run: bool = False) -> dict[str, int]:
    if dry_run:
        pending = 0
        for c in Customer.query.all():
            if c.address or c.city or c.district:
                try:
                    if not (c.lat and c.lng):
                        pending += 1
                except (TypeError, ValueError):
                    pending += 1
        return {'would_geocode': pending}
    return geocode_customers_missing(db_session=db.session)


def main() -> int:
    parser = argparse.ArgumentParser(description='Import Jama clients, technicians, elevators')
    parser.add_argument('--clients', required=True, help='Excel: العملاء')
    parser.add_argument('--technicians', required=True, help='Excel: الفنيين')
    parser.add_argument('--elevators', required=True, help='Excel: المصاعد')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--skip-geocode', action='store_true')
    args = parser.parse_args()

    for label, path in (
        ('clients', args.clients),
        ('technicians', args.technicians),
        ('elevators', args.elevators),
    ):
        if not os.path.isfile(path):
            print(f'ERROR: {label} file not found: {path}')
            return 1

    with app.app_context():
        db.create_all()
        print('Database:', app.config.get('SQLALCHEMY_DATABASE_URI', ''))

        print('\n==> [1/4] العملاء')
        cstats = import_customers(args.clients, dry_run=args.dry_run)
        print(cstats)

        print('\n==> [2/4] الفنيين')
        tstats = import_technicians(args.technicians, dry_run=args.dry_run)
        print(tstats)

        print('\n==> [3/4] المصاعد')
        estats = import_elevators(args.elevators, dry_run=args.dry_run)
        print(estats)

        if not args.skip_geocode:
            print('\n==> [4/4] إحداثيات الخريطة (قد تستغرق 3–5 دقائق)')
            gstats = geocode_all_clients(dry_run=args.dry_run)
            print(gstats)
        else:
            print('\n==> [4/4] تخطي الخريطة — شغّل: bash deploy/geocode_jama_clients.sh')

        if not args.dry_run:
            print('\n=== الملخص ===')
            print('  عملاء:', Customer.query.count())
            print('  فنيون:', Technician.query.count())
            from models import Elevator
            print('  مصاعد:', Elevator.query.count())
            mapped = Customer.query.filter(Customer.lat.isnot(None), Customer.lng.isnot(None)).count()
            print('  عملاء على الخريطة:', mapped)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
