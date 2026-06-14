#!/usr/bin/env python3
"""استيراد بيان تركيب قطع الغيار من Excel إلى jama.db.

الاستخدام:
  export DATABASE_URL="sqlite:////path/to/jama.db"
  python scripts/import_parts_billing_xlsx.py deploy/data/jama_parts_billing_14_6_2026.xlsx --dry-run
  python scripts/import_parts_billing_xlsx.py deploy/data/jama_parts_billing_14_6_2026.xlsx

أو:
  bash deploy/import_jama_parts_billing.sh
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import openpyxl
except ImportError as exc:
    raise SystemExit('pip install openpyxl') from exc

from app import app, db, next_code  # noqa: E402
from entity_links import normalize_parts_status, resolve_parts_links  # noqa: E402
from models import Contract, PartsBilling  # noqa: E402

OP_NOTE_PREFIX = 'رقم العملية:'


def _str(val) -> str:
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s


def _float(val, default: float = 0.0) -> float:
    try:
        if val is None or _str(val) == '':
            return default
        return round(float(val), 2)
    except (TypeError, ValueError):
        return default


def _extract_cn(text: str) -> str | None:
    m = re.search(r'CN-\s*(\d+)', _str(text), re.I)
    if not m:
        return None
    return f'CN-{int(m.group(1)):05d}'


def _parse_date(val) -> date | None:
    if val is None or val == '':
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = _str(val)
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _norm_op_number(val) -> str:
    s = _str(val)
    if not s:
        return ''
    digits = re.sub(r'\D', '', s)
    return digits.lstrip('0') or '0'


def _compose_notes(row: tuple) -> str:
    parts = []
    op = _norm_op_number(row[1] if len(row) > 1 else '')
    if op:
        parts.append(f'{OP_NOTE_PREFIX} {op.zfill(3)}')
    invoice = _str(row[7] if len(row) > 7 else '')
    if invoice:
        parts.append(f'فاتورة: {invoice}')
    paid_on = _parse_date(row[9] if len(row) > 9 else '')
    if paid_on:
        parts.append(f'تاريخ السداد: {paid_on.isoformat()}')
    extra = _str(row[11] if len(row) > 11 else '')
    if extra:
        parts.append(extra)
    return '\n'.join(parts)


def _existing_op_numbers() -> set[str]:
    found: set[str] = set()
    pattern = re.compile(r'رقم العملية:\s*(\d+)')
    for p in PartsBilling.query.all():
        if not p.notes:
            continue
        for m in pattern.finditer(p.notes):
            found.add(m.group(1).lstrip('0') or '0')
    return found


def load_rows(path: str) -> list[tuple]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    raw = [tuple(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    if not raw:
        return []
    header_idx = 0
    for i, row in enumerate(raw):
        text = ' '.join(_str(v) for v in row)
        if 'بيان قطع' in text or 'رقم العمل' in text or 'CN-' in text:
            header_idx = i
            break
    out = []
    for row in raw[header_idx + 1:]:
        if not any(_str(v) for v in row):
            continue
        if not _parse_date(row[3] if len(row) > 3 else ''):
            continue
        if not _str(row[4] if len(row) > 4 else ''):
            continue
        out.append(row)
    return out


def import_parts(path: str, *, dry_run: bool = False, skip_existing: bool = True) -> dict:
    rows = load_rows(path)
    stats = {
        'rows': len(rows),
        'imported': 0,
        'skipped_existing': 0,
        'skipped_missing': 0,
        'errors': 0,
    }
    missing_samples: list[str] = []

    contracts = {
        c.code.upper(): c
        for c in Contract.query.all()
        if c.code
    }
    existing_ops = _existing_op_numbers() if skip_existing else set()

    for row in rows:
        cn_code = _extract_cn(row[2] if len(row) > 2 else '') or _extract_cn(row[0] if len(row) > 0 else '')
        billing_date = _parse_date(row[3] if len(row) > 3 else '')
        description = _str(row[4] if len(row) > 4 else '')
        op_num = _norm_op_number(row[1] if len(row) > 1 else '')

        if not cn_code or not billing_date or not description:
            stats['errors'] += 1
            continue

        if skip_existing and op_num and op_num in existing_ops:
            stats['skipped_existing'] += 1
            continue

        contract = contracts.get(cn_code.upper())
        if not contract:
            stats['skipped_missing'] += 1
            if len(missing_samples) < 15:
                missing_samples.append(f'عملية {op_num or "?"}: عقد {cn_code} غير موجود')
            continue

        cost = _float(row[5] if len(row) > 5 else 0)
        sell = _float(row[6] if len(row) > 6 else 0)
        status = normalize_parts_status(_str(row[8] if len(row) > 8 else ''))
        payment_method = _str(row[10] if len(row) > 10 else '')
        notes = _compose_notes(row)

        links = resolve_parts_links(contract_code=cn_code)

        if dry_run:
            stats['imported'] += 1
            if op_num:
                existing_ops.add(op_num)
            continue

        part = PartsBilling(
            code=next_code(PartsBilling, 'PB-', digits=3),
            customer_id=links['customer_id'],
            contract_id=links['contract_id'],
            elevator_id=links['elevator_id'],
            technician_id=links['technician_id'],
            visit_id=links['visit_id'],
            fault_id=links['fault_id'],
            billing_date=billing_date,
            description=description,
            cost_price=cost,
            sell_price=sell,
            profit=round(sell - cost, 2),
            paid_amount=sell if status == 'محصل' else 0,
            payment_method=payment_method,
            status=status,
            notes=notes or None,
        )
        db.session.add(part)
        if op_num:
            existing_ops.add(op_num)
        stats['imported'] += 1

    if not dry_run:
        db.session.commit()

    stats['missing_samples'] = missing_samples
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Import parts billing from Excel')
    parser.add_argument('xlsx', help='Path to Excel file')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--force', action='store_true', help='Import even if operation number exists')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    with app.app_context():
        result = import_parts(
            args.xlsx,
            dry_run=args.dry_run,
            skip_existing=not args.force,
        )
        print(f"Rows in file: {result['rows']}")
        if args.dry_run:
            print(f"Dry run: would import {result['imported']}")
        else:
            print(f"Imported: {result['imported']}")
        print(f"Skipped (existing): {result['skipped_existing']}")
        print(f"Skipped (missing contract): {result['skipped_missing']}")
        print(f"Errors: {result['errors']}")
        if result.get('missing_samples'):
            print('Missing samples:')
            for line in result['missing_samples']:
                print(' ', line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
