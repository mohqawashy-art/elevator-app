#!/usr/bin/env python3
"""تصحيح حقل المبنى للمصاعد التي تشترك بنفس اسم العميل فقط.

مثال: 6 مصاعد لـ «حمدي حمدان الوافي» كلها building_name = اسم العميل
→ يصبح: حمدي حمدان الوافي — EL-0054

الاستخدام:
  python scripts/fix_elevator_building_labels.py --dry-run
  python scripts/fix_elevator_building_labels.py
  python scripts/fix_elevator_building_labels.py --customer "حمدي حمدان الوافي"
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import Customer, Elevator


def fix_labels(*, customer_name: str = '', dry_run: bool = False) -> dict:
    stats = {'customers': 0, 'updated': 0, 'skipped': 0}
    q = Customer.query
    if customer_name:
        q = q.filter(Customer.name.contains(customer_name.strip()))
    for customer in q.order_by(Customer.id).all():
        elevs = (
            Elevator.query.filter_by(customer_id=customer.id)
            .order_by(Elevator.code)
            .all()
        )
        if len(elevs) < 2:
            continue
        names = {(e.building_name or '').strip() for e in elevs}
        cust_name = (customer.name or '').strip()
        if len(names) != 1:
            stats['skipped'] += len(elevs)
            continue
        only = next(iter(names))
        if only != cust_name and only != '':
            stats['skipped'] += len(elevs)
            continue
        stats['customers'] += 1
        for elev in elevs:
            new_name = f'{cust_name} — {elev.code}'
            if (elev.building_name or '').strip() == new_name:
                stats['skipped'] += 1
                continue
            print(f'  {elev.code}: «{elev.building_name or "—"}» → «{new_name}»')
            if not dry_run:
                elev.building_name = new_name
            stats['updated'] += 1
    if not dry_run:
        db.session.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Fix duplicate elevator building_name labels')
    parser.add_argument('--customer', default='', help='جزء من اسم العميل للتصفية')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    with app.app_context():
        stats = fix_labels(customer_name=args.customer, dry_run=args.dry_run)
        print('\n=== النتيجة ===')
        for k, v in stats.items():
            print(f'  {k}: {v}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
