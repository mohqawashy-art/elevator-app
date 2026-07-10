#!/usr/bin/env python3
"""تحديث بيانات العملاء في جما من Excel (مطابقة برقم C-xxxx).

الاستخدام:
  export DATABASE_URL="sqlite:///$HOME/liftcore/jama-elevator-app/instance/jama.db"
  python scripts/import_jama_clients_xlsx.py "deploy/data/jama_import/العملاء 1_7_2026.xlsx" --dry-run
  python scripts/import_jama_clients_xlsx.py "deploy/data/jama_import/العملاء 1_7_2026.xlsx"
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from client_address_import import (
    _cell,
    _display_address,
    geocode_customer,
    load_rows_from_path,
    normalize_client_code,
)
from import_real_data import _norm_city, _norm_id, _str
from models import Customer


def _norm_phone(val) -> str:
    s = _norm_id(val)
    if not s:
        return ''
    if s.startswith('+'):
        return s
    if s.startswith('966'):
        return '+' + s
    if s.startswith('0'):
        return '+966' + s[1:]
    if s.startswith('5'):
        return '+966' + s
    return s


def import_clients(
    rows: list[dict],
    *,
    dry_run: bool = False,
    no_geocode: bool = False,
    force_geocode: bool = False,
    geocode_delay: float = 0.45,
) -> dict:
    stats = {
        'rows': len(rows),
        'added': 0,
        'updated': 0,
        'unchanged': 0,
        'skipped': 0,
        'geocoded': 0,
        'geo_fail': 0,
    }
    by_code = {normalize_client_code(c.code): c for c in Customer.query.all() if c.code}

    for row in rows:
        code = row.get('_code') or normalize_client_code(_cell(row, 'رقم العميل'))
        name = row.get('_name') or _str(_cell(row, 'اسم العميل'))
        if not code or not name:
            stats['skipped'] += 1
            continue

        city = _norm_city(_cell(row, 'المدينة'))
        district = _str(_cell(row, 'الحي أو المنطقة', 'الحي'))
        geo_query = _str(_cell(row, 'العنوان'))
        display_addr = _display_address(city, district, geo_query) or geo_query
        phone = _norm_phone(_cell(row, 'الجوال', 'الهاتف'))
        national_id = _norm_id(_cell(row, 'رقم الهوية'))
        email = _str(_cell(row, 'البريد الالكتروني', 'البريد الإلكتروني'))
        status = _str(_cell(row, 'حالة العميل')) or 'نشط'
        notes = _str(_cell(row, 'ملاحظات'))

        is_new = code not in by_code
        customer = by_code.get(code)
        if is_new:
            if dry_run:
                stats['added'] += 1
                continue
            customer = Customer(code=code, name=name)
            db.session.add(customer)
            db.session.flush()
            by_code[code] = customer
        elif customer is None:
            stats['skipped'] += 1
            continue

        changed = False
        for attr, val in (
            ('name', name),
            ('city', city),
            ('district', district),
            ('address', display_addr),
            ('phone', phone),
            ('national_id', national_id),
            ('email', email),
            ('status', status),
            ('notes', notes),
        ):
            if val and getattr(customer, attr) != val:
                setattr(customer, attr, val)
                changed = True

        if is_new:
            stats['added'] += 1
            changed = True
        elif changed:
            stats['updated'] += 1
        else:
            stats['unchanged'] += 1

        if dry_run:
            continue

        need_geo = not no_geocode and (force_geocode or changed or not (customer.lat and customer.lng))
        if need_geo and (geo_query or city or district):
            has_gps = False
            if customer.lat and customer.lng and not force_geocode:
                try:
                    float(customer.lat)
                    float(customer.lng)
                    has_gps = True
                except (TypeError, ValueError):
                    pass
            if not has_gps or force_geocode:
                if geocode_customer(
                    customer,
                    delay=geocode_delay,
                    query_address=geo_query or None,
                    force=force_geocode,
                ):
                    stats['geocoded'] += 1
                else:
                    stats['geo_fail'] += 1

    if not dry_run:
        db.session.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Update Jama customers from Excel')
    parser.add_argument('xlsx', help='Path to clients Excel file')
    parser.add_argument('--slug', default='jama', help='Organization slug (default: jama)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-geocode', action='store_true')
    parser.add_argument('--force-geocode', action='store_true')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    rows = load_rows_from_path(args.xlsx)
    print(f'File: {args.xlsx}')
    print(f'Rows with client code: {len(rows)}')

    from flask import g
    from models import Organization
    from tenant_scope import assign_organization

    with app.app_context():
        slug = (args.slug or 'jama').strip().lower()
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
            for o in Organization.query.order_by(Organization.id).all():
                print(f'  - {o.slug}')
            return 1
        g.organization = org
        g.organization_id = org.id
        print(f'Tenant: {org.name} ({org.slug}) id={org.id}')
        print(f'Database: {app.config.get("SQLALCHEMY_DATABASE_URI", "")}')

        # لفّ الإنشاء لتعيين organization_id
        _orig_add = db.session.add

        def _add_with_org(obj):
            if isinstance(obj, Customer) and getattr(obj, 'organization_id', None) is None:
                assign_organization(obj)
            return _orig_add(obj)

        db.session.add = _add_with_org  # type: ignore[method-assign]
        try:
            stats = import_clients(
                rows,
                dry_run=args.dry_run,
                no_geocode=args.no_geocode,
                force_geocode=args.force_geocode,
            )
        finally:
            db.session.add = _orig_add  # type: ignore[method-assign]

        print('\n=== النتيجة ===')
        for key, val in stats.items():
            print(f'  {key}: {val}')
        if not args.dry_run:
            n = Customer.query.filter_by(organization_id=org.id).count()
            print(f'  customers_in_tenant: {n}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
