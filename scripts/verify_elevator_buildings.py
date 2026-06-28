#!/usr/bin/env python3
"""عرض أسماء المباني للمصاعد — للتحقق من قاعدة jama.db على السيرفر."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import Customer, Elevator


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify elevator building_name values')
    parser.add_argument('--customer', default='', help='جزء من اسم العميل')
    parser.add_argument('--customer-code', default='', help='كود العميل مثل C-0051')
    parser.add_argument('--limit', type=int, default=0, help='حد أقصى للصفوف (0 = الكل)')
    args = parser.parse_args()

    with app.app_context():
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print(f'Database: {db_uri}')
        if 'jama.db' not in db_uri:
            print('WARN: ليست jama.db — عيّن DATABASE_URL قبل التشغيل')

        q = Customer.query
        if args.customer_code:
            q = q.filter(Customer.code == args.customer_code.strip())
        elif args.customer:
            q = q.filter(Customer.name.contains(args.customer.strip()))

        customers = q.order_by(Customer.id).all()
        if not customers:
            print('لم يُعثر على عملاء.')
            return 1

        shown = 0
        for customer in customers:
            elevs = (
                Elevator.query.filter_by(customer_id=customer.id)
                .order_by(Elevator.code)
                .all()
            )
            if len(elevs) < 2:
                continue
            names = {(e.building_name or '').strip() for e in elevs}
            flag = '⚠ مكرر' if len(names) == 1 else '✓'
            print(f'\n{flag} {customer.code} — {customer.name} ({len(elevs)} مصعد)')
            for elev in elevs:
                print(f'  {elev.code}: «{elev.building_name or "—"}»')
                shown += 1
                if args.limit and shown >= args.limit:
                    return 0
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
