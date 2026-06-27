#!/usr/bin/env python3
"""Import Jama revenues from Excel with contract / parts / invoice linking."""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

from app import app, db, sync_contract_invoice_status
from customer_billing import (
    apply_payment_to_source,
    parts_remaining,
    repair_contract_payment_links,
    resolve_contract_id,
    split_vat_amounts,
)
from entity_links import contract_by_code, customer_by_name
from import_real_data import _cell, _extract_cn, _f, _i, _parse_date, _str
from models import Contract, Invoice, PartsBilling, Revenue

PARTS_REVENUE_TYPES = frozenset({'قطع غيار', 'بيع قطع غيار', 'زيارة'})
CONTRACT_REVENUE_TYPES = frozenset({'تجديد عقد', 'عقد صيانة', 'عقد جديد', 'ضمان'})


def _normalize_cn(code: str | None) -> str | None:
    raw = _extract_cn(code or '') or _extract_cn(_str(code))
    if not raw:
        return None
    m = re.search(r'CN-(\d+)', raw.upper())
    if not m:
        return raw.upper()
    return f'CN-{int(m.group(1)):05d}'


def _customer_name_from_title(title: str) -> str:
    text = _str(title)
    text = re.sub(r'CN-\s*\d+\s*', '', text, flags=re.I).strip(' -|،,')
    return text


def _map_status(raw: str) -> str:
    s = _str(raw)
    if s in ('محصل', 'محصّل', 'مكتملة'):
        return 'محصّل'
    if s in ('معلق', 'معلّق'):
        return 'معلق'
    if 'لغ' in s:
        return 'ملغي'
    return s or 'محصّل'


def _normalize_revenue_type(raw: str) -> str:
    s = _str(raw)
    if not s:
        return 'أخرى'
    if 'بيع' in s and 'قطع' in s:
        return 'قطع غيار'
    if s == 'زيارة':
        return 'أعمال إضافية'
    if s in ('تجديد عقد', 'عقد جديد', 'قطع غيار', 'عقد صيانة', 'أعمال إضافية', 'أخرى'):
        return s
    if 'تجديد' in s or 'صيانة' in s:
        return 'تجديد عقد'
    if 'عقد' in s and 'جديد' in s:
        return 'عقد جديد'
    if 'قطع' in s:
        return 'قطع غيار'
    return s


def _money_close(a: float, b: float, tol: float = 1.0) -> bool:
    return abs(_f(a) - _f(b)) <= tol


def _find_parts_billing(
    *,
    customer_id: int,
    contract_id: int | None,
    revenue_date,
    amount_ex: float,
    total_incl: float,
    used_parts: set[int],
) -> PartsBilling | None:
    q = PartsBilling.query.filter_by(customer_id=customer_id)
    if contract_id:
        q = q.filter(
            (PartsBilling.contract_id == contract_id) | (PartsBilling.contract_id.is_(None))
        )
    candidates = q.order_by(PartsBilling.billing_date.desc()).all()
    scored: list[tuple[int, PartsBilling]] = []

    for pb in candidates:
        if pb.id in used_parts:
            continue
        if pb.billing_date and revenue_date:
            days = abs((pb.billing_date - revenue_date).days)
            if days > 90:
                continue
        else:
            days = 999

        sell = _f(pb.sell_price)
        sell_incl = round(sell * 1.15, 2)
        remaining = parts_remaining(pb)

        score = 0
        if _money_close(amount_ex, sell) or _money_close(total_incl, sell) or _money_close(total_incl, sell_incl):
            score += 50
        elif _money_close(remaining, total_incl) or _money_close(remaining, amount_ex):
            score += 40
        elif remaining > 0.01:
            score += 10

        if contract_id and pb.contract_id == contract_id:
            score += 20
        if days <= 7:
            score += 15
        elif days <= 30:
            score += 8

        if score >= 40:
            scored.append((score, pb))

    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1].billing_date or revenue_date), reverse=False)
    return scored[0][1]


def _find_invoice(
    *,
    customer_id: int,
    contract_id: int | None,
    total_incl: float,
    used_invoices: set[int],
) -> Invoice | None:
    q = Invoice.query.filter_by(customer_id=customer_id)
    if contract_id:
        q = q.filter(
            (Invoice.contract_id == contract_id) | (Invoice.contract_id.is_(None))
        )
    for inv in q.order_by(Invoice.invoice_date.desc()).all():
        if inv.id in used_invoices:
            continue
        if _money_close(inv.total, total_incl) or _money_close(inv.amount, total_incl / 1.15):
            return inv
    return None


def _resolve_customer_contract(row: dict) -> tuple:
    cn = _normalize_cn(_cell(row, 'العقود', 'Title'))
    title = _str(_cell(row, 'Title', 'العقود'))
    contract = contract_by_code(cn) if cn else None
    customer = contract.customer if contract else None

    if not customer:
        name = _customer_name_from_title(title)
        if name:
            customer = customer_by_name(name)

    if not contract and customer and cn:
        contract = Contract.query.filter_by(code=cn, customer_id=customer.id).first()
        if not contract:
            contract = contract_by_code(cn)

    if not contract and customer:
        contract = (
            Contract.query.filter_by(customer_id=customer.id)
            .order_by(Contract.end_date.desc())
            .first()
        )

    return contract, customer, cn


