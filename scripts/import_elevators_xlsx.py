#!/usr/bin/env python3
"""استيراد مصاعد من ملف Excel (تنسيق جما / Notion) إلى قاعدة LiftCore.

الاستخدام على سيرفر جما:
  cd ~/liftcore/jama-elevator-app
  source .venv/bin/activate
  export DATABASE_URL="sqlite:////home/USER/liftcore/jama-elevator-app/instance/jama.db"
  python scripts/import_elevators_xlsx.py deploy/data/jama_elevators_13_6_2026.xlsx

أو:
  bash deploy/import_jama_elevators.sh
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import openpyxl
except ImportError as exc:
    raise SystemExit('pip install openpyxl') from exc

from app import app, db, sync_customer_from_elevators
from models import Contract, ContractElevator, Customer, Elevator


def _str(val) -> str:
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s


def _int(val, default=0) -> int:
    try:
        if val is None or _str(val) == '':
            return default
        return int(float(val))
    except (TypeError, ValueError):
        return default


def _extract_cn(text: str) -> str | None:
    m = re.search(r'CN-\d+', _str(text))
    return m.group(0) if m else None


def _extract_el(text: str) -> str | None:
    m = re.search(r'EL-\d+', _str(text).split('|')[0])
    return m.group(0) if m else None


def _norm_status(val: str) -> str:
    s = _str(val)
    if s in ('فعال', 'نشط'):
        return 'نشط'
    if s in ('متوقف', 'خارج الخدمة', 'تحت الصيانة'):
        return s
    return s or 'نشط'


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
    for key, val in row.items():
        for name in names:
            if name in key and val:
                return val
    return ''


def _normalize_name(text: str) -> str:
    return re.sub(r'\s+', ' ', _str(text)).strip()


def _find_customer(cn_code: str | None, title: str, contracts: dict, customers_by_name: dict) -> Customer | None:
    contract = contracts.get(cn_code or '') if cn_code else None
    if contract and contract.customer_id:
        customer = Customer.query.get(contract.customer_id)
        if customer:
            return customer

    name_part = _normalize_name(re.sub(r'^CN-\d+\s*', '', title))
    if name_part:
        customer = customers_by_name.get(name_part)
        if customer:
            return customer
        for name, cust in customers_by_name.items():
            if name_part in name or name in name_part:
                return cust

    if cn_code:
        alt = re.sub(r'^CN-', 'C-', cn_code)
        customer = Customer.query.filter_by(code=alt).first()
        if customer:
            return customer
        # CN-00001 → C-0001
        m = re.match(r'CN-(\d+)$', cn_code)
        if m:
            short = f'C-{int(m.group(1))}'
            customer = Customer.query.filter_by(code=short).first()
            if customer:
                return customer
    return None


def load_rows(path: str) -> list[dict[str, str]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []
    header_idx = 0
    for i, row in enumerate(rows):
        text = ' '.join(_str(v) for v in row)
        if 'رقم المصعد' in text or 'EL-' in text:
            header_idx = i
            break
    headers = [_str(h) for h in rows[header_idx]]
    out = []
    for row in rows[header_idx + 1:]:
        if not any(row):
            continue
        parsed = _row_dict(headers, row)
        if not _extract_el(_cell(parsed, 'رقم المصعد')):
            continue
        out.append(parsed)
    return out


def import_elevators(path: str, dry_run: bool = False) -> dict[str, int]:
    rows = load_rows(path)
    stats = {'rows': len(rows), 'added': 0, 'linked': 0, 'skipped_existing': 0, 'skipped_no_customer': 0, 'errors': 0}

    contracts = {c.code: c for c in Contract.query.all() if c.code}
    customers_by_name = {_normalize_name(c.name): c for c in Customer.query.all() if c.name}

    touched_customers: set[int] = set()

    for row in rows:
        el_code = _extract_el(_cell(row, 'رقم المصعد'))
        cn_code = _extract_cn(_cell(row, 'رقم العقد', 'Link to Contracts / العقود', 'Title'))
        if not el_code:
            stats['errors'] += 1
            continue

        if Elevator.query.filter_by(code=el_code).first():
            stats['skipped_existing'] += 1
            continue

        title = _cell(row, 'Title', 'Link to Contracts / العقود')
        contract = contracts.get(cn_code or '')
        customer = None
        cust_code = _cell(row, 'كود العميل', 'customer_code')
        m_code = re.match(r'C-(\d+)', cust_code, re.I) if cust_code else None
        if m_code:
            customer = Customer.query.filter_by(code=f'C-{int(m_code.group(1)):04d}').first()
        if not customer:
            customer = _find_customer(cn_code, title, contracts, customers_by_name)
        if not customer:
            stats['skipped_no_customer'] += 1
            print(f'  [تخطي] {el_code}: لا عميل/عقد لـ {cn_code or _cell(row, "Title")}')
            continue

        title = _cell(row, 'Title', 'Link to Contracts / العقود')
        base_name = _normalize_name(re.sub(r'^CN-\d+\s*', '', title)) or customer.name
        unit = _str(_cell(row, 'اسم المبنى', 'الوحدة', 'المبنى', 'رقم الوحدة', 'ملاحظات المصعد')).strip()
        if unit and unit != base_name:
            building = unit
        else:
            building = f'{base_name} — {el_code}'
        warranty = _cell(row, 'حالة الضمان')
        notes = f'حالة الضمان: {warranty}' if warranty else ''

        elev = Elevator(
            code=el_code,
            customer_id=customer.id,
            building_name=building,
            city=customer.city or '',
            district=customer.district or '',
            elev_type=_cell(row, 'نوع المصعد') or 'مصعد ركاب',
            door_type=_cell(row, 'نوع الباب', 'door_type') or '',
            capacity_kg=_int(_cell(row, 'الحمولة (كجم)', 'الحمولة')) or None,
            floors=_int(_cell(row, 'عدد الوقفات', 'عدد الطوابق')) or None,
            status=_norm_status(_cell(row, 'حالة المصعد', 'الحالة')),
            notes=notes,
        )
        if dry_run:
            stats['added'] += 1
            print(f'  [معاينة] {el_code} → {customer.name} ({cn_code or "—"})')
            continue

        db.session.add(elev)
        db.session.flush()
        stats['added'] += 1
        touched_customers.add(customer.id)

        if contract:
            exists = ContractElevator.query.filter_by(
                contract_id=contract.id, elevator_id=elev.id
            ).first()
            if not exists:
                db.session.add(ContractElevator(contract_id=contract.id, elevator_id=elev.id))
                stats['linked'] += 1

    if not dry_run:
        for cid in touched_customers:
            cust = Customer.query.get(cid)
            if cust:
                sync_customer_from_elevators(cust)
        db.session.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description='Import elevators Excel into LiftCore DB')
    parser.add_argument('xlsx', help='Path to elevators .xlsx file')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, no DB writes')
    args = parser.parse_args()

    path = args.xlsx
    if not os.path.isfile(path):
        raise SystemExit(f'File not found: {path}')

    with app.app_context():
        db.create_all()
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print(f'Database: {db_uri}')
        print(f'File: {path}')
        stats = import_elevators(path, dry_run=args.dry_run)
        print('\n=== النتيجة ===')
        for key, val in stats.items():
            print(f'  {key}: {val}')


if __name__ == '__main__':
    main()
