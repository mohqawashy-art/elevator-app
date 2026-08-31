#!/usr/bin/env python3
"""استيراد زيارات الصيانة من Excel (تنسيق جما / Notion) إلى jama.db.

الاستخدام:
  cd ~/liftcore/jama-elevator-app
  source .venv/bin/activate
  export DATABASE_URL="sqlite:////home/info/liftcore/jama-elevator-app/instance/jama.db"
  python scripts/import_maintenance_visits_xlsx.py deploy/data/jama_visits_14_6_2026.xlsx --dry-run
  python scripts/import_maintenance_visits_xlsx.py deploy/data/jama_visits_14_6_2026.xlsx

أو:
  bash deploy/import_jama_maintenance_visits.sh
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

from app import app, db
from models import Contract, Elevator, MaintenanceVisit, Technician


def _str(val) -> str:
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s


def _extract_code(text: str, prefix: str) -> str | None:
    m = re.search(rf'{prefix}-\s*(\d+)', _str(text), re.I)
    if not m:
        return None
    digits = int(m.group(1))
    width = 5 if prefix.upper() == 'CN' else 4
    return f'{prefix.upper()}-{digits:0{width}d}'


def _extract_all_codes(text: str, prefix: str) -> list[str]:
    return [
        f'{prefix.upper()}-{int(n):04d}'
        for n in re.findall(rf'{prefix}-\s*(\d+)', _str(text), re.I)
    ]


def _norm_visit_code(text: str) -> str | None:
    m = re.search(r'VI-\s*(\d+)', _str(text).replace(' ', ''), re.I)
    if not m:
        return None
    return f'VI-{int(m.group(1)):05d}'


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


def _map_status(raw: str) -> str:
    s = _str(raw)
    if not s:
        return 'مجدولة'
    if 'مكتمل' in s or 'اصلاح' in s or 'إصلاح' in s or 'تم ال' in s:
        return 'مكتملة'
    if 'ملغ' in s:
        return 'ملغية'
    if 'متأخر' in s:
        return 'متأخرة'
    if 'جار' in s or 'جاري' in s:
        return 'جاري التنفيذ'
    if 'مجدول' in s:
        return 'مجدولة'
    return s


def _map_visit_type(raw: str) -> str:
    s = _str(raw)
    if 'متابعة' in s or 'مرجعة' in s:
        return 'زيارة متابعة'
    if 'دور' in s:
        return 'صيانة دورية'
    return s or 'صيانة دورية'


def is_routine_maintenance_visit(raw: str) -> bool:
    """صيانة دورية + زيارة متابعة → صفحة زيارات الصيانة."""
    s = _str(raw)
    if not s or 'عطل' in s:
        return False
    return 'دورية' in s or 'متابعة' in s or 'مرجعة' in s


def is_fault_bucket_visit(raw: str) -> bool:
    """صفوف «عطل» فقط → صفحة الأعطال."""
    s = _str(raw)
    return bool(s) and 'عطل' in s


def _visit_type_cell(row: tuple) -> str:
    return _str(row[6] if len(row) > 6 else '')


def _is_fault_visit_row(row: tuple) -> bool:
    return is_fault_bucket_visit(_visit_type_cell(row))


def _pick_elevator_code(el_text: str, report_text: str) -> str | None:
    codes = _extract_all_codes(el_text, 'EL')
    if not codes:
        return None
    if len(codes) == 1:
        return codes[0]
    report = _str(report_text)
    if re.search(r'رقم\s*2|مصعد\s*2|#2', report):
        return codes[1] if len(codes) > 1 else codes[0]
    return codes[0]


def _pick_technician_code(tech_text: str) -> str | None:
    codes = _extract_all_codes(tech_text, 'Tech')
    return codes[0] if codes else None


def _build_index(model, prefix: str) -> dict[str, object]:
    idx: dict[str, object] = {}
    width = 5 if prefix.upper() == 'CN' else 4
    for row in model.query.all():
        code = getattr(row, 'code', None)
        if not code:
            continue
        idx[str(code).upper()] = row
        m = re.match(rf'{prefix.upper()}-(\d+)$', str(code).upper())
        if m:
            norm = f'{prefix.upper()}-{int(m.group(1)):0{width}d}'
            idx[norm] = row
    return idx


def _lookup(idx: dict, code: str | None):
    if not code:
        return None
    return idx.get(code.upper()) or idx.get(code)


def _compose_notes(row: tuple) -> str:
    parts = []
    mapping = (
        (10, 'تقرير'),
        (16, 'توصيات'),
        (17, 'قطع الغيار'),
        (18, 'وصف العطل'),
        (20, 'التشخيص'),
        (21, 'الإجراء'),
        (22, 'ضمان'),
    )
    for i, label in mapping:
        val = _str(row[i]) if i < len(row) else ''
        if val:
            parts.append(f'{label}: {val}')
    return '\n'.join(parts)


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
        if 'رقم الزيارة' in text or 'VI' in text:
            header_idx = i
            break
    out = []
    for row in raw[header_idx + 1:]:
        if not any(_str(v) for v in row):
            continue
        if not _str(row[6] if len(row) > 6 else ''):
            continue
        out.append(row)
    return out


def import_visits(
    path: str,
    *,
    dry_run: bool = False,
    skip_existing: bool = True,
    force_completed: bool = True,
    update_existing: bool = False,
) -> dict:
    from tenant_scope import assign_organization

    rows = load_rows(path)
    stats = {
        'rows': len(rows),
        'imported': 0,
        'updated': 0,
        'skipped_existing': 0,
        'skipped_missing': 0,
        'skipped_fault': 0,
        'errors': 0,
    }
    missing_samples: list[str] = []

    elevators = _build_index(Elevator, 'EL')
    contracts = _build_index(Contract, 'CN')
    technicians = _build_index(Technician, 'Tech')
    existing_by_code = {
        (v.code or '').upper(): v
        for v in MaintenanceVisit.query.all()
        if v.code
    }

    # ترتيب خط السير داخل كل يوم
    day_route: dict[str, int] = {}

    for row in rows:
        visit_type_raw = _visit_type_cell(row)
        if not is_routine_maintenance_visit(visit_type_raw):
            stats['skipped_fault'] += 1
            continue

        visit_code = _norm_visit_code(row[1] if len(row) > 1 else '')
        cn_code = _extract_code(row[3] if len(row) > 3 else '', 'CN')
        el_code = _pick_elevator_code(row[4] if len(row) > 4 else '', row[10] if len(row) > 10 else '')
        tech_code = _pick_technician_code(row[5] if len(row) > 5 else '')
        visit_date = _parse_date(row[7] if len(row) > 7 else '')

        if not visit_code or not el_code or not visit_date:
            stats['errors'] += 1
            continue

        day_key = str(visit_date)
        day_route[day_key] = day_route.get(day_key, 0) + 1
        route_order = day_route[day_key]

        elevator = _lookup(elevators, el_code)
        if not elevator:
            stats['skipped_missing'] += 1
            if len(missing_samples) < 20:
                missing_samples.append(f'{visit_code}: مصعد {el_code} غير موجود')
            continue

        contract = _lookup(contracts, cn_code) if cn_code else None
        technician = _lookup(technicians, tech_code) if tech_code else None

        visit_type = _map_visit_type(row[6] if len(row) > 6 else '')
        status = 'مكتملة' if force_completed else _map_status(row[9] if len(row) > 9 else '')
        if force_completed:
            status = 'مكتملة'
        visit_time = _str(row[8] if len(row) > 8 else '') or None
        notes = _compose_notes(row)
        plan_month = visit_date.strftime('%Y-%m')
        works = _str(row[10] if len(row) > 10 else '')
        observations = _str(row[16] if len(row) > 16 else '')

        existing = existing_by_code.get(visit_code.upper())
        if existing:
            if update_existing:
                if dry_run:
                    stats['updated'] += 1
                    continue
                existing.contract_id = contract.id if contract else existing.contract_id
                existing.elevator_id = elevator.id
                if technician:
                    existing.technician_id = technician.id
                existing.visit_type = visit_type
                existing.visit_date = visit_date
                existing.visit_time = visit_time
                existing.status = status
                existing.plan_month = plan_month
                existing.route_order = route_order
                if works:
                    existing.works_done = works
                if observations:
                    existing.observations = observations
                if notes:
                    existing.notes = notes
                if status == 'مكتملة' and not existing.completed_at:
                    existing.completed_at = datetime.utcnow()
                stats['updated'] += 1
                continue
            if skip_existing:
                stats['skipped_existing'] += 1
                continue

        if dry_run:
            stats['imported'] += 1
            continue

        visit = MaintenanceVisit(
            code=visit_code,
            contract_id=contract.id if contract else None,
            elevator_id=elevator.id,
            technician_id=technician.id if technician else None,
            visit_type=visit_type,
            visit_date=visit_date,
            visit_time=visit_time,
            status=status,
            plan_month=plan_month,
            route_order=route_order,
            works_done=works or None,
            observations=observations or None,
            notes=notes or None,
            completed_at=datetime.utcnow() if status == 'مكتملة' else None,
        )
        assign_organization(visit)
        db.session.add(visit)
        existing_by_code[visit_code.upper()] = visit
        stats['imported'] += 1

    if not dry_run:
        db.session.commit()

    stats['missing_samples'] = missing_samples
    stats['plan_days'] = len(day_route)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Import maintenance visits from Excel')
    parser.add_argument('xlsx', help='Path to Excel file')
    parser.add_argument('--slug', default='jama', help='Organization slug')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--force', action='store_true', help='Import even if visit code exists (create duplicate risk)')
    parser.add_argument('--update-existing', action='store_true',
                        help='Update existing visit codes instead of skipping')
    parser.add_argument('--keep-status', action='store_true',
                        help='Keep Excel status instead of forcing مكتملة')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    from flask import g
    from models import Organization

    with app.app_context():
        slug = (args.slug or 'jama').strip().lower()
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
            return 1
        g.organization = org
        g.organization_id = org.id
        print(f'Tenant: {org.name} ({org.slug}) id={org.id}')

        result = import_visits(
            args.xlsx,
            dry_run=args.dry_run,
            skip_existing=not args.force,
            force_completed=not args.keep_status,
            update_existing=args.update_existing,
        )
        print(f"Rows in file: {result['rows']}")
        if args.dry_run:
            print(f"Dry run: would import {result['imported']} / update {result['updated']}")
        else:
            print(f"Imported: {result['imported']}")
            print(f"Updated: {result['updated']}")
        print(f"Skipped (existing): {result['skipped_existing']}")
        print(f"Skipped (missing elevator): {result['skipped_missing']}")
        print(f"Skipped (non-routine / faults): {result['skipped_fault']}")
        print(f"Errors: {result['errors']}")
        print(f"Plan days organized: {result.get('plan_days', 0)}")
        print('\n=== النتيجة — زيارات الصيانة الدورية ===')
        print(f"  مستوردة: {result['imported']}")
        print(f"  محدّثة: {result['updated']}")
        print(f"  موجودة مسبقاً: {result['skipped_existing']}")
        print(f"  مصعد ناقص: {result['skipped_missing']}")
        if result.get('missing_samples'):
            print('Missing samples:')
            for line in result['missing_samples']:
                print(' ', line)
        if not args.dry_run:
            print('  visits in tenant:', MaintenanceVisit.query.filter_by(organization_id=org.id).count())
            done = MaintenanceVisit.query.filter_by(organization_id=org.id, status='مكتملة').count()
            print('  completed in tenant:', done)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
