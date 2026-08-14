#!/usr/bin/env python3
"""استيراد العقود لجما من Excel (بعد استيراد العملاء والمصاعد).

يحافظ على أكواد التجديد مثل CN-00001-2026.

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/import_jama_contracts.py deploy/data/jama_import/file.xlsx --slug jama --dry-run
  python scripts/import_jama_contracts.py deploy/data/jama_import/file.xlsx --slug jama --yes
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

from contract_codes import contract_base_code, normalize_contract_code
from import_real_data import (
    _cell,
    _extract_all_el,
    _extract_cn,
    _f,
    _invoice_status,
    _norm_contract_status,
    _parse_date,
    _str,
)


def _norm_cn(code: str) -> str:
    return normalize_contract_code(code)


def _customer_code_from_cn(cn_code: str) -> str | None:
    m = re.match(r'(?:CN|CI)-(\d+)', cn_code or '', re.I)
    if not m:
        return None
    return f'C-{int(m.group(1)):04d}'


def _find_customer(name: str, cn_code: str | None, customer_code: str | None = None):
    from models import Customer
    from tenant_scope import tenant_query

    code = _str(customer_code) or (_customer_code_from_cn(cn_code or '') or '')
    if code:
        customer = tenant_query(Customer).filter_by(code=code).first()
        if customer:
            return customer
    name = _str(name)
    if name:
        customer = tenant_query(Customer).filter_by(name=name).first()
        if customer:
            return customer
        norm = re.sub(r'\s+', ' ', name).strip()
        for c in tenant_query(Customer).all():
            if c.name and re.sub(r'\s+', ' ', c.name).strip() == norm:
                return c
        for c in tenant_query(Customer).all():
            if c.name and (norm in c.name or c.name in norm):
                return c
    return None


def _count_linkable_elevators(el_codes: list[str]) -> int:
    from models import Elevator
    from tenant_scope import tenant_query

    return sum(1 for code in el_codes if code and tenant_query(Elevator).filter_by(code=code).first())


def _link_elevators(contract, el_codes: list[str], *, dry_run: bool) -> int:
    from models import ContractElevator, Elevator, db
    from tenant_scope import assign_organization, tenant_query

    linked = 0
    for el_code in el_codes:
        if not el_code:
            continue
        elev = tenant_query(Elevator).filter_by(code=el_code).first()
        if not elev:
            continue
        exists = tenant_query(ContractElevator).filter_by(
            contract_id=contract.id, elevator_id=elev.id
        ).first()
        if exists:
            continue
        if dry_run:
            linked += 1
            continue
        row = ContractElevator(contract_id=contract.id, elevator_id=elev.id)
        assign_organization(row)
        db.session.add(row)
        linked += 1
    return linked


def _load_rows(path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    sheet = xl.sheet_names[0]
    for name in xl.sheet_names:
        if 'استيراد' in str(name) or str(name).lower() in ('sheet1', 'contracts'):
            sheet = name
            break
    return pd.read_excel(path, sheet_name=sheet)


def _reassign_existing_to_renewal(rows: list[dict], existing: dict, *, dry_run: bool) -> int:
    """إن كان CN-00001 في القاعدة هو فترة التجديد، انقل الكود إلى CN-00001-2026 قبل إدخال المتبقي."""
    from models import db

    leftovers = {}
    renewals = {}
    for r in rows:
        code = r['code']
        base = contract_base_code(code)
        if code == base:
            leftovers[base] = r
        else:
            renewals[base] = r

    moved = 0
    for base, renewal in renewals.items():
        leftover = leftovers.get(base)
        current = existing.get(base)
        if not leftover or not current or renewal['code'] in existing:
            continue
        cur_start = current.start_date
        new_start = renewal['start']
        old_start = leftover['start']
        if not cur_start or not new_start:
            continue
        # العقد الحالي أقرب لتواريخ التجديد منه للمتبقي
        if abs((cur_start - new_start).days) <= abs((cur_start - old_start).days):
            print(f'  [نقل كود] {base} → {renewal["code"]}  ({cur_start} ≈ تجديد {new_start})')
            if not dry_run:
                current.code = renewal['code']
                db.session.flush()
            existing.pop(base, None)
            existing[renewal['code']] = current
            moved += 1
    return moved


def import_contracts(path: str, *, dry_run: bool = False) -> dict[str, int]:
    from models import Contract, db
    from tenant_scope import assign_organization, tenant_query

    df = _load_rows(path)
    stats = {
        'rows': len(df),
        'added': 0,
        'updated': 0,
        'skipped': 0,
        'no_customer': 0,
        'linked_elevators': 0,
        'reassigned': 0,
    }
    parsed: list[dict] = []
    for _, row in df.iterrows():
        r = row.to_dict()
        code = _str(_cell(r, 'رقم العقد')) or (_extract_cn(_cell(r, 'اسم العميل ورقم العقد')) or '')
        code = _norm_cn(code) if code else ''
        name = _str(_cell(r, 'العملاء')) or _str(_cell(r, 'اسم العميل'))
        annual = _f(_cell(r, 'قيمة العقد', 'قيمة العقد قبل الضريبة'))
        start = _parse_date(_cell(r, 'تاريخ بداية العقد', 'تاريخ البداية'))
        end = _parse_date(_cell(r, 'تاريخ انتهاء العقد', 'تاريخ الانتهاء'))
        if not code or not start or not end:
            stats['skipped'] += 1
            continue
        parsed.append({
            'raw': r,
            'code': code,
            'name': name,
            'annual': annual,
            'start': start,
            'end': end,
            'el_codes': _extract_all_el(_cell(r, 'رقم المصعد', 'أكواد المصاعد', 'اسم العميل ورقم العقد')),
            'cust_code': _str(_cell(r, 'كود العميل')),
        })

    existing = {_norm_cn(c.code): c for c in tenant_query(Contract).all() if c.code}
    stats['reassigned'] = _reassign_existing_to_renewal(parsed, existing, dry_run=dry_run)

    for item in parsed:
        r = item['raw']
        code = item['code']
        name = item['name']
        annual = item['annual']
        start = item['start']
        end = item['end']
        el_codes = item['el_codes']

        if (not name or name.lower() == 'nan') and annual <= 0 and code not in existing:
            stats['skipped'] += 1
            continue

        customer = _find_customer(name, code, item['cust_code'])
        if not customer:
            stats['no_customer'] += 1
            print(f'  [تخطي] {code}: لا عميل لـ «{name}»')
            continue

        paid = _f(_cell(r, 'المبلغ المسدد'))
        val = annual
        tax = round(val * 0.15, 2)
        raw_type = _str(_cell(r, 'نوع العقد'))
        payload = dict(
            customer_id=customer.id,
            contract_type=(
                'عقد صيانة'
                if raw_type == 'صيانة'
                else raw_type or 'عقد صيانة'
            ),
            start_date=start,
            end_date=end,
            duration_months=max(0, (end.year - start.year) * 12 + end.month - start.month),
            maint_frequency=_str(_cell(r, 'برنامج الصيانة', 'تكرار الصيانة')) or 'سنوي',
            visits_per_month=1,
            value=val,
            tax_pct=15,
            tax_amount=tax,
            total=round(val + tax, 2),
            payment_terms=_str(_cell(r, 'شروط الدفع')) or 'دفعة واحدة',
            paid_amount=paid,
            invoice_status=_invoice_status(val, paid),
            status=_norm_contract_status(_cell(r, 'حالة العقد')),
            reminder_date=end - timedelta(days=30),
            city=customer.city or _str(_cell(r, 'المنطقة')),
            district=customer.district or '',
            address=customer.address or _str(_cell(r, 'العنوان')),
            notes=_str(_cell(r, 'ملاحظات')),
        )

        if code in existing:
            c = existing[code]
            for key, val_item in payload.items():
                setattr(c, key, val_item)
            stats['updated'] += 1
            contract = c
        else:
            if dry_run:
                stats['added'] += 1
                stats['linked_elevators'] += _count_linkable_elevators(el_codes)
                continue
            c = Contract(code=code, **payload)
            assign_organization(c)
            db.session.add(c)
            db.session.flush()
            existing[code] = c
            contract = c
            stats['added'] += 1

        if contract.id:
            stats['linked_elevators'] += _link_elevators(contract, el_codes, dry_run=dry_run)

    if not dry_run:
        db.session.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Import Jama contracts from Excel')
    parser.add_argument('xlsx', help='Path to contracts .xlsx')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true', help='تنفيذ الاستيراد فعلياً')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes للتأكيد أو --dry-run للمعاينة')
        return 2

    from flask import g
    from app import app
    from models import Contract, Organization

    with app.app_context():
        slug = (args.slug or 'jama').strip().lower()
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
            return 1
        g.organization = org
        g.organization_id = org.id
        print('Tenant:', org.name, org.slug, 'id=', org.id)
        print('Database:', (app.config.get('SQLALCHEMY_DATABASE_URI') or '')[:70])
        print('File:', args.xlsx)
        stats = import_contracts(args.xlsx, dry_run=args.dry_run)
        print('\n=== النتيجة ===')
        for key, val in stats.items():
            print(f'  {key}: {val}')
        if not args.dry_run:
            print('  contracts in DB:', Contract.query.filter_by(organization_id=org.id).count())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
