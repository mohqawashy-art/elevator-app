#!/usr/bin/env python3
"""تحديث ملاحظات الأعطال بربط الزيارة والعقد من Excel (للأعطال المستوردة سابقاً).

Usage:
  python scripts/backfill_fault_link_notes.py deploy/data/jama_visits_14_6_2026.xlsx --dry-run
  python scripts/backfill_fault_link_notes.py deploy/data/jama_visits_14_6_2026.xlsx
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')
for path in (ROOT, SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

import import_faults_from_visits_xlsx as fi  # noqa: E402
import import_maintenance_visits_xlsx as vx  # noqa: E402

from app import app, db  # noqa: E402
from models import Elevator, Fault  # noqa: E402


def _fault_key(elevator_id: int, reported_at) -> str:
    d = reported_at.date() if hasattr(reported_at, 'date') else reported_at
    return f'{elevator_id}:{d.isoformat()}'


def backfill(path: str, *, dry_run: bool = False) -> dict:
    rows = fi.load_fault_rows(path)
    elevators = vx._build_index(Elevator, 'EL')

    by_key: dict[str, Fault] = {}
    for f in Fault.query.all():
        if not f.elevator_id or not f.reported_at:
            continue
        by_key[_fault_key(f.elevator_id, f.reported_at)] = f

    stats = {'rows': len(rows), 'updated': 0, 'missing': 0}

    for row in rows:
        el_code = vx._pick_elevator_code(row[4] if len(row) > 4 else '', row[10] if len(row) > 10 else '')
        reported_at = fi._parse_reported_at(row[7] if len(row) > 7 else '', row[8] if len(row) > 8 else '')
        visit_code = vx._norm_visit_code(row[1] if len(row) > 1 else '')
        cn_code = vx._extract_code(row[3] if len(row) > 3 else '') or vx._extract_code(row[0] if len(row) > 0 else '')

        elevator = vx._lookup(elevators, el_code) if el_code else None
        if not elevator or not reported_at:
            stats['missing'] += 1
            continue

        fault = by_key.get(_fault_key(elevator.id, reported_at))
        if not fault:
            stats['missing'] += 1
            continue

        meta = []
        if visit_code:
            meta.append(f'زيارة: {visit_code}')
        if cn_code:
            meta.append(f'عقد: {cn_code}')
        if not meta:
            continue

        notes = fault.notes or ''
        changed = False
        for line in meta:
            if line not in notes:
                notes = f'{notes}\n{line}'.strip() if notes else line
                changed = True
        if not changed:
            continue

        if dry_run:
            stats['updated'] += 1
            continue

        fault.notes = notes
        stats['updated'] += 1

    if not dry_run:
        db.session.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill fault visit/contract notes from Excel')
    parser.add_argument('xlsx')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f'ERROR: file not found: {args.xlsx}')
        return 1

    with app.app_context():
        result = backfill(args.xlsx, dry_run=args.dry_run)
        print(f"Fault rows in file: {result['rows']}")
        print(f"{'Would update' if args.dry_run else 'Updated'}: {result['updated']}")
        print(f"Not matched: {result['missing']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
