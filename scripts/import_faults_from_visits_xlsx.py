#!/usr/bin/env python3
"""استيراد الأعطال من Excel زيارات جما — صفوف نوع الزيارة «عطل» فقط.

الاستخدام:
  export DATABASE_URL="sqlite:////path/to/jama.db"
  python scripts/import_faults_from_visits_xlsx.py deploy/data/jama_visits_14_6_2026.xlsx --dry-run
  python scripts/import_faults_from_visits_xlsx.py deploy/data/jama_visits_14_6_2026.xlsx

أو:
  bash deploy/import_jama_faults.sh
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')
for path in (ROOT, SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

import import_maintenance_visits_xlsx as vx  # noqa: E402

from app import app, db, next_code  # noqa: E402
from entity_links import link_fault_to_visit  # noqa: E402
from models import Elevator, Fault, MaintenanceVisit, Technician  # noqa: E402


def _parse_reported_at(date_val, time_val) -> datetime | None:
    d = vx._parse_date(date_val)
    if not d:
        return None
    t = vx._str(time_val)
    if not t:
        return datetime.combine(d, datetime.min.time())
    for fmt in ('%I:%M %p', '%I:%M%p', '%H:%M', '%H:%M:%S'):
        try:
            tm = datetime.strptime(t.replace(' ', ' ').strip(), fmt).time()
            return datetime.combine(d, tm)
        except ValueError:
            continue
    return datetime.combine(d, datetime.min.time())


def _map_fault_status(raw: str) -> str:
    s = vx._str(raw)
    if not s:
        return 'مفتوح'
    if 'اصلاح' in s or 'مكتمل' in s or 'محلول' in s:
        return 'تم الاصلاح'
    if 'انتظار' in s and 'قطع' in s:
        return 'انتظار قطع'
    if 'قيد' in s or 'جار' in s or 'جاري' in s:
        return 'قيد المعالجة'
    if 'مغلق' in s or 'ملغ' in s:
        return 'مغلق'
    return 'مفتوح'


def _is_fault_row(row: tuple) -> bool:
    return vx._str(row[6] if len(row) > 6 else '') == 'عطل'


def _compose_notes(row: tuple) -> str:
    parts = []
    mapping = (
        (10, 'تقرير'),
        (16, 'توصيات'),
        (17, 'قطع الغيار'),
        (22, 'ضمان'),
    )
    for i, label in mapping:
        val = vx._str(row[i]) if i < len(row) else ''
        if val:
            parts.append(f'{label}: {val}')
    return '\n'.join(parts)


def _compose_resolution(row: tuple) -> str:
    parts = []
    mapping = (
        (20, 'التشخيص'),
        (21, 'الإجراء'),
    )
    for i, label in mapping:
        val = vx._str(row[i]) if i < len(row) else ''
        if val:
            parts.append(f'{label}: {val}')
    report = vx._str(row[10] if len(row) > 10 else '')
    if report and not parts:
        return report
    return '\n'.join(parts)


def load_fault_rows(path: str) -> list[tuple]:
    return [row for row in vx.load_rows(path) if _is_fault_row(row)]


def import_faults(path: str, *, dry_run: bool = False, skip_existing: bool = True) -> dict:
    rows = load_fault_rows(path)
    stats = {
        'rows': len(rows),
        'imported': 0,
        'skipped_existing': 0,
        'skipped_missing': 0,
        'errors': 0,
    }
    missing_samples: list[str] = []

    elevators = vx._build_index(Elevator, 'EL')
    technicians = vx._build_index(Technician, 'Tech')
    visits_by_code = {
        v.code.upper(): v
        for v in MaintenanceVisit.query.all()
        if v.code
    }
    visits_with_fault = {
        v.id
        for v in MaintenanceVisit.query.filter(MaintenanceVisit.fault_id.isnot(None)).all()
    }
    fault_visit_ids = {
        f.visit_id
        for f in Fault.query.filter(Fault.visit_id.isnot(None)).all()
    }

    for row in rows:
        visit_code = vx._norm_visit_code(row[1] if len(row) > 1 else '')
        el_code = vx._pick_elevator_code(row[4] if len(row) > 4 else '', row[10] if len(row) > 10 else '')
        tech_code = vx._pick_technician_code(row[5] if len(row) > 5 else '')
        reported_at = _parse_reported_at(row[7] if len(row) > 7 else '', row[8] if len(row) > 8 else '')

        if not el_code or not reported_at:
            stats['errors'] += 1
            continue

        visit = visits_by_code.get(visit_code.upper()) if visit_code else None
        if skip_existing and visit:
            if visit.id in visits_with_fault or visit.id in fault_visit_ids:
                stats['skipped_existing'] += 1
                continue

        elevator = vx._lookup(elevators, el_code)
        if not elevator:
            stats['skipped_missing'] += 1
            if len(missing_samples) < 15:
                label = visit_code or el_code
                missing_samples.append(f'{label}: مصعد {el_code} غير موجود')
            continue

        technician = vx._lookup(technicians, tech_code) if tech_code else None
        client_report = vx._str(row[18] if len(row) > 18 else '') or vx._str(row[13] if len(row) > 13 else '')
        fault_type = vx._str(row[19] if len(row) > 19 else '') or 'عطل'
        status = _map_fault_status(row[9] if len(row) > 9 else '')
        parts_text = vx._str(row[17] if len(row) > 17 else '')
        notes = _compose_notes(row)
        resolution = _compose_resolution(row)
        tech_notes = vx._str(row[20] if len(row) > 20 else '')
        cn_code = vx._extract_code(row[3] if len(row) > 3 else '') or vx._extract_code(row[0] if len(row) > 0 else '')
        meta = []
        if visit_code:
            meta.append(f'زيارة: {visit_code}')
        if cn_code:
            meta.append(f'عقد: {cn_code}')
        if meta:
            notes = '\n'.join([notes] + meta) if notes else '\n'.join(meta)

        if dry_run:
            stats['imported'] += 1
            continue

        fault = Fault(
            code=next_code(Fault, 'FA-', digits=5),
            elevator_id=elevator.id,
            technician_id=technician.id if technician else None,
            fault_type=fault_type,
            description=client_report or resolution or fault_type,
            client_report=client_report or None,
            tech_notes=tech_notes or None,
            needs_parts=bool(parts_text),
            priority='عادية',
            reported_at=reported_at,
            status=status,
            resolution=resolution or None,
            notes=notes or None,
            resolved_at=reported_at if status == 'تم الاصلاح' else None,
        )
        db.session.add(fault)
        db.session.flush()

        if visit:
            link_fault_to_visit(fault, visit)
            visits_with_fault.add(visit.id)
            fault_visit_ids.add(visit.id)

        stats['imported'] += 1

    if not dry_run:
        db.session.commit()

    stats['missing_samples'] = missing_samples
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Import faults from visits Excel (عطل rows only)')
    parser.add_argument('xlsx', help='Path to Excel file')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--force', action='store_true', help='Import even if visit already has a fault')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    with app.app_context():
        result = import_faults(
            args.xlsx,
            dry_run=args.dry_run,
            skip_existing=not args.force,
        )
        print(f"Fault rows in file: {result['rows']}")
        if args.dry_run:
            print(f"Dry run: would import {result['imported']}")
        else:
            print(f"Imported: {result['imported']}")
        print(f"Skipped (existing): {result['skipped_existing']}")
        print(f"Skipped (missing elevator): {result['skipped_missing']}")
        print(f"Errors: {result['errors']}")
        if result.get('missing_samples'):
            print('Missing samples:')
            for line in result['missing_samples']:
                print(' ', line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
