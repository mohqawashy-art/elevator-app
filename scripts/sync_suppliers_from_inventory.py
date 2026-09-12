#!/usr/bin/env python3
"""إنشاء سجلات الموردين من حقل supplier في أصناف المخزن.

  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/sync_suppliers_from_inventory.py --slug jama --dry-run
  python3 scripts/sync_suppliers_from_inventory.py --slug jama --yes
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description='Sync suppliers from inventory item names')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL — source /etc/liftcore/platform.env أولاً')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes للتنفيذ أو --dry-run للمعاينة')
        return 2

    from flask import g

    from app import app, db
    from models import InventoryItem, Organization, Supplier
    from supplier_prices import find_or_create_supplier
    from tenant_scope import assign_organization

    slug = (args.slug or 'jama').strip().lower()
    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1
        g.organization = org
        g.organization_id = org.id

        names = set()
        rows = (
            InventoryItem.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .all()
        )
        for item in rows:
            name = (item.supplier or '').strip()
            if name and name not in ('—', '-', 'لا يوجد'):
                names.add(name)

        before = (
            Supplier.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .count()
        )
        print(f'==> {org.name} ({slug})')
        print(f'موردون حالياً: {before} | أسماء في الأصناف: {len(names)}')
        for name in sorted(names):
            print(f'  - {name}')

        if args.dry_run:
            print('DRY-RUN')
            return 0

        created = 0
        for name in sorted(names):
            existing = (
                Supplier.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=org.id, name=name)
                .first()
            )
            if existing:
                continue
            find_or_create_supplier(name, assign_org_fn=assign_organization)
            created += 1

        db.session.commit()
        after = (
            Supplier.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .count()
        )
        print(f'تم: أُنشئ {created} مورد | الإجمالي الآن {after}')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