def import_revenues(path: str, *, dry_run: bool = False, skip_existing: bool = True) -> dict:
    df = pd.read_excel(path)
    stats = {
        'rows': len(df),
        'imported': 0,
        'skipped_existing': 0,
        'skipped_missing': 0,
        'errors': 0,
        'linked_contract': 0,
        'linked_parts': 0,
        'linked_invoice': 0,
        'types': {},
    }
    missing_samples: list[str] = []
    contract_ids: set[int] = set()
    used_parts: set[int] = set()
    used_invoices: set[int] = set()

    existing_codes = {r.code.upper() for r in Revenue.query.all() if r.code}

    for _, row in df.iterrows():
        r = row.to_dict()
        num = _i(_cell(r, 'رقم العملية'))
        code = f'REV-{num:04d}' if num else ''
        rdate = _parse_date(_cell(r, 'التاريخ'))
        amount_ex = _f(_cell(r, 'المبلغ'))
        amount_ex, tax, total_incl = split_vat_amounts(amount_ex_vat=amount_ex)
        rev_type = _normalize_revenue_type(_cell(r, 'نوع الايراد'))

        if not code or not rdate or amount_ex <= 0:
            stats['errors'] += 1
            continue

        if skip_existing and code.upper() in existing_codes:
            stats['skipped_existing'] += 1
            continue

        contract, customer, cn = _resolve_customer_contract(r)
        if not contract and not customer:
            stats['skipped_missing'] += 1
            if len(missing_samples) < 20:
                missing_samples.append(f'{code}: لا عقد/عميل لـ {cn or _str(_cell(r, "Title"))}')
            continue

        customer_id = customer.id if customer else (contract.customer_id if contract else None)
        contract_id = contract.id if contract else None

        if not contract_id and customer_id:
            contract_id = resolve_contract_id(
                customer_id,
                _str(_cell(r, 'مرفقات')),
                _str(_cell(r, 'ملاحظات')),
                cn or '',
                rev_type,
            )

        invoice_id = None
        parts_billing_id = None

        if rev_type in PARTS_REVENUE_TYPES:
            pb = _find_parts_billing(
                customer_id=customer_id,
                contract_id=contract_id,
                revenue_date=rdate,
                amount_ex=amount_ex,
                total_incl=total_incl,
                used_parts=used_parts,
            )
            if pb:
                parts_billing_id = pb.id
                if not contract_id and pb.contract_id:
                    contract_id = pb.contract_id
                stats['linked_parts'] += 1
                if not dry_run:
                    used_parts.add(pb.id)

        elif rev_type == 'عقد جديد':
            inv = _find_invoice(
                customer_id=customer_id,
                contract_id=contract_id,
                total_incl=total_incl,
                used_invoices=used_invoices,
            )
            if inv:
                invoice_id = inv.id
                if not contract_id and inv.contract_id:
                    contract_id = inv.contract_id
                stats['linked_invoice'] += 1
                if not dry_run:
                    used_invoices.add(inv.id)

        if contract_id:
            stats['linked_contract'] += 1
            contract_ids.add(contract_id)

        stats['types'][rev_type] = stats['types'].get(rev_type, 0) + 1

        revenue = Revenue(
            code=code,
            customer_id=customer_id,
            contract_id=contract_id,
            invoice_id=invoice_id,
            parts_billing_id=parts_billing_id,
            revenue_date=rdate,
            revenue_type=rev_type,
            payment_method=_str(_cell(r, 'طريقة الدفع')) or 'كاش',
            amount=amount_ex,
            tax_amount=tax,
            total=total_incl,
            status=_map_status(_cell(r, 'Status', 'الحالة')),
            reference=_str(_cell(r, 'مرفقات')),
            notes=_str(_cell(r, 'ملاحظات')),
        )

        if not dry_run:
            db.session.add(revenue)
            db.session.flush()

            if parts_billing_id and revenue.status in ('محصّل', 'محصل'):
                try:
                    link = apply_payment_to_source('parts_billing', parts_billing_id, total_incl)
                    revenue.parts_billing_id = link['parts_billing_id']
                    revenue.contract_id = link.get('contract_id') or revenue.contract_id
                    revenue.revenue_type = link.get('revenue_type') or revenue.revenue_type
                except ValueError:
                    pass

            if invoice_id and revenue.status in ('محصّل', 'محصل'):
                try:
                    link = apply_payment_to_source('invoice', invoice_id, total_incl)
                    revenue.invoice_id = link['invoice_id']
                    revenue.contract_id = link.get('contract_id') or revenue.contract_id
                    revenue.revenue_type = link.get('revenue_type') or revenue.revenue_type
                except ValueError:
                    pass

            existing_codes.add(code.upper())

        stats['imported'] += 1

    if not dry_run:
        repair_contract_payment_links(commit=False)
        for cid in contract_ids:
            sync_contract_invoice_status(cid)
        db.session.commit()

    stats['missing_samples'] = missing_samples
    stats['total_in_db'] = Revenue.query.count() if not dry_run else None
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Import Jama revenues from Excel')
    parser.add_argument('xlsx', help='Path to revenues .xlsx')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true', help='Import even if revenue code exists')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    with app.app_context():
        db.create_all()
        print('Database:', app.config.get('SQLALCHEMY_DATABASE_URI', ''))
        print('File:', args.xlsx)
        result = import_revenues(
            args.xlsx,
            dry_run=args.dry_run,
            skip_existing=not args.force,
        )
        print(result)
        if result.get('missing_samples'):
            print('Missing samples:')
            for line in result['missing_samples']:
                print(' ', line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
