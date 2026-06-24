#!/usr/bin/env python3
"""استيراد العقود لجما من Excel (بعد استيراد العملاء والمصاعد).

الاستخدام:
  export DATABASE_URL="sqlite:////path/to/jama.db"
  python scripts/import_jama_contracts.py deploy/data/jama_import/contracts_24_6_2026.xlsx
  python scripts/import_jama_contracts.py --dry-run ...
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

from app import app, db
from import_real_data import (
    _cell,
    _extract_cn,
    _extract_el,
    _f,
    _invoice_status,
    _norm_contract_status,
    _parse_date,
    _str,
)
from models import Contract, ContractElevator, Customer, Elevator


def _norm_cn(code: str) -> str:
    s = _str(code)
    m = re.match(r'CN-(\d+)', s, re.I)
    if m:
        return f'CN-{int(m.group(1)):05d}'
    return s.upper()


def _find_customer(name: str, cn_code: str | None) -> Customer | None:
    name = _str(name)
    if name:
        customer = Customer.query.filter_by(name=name).first()
        if customer:
            return customer
        norm = re.sub(r'\s+', ' ', name).strip()
        for c in Customer.query.all():
            if c.name and re.sub(r'\s+', ' ', c.name).strip() == norm:
                return c
            if c.name and (norm in c.name or c.name in norm):
                return c
    if cn_code:
        m = re.match(r'CN-(\d+)$', cn_code, re.I)
        if m:
            short = f'C-{int(m.group(1)):04d}'
            customer = Customer.query.filter_by(code=short).first()
            if customer:
                return customer
    return None


def _link_elevator(contract: Contract, el_code: str | None, *, dry_run: bool) -> bool:
    if not el_code:
        return False
    elev = Elevator.query.filter_by(code=el_code).first()
    if not elev:
        return False
    exists = ContractElevator.query.filter_by(
        contract_id=contract.id, elevator_id=elev.id
    ).first()
    if exists:
        return False
    if dry_run:
        return True
    db.session.add(ContractElevator(contract_id=contract.id, elevator_id=elev.id))
    return True


def import_contracts(path: str, *, dry_run: bool = False) -> dict[str, int]:
    df = pd.read_excel(path)
    stats = {
        'rows': len(df),
        'added': 0,
        'updated': 0,
        'skipped': 0,
        'no_customer': 0,
        'linked_elevators': 0,
    }
    existing = {_norm_cn(c.code): c for c in Contract.query.all() if c.code}

    for _, row in df.iterrows():
        r = row.to_dict()
        code = _str(_cell(r, 'رقم العقد')) or (_extract_cn(_cell(r, 'اسم العميل ورقم العقد')) or '')
        code = _norm_cn(code) if code else ''
        name = _str(_cell(r, 'العملاء'))
        annual = _f(_cell(r, 'قيمة العقد'))
        start = _parse_date(_cell(r, 'تاريخ بداية العقد'))
        end = _parse_date(_cell(r, 'تاريخ انتهاء العقد'))
        el_code = _extract_el(_cell(r, 'رقم المصعد', 'اسم العميل ورقم العقد'))

        if not code or not start or not end:
            stats['skipped'] += 1
            continue
        if (not name or name.lower() == 'nan') and annual <= 0 and code not in existing:
            stats['skipped'] += 1
            continue

        customer = _find_customer(name, code)
        if not customer:
            stats['no_customer'] += 1
            print(f'  [تخطي] {code}: لا عميل لـ «{name}»')
            continue

        paid = _f(_cell(r, 'المبلغ المسدد'))
        val = annual
        tax = round(val * 0.15, 2)
        payload = dict(
            customer_id=customer.id,
            contract_type=(
                'عقد صيانة'
                if _str(_cell(r, 'نوع العقد')) == 'صيانة'
                else _str(_cell(r, 'نوع العقد')) or 'عقد صيانة'
            ),
            start_date=start,
            end_date=end,
            duration_months=max(0, (end.year - start.year) * 12 + end.month - start.month),
            maint_frequency=_str(_cell(r, 'برنامج الصيانة')) or 'سنوي',
            visits_per_month=1,
            value=val,
            tax_pct=15,
            tax_amount=tax,
            total=round(val + tax, 2),
            payment_terms='دفعة واحدة',
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
                continue
            c = Contract(code=code, **payload)
            db.session.add(c)
            db.session.flush()
            existing[code] = c
            contract = c
            stats['added'] += 1

        if not dry_run and contract.id:
            if _link_elevator(contract, el_code, dry_run=False):
                stats['linked_elevators'] += 1
        elif dry_run and el_code and Elevator.query.filter_by(code=el_code).first():
            stats['linked_elevators'] += 1

    if not dry_run:
        db.session.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Import Jama contracts from Excel')
    parser.add_argument('xlsx', help='Path to contracts .xlsx')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    with app.app_context():
        db.create_all()
        print('Database:', app.config.get('SQLALCHEMY_DATABASE_URI', ''))
        print('File:', args.xlsx)
        stats = import_contracts(args.xlsx, dry_run=args.dry_run)
        print(stats)
        if not args.dry_run:
            print('  contracts in DB:', Contract.query.count())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
