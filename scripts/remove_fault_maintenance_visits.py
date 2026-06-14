#!/usr/bin/env python3
"""حذف زيارات الصيانة من نوع «عطل» — تبقى في صفحة الأعطال فقط.

الاستخدام:
  export DATABASE_URL="sqlite:////path/to/jama.db"
  python scripts/remove_fault_maintenance_visits.py --dry-run
  python scripts/remove_fault_maintenance_visits.py
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db  # noqa: E402
from models import Fault, MaintenanceVisit  # noqa: E402
from operations import is_fault_visit_type  # noqa: E402


def remove_fault_visits(*, dry_run: bool = False) -> dict:
    visits = [
        v for v in MaintenanceVisit.query.all()
        if is_fault_visit_type(v.visit_type)
    ]
    stats = {'found': len(visits), 'deleted': 0}

    for v in visits:
        if dry_run:
            stats['deleted'] += 1
            continue
        for fault in Fault.query.filter_by(visit_id=v.id).all():
            fault.visit_id = None
            if fault.id == v.fault_id:
                v.fault_id = None
        if v.fault_id:
            fault = Fault.query.get(v.fault_id)
            if fault and fault.visit_id == v.id:
                fault.visit_id = None
        db.session.delete(v)
        stats['deleted'] += 1

    if not dry_run:
        db.session.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Remove fault-type rows from maintenance visits')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    with app.app_context():
        result = remove_fault_visits(dry_run=args.dry_run)
        if args.dry_run:
            print(f"Found fault visits: {result['found']}")
            print(f"Dry run: would delete {result['deleted']}")
        else:
            print(f"Deleted: {result['deleted']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
