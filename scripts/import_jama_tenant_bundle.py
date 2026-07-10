#!/usr/bin/env python3
"""استيراد حزمة جما (عملاء + فنيين + مصاعد + عقود) إلى مؤسسة متعددة المستأجرين.

الترتيب: عملاء → فنيين → مصاعد → عقود

  # على السيرفر:
  set -a; source /etc/liftcore/platform.env; set +a
  cd ~/liftcore/elevator-app
  .venv/bin/python scripts/import_jama_tenant_bundle.py --slug jama \\
    --clients "/path/العملاء.xlsx" \\
    --technicians "/path/الفنيين.xlsx" \\
    --elevators "/path/المصاعد.xlsx" \\
    --contracts "/path/العقود.xlsx" \\
    --skip-geocode
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))


def _norm_phone(val) -> str:
    from import_real_data import _norm_id

    s = _norm_id(val)
    if not s:
        return ''
    if s.startswith('966'):
        return '+' + s
    if s.startswith('0') and len(s) >= 10:
        return '+966' + s[1:]
    if s.startswith('5') and len(s) == 9:
        return '+966' + s
    if s.startswith('+'):
        return s
    return s


def _bind_tenant(slug: str):
    from flask import g
    from models import Organization

    org = Organization.query.filter_by(slug=slug).first()
    if not org:
        print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
        for o in Organization.query.order_by(Organization.id).all():
            print(f'  - {o.slug}')
        raise SystemExit(1)
    g.organization = org
    g.organization_id = org.id
    print(f'Tenant: {org.name} ({org.slug}) id={org.id}')
    return org


def _add(obj):
    from models import db
    from tenant_scope import assign_organization

    assign_organization(obj)
    db.session.add(obj)
    return obj


def import_customers(path: str, *, dry_run: bool = False) -> dict[str, int]:
    import pandas as pd
    from import_real_data import _cell, _norm_city, _norm_id, _str
    from models import Customer, db

    df = pd.read_excel(path)
    stats = {'rows': len(df), 'added': 0, 'updated': 0, 'skipped': 0}

    def norm_code(code: str) -> str:
        s = _str(code)
        m = re.match(r'C-(\d+)', s, re.I)
        return f'C-{int(m.group(1)):04d}' if m else s.upper()

    existing = {norm_code(c.code): c for c in Customer.query.all() if c.code}

    for _, row in df.iterrows():
        r = row.to_dict()
        code = norm_code(_cell(r, 'رقم العميل'))
        name = _str(_cell(r, 'اسم العميل')) or _str(_cell(r, 'اسم العميل | رقم العميل'))
        if '|' in name:
            name = name.split('|', 1)[0].strip()
        if not code or not name:
            stats['skipped'] += 1
            continue

        city = _norm_city(_cell(r, 'المدينة'))
        district = _str(_cell(r, 'الحي أو المنطقة', 'الحي'))
        address = _str(_cell(r, 'العنوان'))
        phone = _norm_phone(_cell(r, 'الجوال', 'الهاتف'))

        if code in existing:
            c = existing[code]
            changed = False
            for attr, val in (
                ('name', name),
                ('city', city),
                ('district', district),
                ('address', address or c.address),
                ('phone', phone or c.phone),
            ):
                if val and getattr(c, attr) != val:
                    setattr(c, attr, val)
                    changed = True
            nid = _norm_id(_cell(r, 'رقم الهوية'))
            if nid and c.national_id != nid:
                c.national_id = nid
                changed = True
            email = _str(_cell(r, 'البريد الالكتروني', 'البريد الإلكتروني'))
            if email and c.email != email:
                c.email = email
                changed = True
            stats['updated' if changed else 'skipped'] += 1
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
            entity_type='فرد',
        )
        if dry_run:
            stats['added'] += 1
            existing[code] = c
            continue
        _add(c)
        existing[code] = c
        stats['added'] += 1

    if not dry_run:
        db.session.commit()
    return stats


def import_technicians(path: str, *, dry_run: bool = False) -> dict[str, int]:
    import pandas as pd
    from import_real_data import _cell, _extract_tech, _str
    from models import Technician, db

    df = pd.read_excel(path)
    stats = {'rows': len(df), 'added': 0, 'updated': 0, 'skipped': 0}
    existing = {t.code.upper(): t for t in Technician.query.all() if t.code}

    def norm_status(raw: str) -> str:
        s = _str(raw).lower()
        if 'on duty' in s or 'نشط' in s or 'متاح' in s or 'مشغول' in s:
            return 'متاح'
        if 'off' in s or 'غير' in s:
            return 'غير نشط'
        return 'متاح'

    for _, row in df.iterrows():
        r = row.to_dict()
        code = _extract_tech(_cell(r, 'Technical ID | رقم الفني', 'رقم واسم الفني', 'رقم الفني'))
        name = _str(_cell(r, 'Technical Name | اسم الفني', 'اسم الفني'))
        if not code or not name:
            stats['skipped'] += 1
            continue
        job = _str(_cell(r, 'Job Title | المسمى الوظيفي', 'المسمى الوظيفي'))
        if '|' in job:
            job = job.split('|')[-1].strip()
        status = norm_status(_cell(r, 'Status | الحالة', 'الحالة'))
        notes = _str(_cell(r, 'Notes | ملاحظات', 'ملاحظات'))

        if code in existing:
            t = existing[code]
            t.name = name
            t.job_title = job or t.job_title or 'فني مصاعد'
            t.status = status
            if notes:
                t.notes = notes
            stats['updated'] += 1
            continue

        t = Technician(
            code=code,
            name=name,
            job_title=job or 'فني مصاعد',
            status=status,
            city='مكة',
            emergency=True,
            notes=notes,
        )
        if dry_run:
            stats['added'] += 1
            existing[code] = t
            continue
        _add(t)
        existing[code] = t
        stats['added'] += 1

    if not dry_run:
        db.session.commit()
    return stats


def import_elevators(path: str, *, dry_run: bool = False) -> dict[str, int]:
    from import_elevators_xlsx import import_elevators as _imp
    from models import Elevator, db
    from tenant_scope import assign_organization

    # لفّ الإضافة لتعيين organization_id
    orig_add = db.session.add

    def add_wrapped(obj):
        if isinstance(obj, Elevator) and getattr(obj, 'organization_id', None) is None:
            assign_organization(obj)
        return orig_add(obj)

    db.session.add = add_wrapped  # type: ignore[method-assign]
    try:
        return _imp(path, dry_run=dry_run)
    finally:
        db.session.add = orig_add  # type: ignore[method-assign]


def import_contracts(path: str, *, dry_run: bool = False) -> dict[str, int]:
    from import_jama_contracts import import_contracts as _imp
    from models import Contract, ContractElevator, db
    from tenant_scope import assign_organization

    orig_add = db.session.add

    def add_wrapped(obj):
        if isinstance(obj, (Contract, ContractElevator)) and hasattr(obj, 'organization_id'):
            if getattr(obj, 'organization_id', None) is None:
                assign_organization(obj)
        return orig_add(obj)

    db.session.add = add_wrapped  # type: ignore[method-assign]
    try:
        return _imp(path, dry_run=dry_run)
    finally:
        db.session.add = orig_add  # type: ignore[method-assign]


def main() -> int:
    parser = argparse.ArgumentParser(description='Import Jama bundle into a tenant')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--clients', required=True)
    parser.add_argument('--technicians', required=True)
    parser.add_argument('--elevators', required=True)
    parser.add_argument('--contracts', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--skip-geocode', action='store_true', default=True)
    parser.add_argument('--geocode', action='store_true', help='Geocode customer addresses')
    args = parser.parse_args()

    for label, path in (
        ('clients', args.clients),
        ('technicians', args.technicians),
        ('elevators', args.elevators),
        ('contracts', args.contracts),
    ):
        if not os.path.isfile(path):
            print(f'ERROR: {label} not found: {path}')
            return 1

    from app import app, db
    from models import Contract, Customer, Elevator, Technician

    with app.app_context():
        org = _bind_tenant(args.slug.strip().lower())
        print('Database:', app.config.get('SQLALCHEMY_DATABASE_URI', '')[:60], '...')

        print('\n==> [1/4] العملاء')
        print(import_customers(args.clients, dry_run=args.dry_run))

        print('\n==> [2/4] الفنيين')
        print(import_technicians(args.technicians, dry_run=args.dry_run))

        print('\n==> [3/4] المصاعد')
        print(import_elevators(args.elevators, dry_run=args.dry_run))

        print('\n==> [4/4] العقود')
        print(import_contracts(args.contracts, dry_run=args.dry_run))

        if args.geocode and not args.dry_run:
            print('\n==> Geocode')
            from client_address_import import geocode_customers_missing
            print(geocode_customers_missing(db_session=db.session))

        if not args.dry_run:
            print('\n=== الملخص (جما) ===')
            print('  عملاء:', Customer.query.filter_by(organization_id=org.id).count())
            print('  فنيون:', Technician.query.filter_by(organization_id=org.id).count())
            print('  مصاعد:', Elevator.query.filter_by(organization_id=org.id).count())
            print('  عقود:', Contract.query.filter_by(organization_id=org.id).count())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
