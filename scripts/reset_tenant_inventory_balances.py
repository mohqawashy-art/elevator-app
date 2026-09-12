#!/usr/bin/env python3
"""تصفير أرصدة المخزون وحذف حركاته — مع الإبقاء على الأصناف.

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/reset_tenant_inventory_balances.py --slug jama --dry-run
  python3 scripts/reset_tenant_inventory_balances.py --slug jama --yes --confirm RESET_INVENTORY
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CONFIRM_TOKEN = 'RESET_INVENTORY'


def main() -> int:
    parser = argparse.ArgumentParser(description='Reset tenant inventory balances and movements')
    parser.add_argument('--slug', default='jama', help='Organization slug')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--confirm', default='')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL — source /etc/liftcore/platform.env أولاً')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes --confirm RESET_INVENTORY للتنفيذ أو --dry-run للمعاينة')
        return 2
    if args.yes and (args.confirm or '').strip() != CONFIRM_TOKEN:
        print(f'ERROR: --confirm يجب أن يكون {CONFIRM_TOKEN}')
        return 2

    from flask import g

    from app import app, db
    from models import InventoryItem, Organization, StockMovement

    slug = (args.slug or 'jama').strip().lower()
    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1

        g.organization = org
        g.organization_id = org.id

        items = (
            InventoryItem.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .order_by(InventoryItem.code)
            .all()
        )
        movements = (
            StockMovement.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .all()
        )

        qty_before = sum(float(i.current_qty or 0) for i in items)
        nonzero = [i for i in items if float(i.current_qty or 0) != 0]

        print(f'==> {org.name} ({slug}) id={org.id}')
        print(f'أصناف: {len(items)} | حركات مخزن: {len(movements)}')
        print(f'إجمالي الكميات الحالية: {qty_before:g} | أصناف بها رصيد: {len(nonzero)}')

        if args.dry_run:
            print('DRY-RUN — سيتم: حذف كل حركات المخزن + تصفير current_qty لكل صنف')
            if nonzero[:5]:
                print('عينة أرصدة:')
                for i in nonzero[:5]:
                    print(f'  {i.code} {i.name}: {i.current_qty:g}')
            return 0

        deleted = (
            StockMovement.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .delete(synchronize_session=False)
        )
        zeroed = 0
        for item in items:
            if float(item.current_qty or 0) != 0:
                item.current_qty = 0
                zeroed += 1
            elif item.current_qty is None:
                item.current_qty = 0
                zeroed += 1

        db.session.commit()

        items_after = (
            InventoryItem.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .count()
        )
        mv_after = (
            StockMovement.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .count()
        )
        qty_after = (
            db.session.query(db.func.coalesce(db.func.sum(InventoryItem.current_qty), 0))
            .execution_options(skip_tenant=True)
            .filter(InventoryItem.organization_id == org.id)
            .scalar()
        )

        print('')
        print(f'تم: حذف {deleted} حركة | تصفير {zeroed} صنف')
        print(f'بعد: أصناف {items_after} | حركات {mv_after} | إجمالي الكميات {float(qty_after or 0):g}')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
