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


def fix_labels(
    *,
    customer_name: str = '',
    customer_code: str = '',
    dry_run: bool = False,
) -> dict:
    stats = {'customers': 0, 'updated': 0, 'skipped': 0, 'matched': 0}
    q = Customer.query
    if customer_code:
        q = q.filter(Customer.code == customer_code.strip())
    elif customer_name:
        q = q.filter(Customer.name.contains(customer_name.strip()))
    customers = q.order_by(Customer.id).all()
    stats['matched'] = len(customers)
    for customer in customers:
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
    parser.add_argument('--customer-code', default='', help='كود العميل مثل C-0051')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    with app.app_context():
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print(f'Database: {db_uri}')
        if 'jama.db' not in db_uri and os.environ.get('DATABASE_URL'):
            print('WARN: DATABASE_URL set but URI does not mention jama.db')
        elif not os.environ.get('DATABASE_URL'):
            print('WARN: DATABASE_URL not set — on jama server use:')
            print('  export DATABASE_URL=sqlite:///$HOME/liftcore/jama-elevator-app/instance/jama.db')
        stats = fix_labels(
            customer_name=args.customer,
            customer_code=args.customer_code,
            dry_run=args.dry_run,
        )
        if stats['matched'] == 0 and (args.customer or args.customer_code):
            print('لم يُعثر على عميل بهذا الاسم/الكود — تحقق من قاعدة البيانات أعلاه.')
        elif stats['matched'] and stats['customers'] == 0:
            print('وُجد عميل لكن لا مصاعد تحتاج تصحيح (أسماء مباني مختلفة أو مصعد واحد فقط).')
        print('\n=== النتيجة ===')
        for k, v in stats.items():
            print(f'  {k}: {v}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
