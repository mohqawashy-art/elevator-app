#!/usr/bin/env python3
"""حذف مستندات رصيد أول المدة (OS) وإعادة حساب أرصدة الأصناف.

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/reset_tenant_opening_stock.py --slug jama --dry-run
  python3 scripts/reset_tenant_opening_stock.py --slug jama --yes --confirm RESET_OPENING_STOCK
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CONFIRM_TOKEN = 'RESET_OPENING_STOCK'


def _opening_movement_filter(query):
    from inventory_warehouse import MOVEMENT_OPENING, OPENING_DOC_REF_PREFIX
    from models import StockMovement

    return query.filter(
        StockMovement.movement_type == MOVEMENT_OPENING,
        StockMovement.reference.like(f'{OPENING_DOC_REF_PREFIX}%'),
    )


def recalculate_qty_from_movements(org_id: int) -> dict[int, float]:
    from models import InventoryItem, StockMovement

    qty_by_item: dict[int, float] = defaultdict(float)
    rows = (
        StockMovement.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=org_id)
        .with_entities(StockMovement.item_id, StockMovement.direction, StockMovement.quantity)
        .all()
    )
    for item_id, direction, quantity in rows:
        qty = float(quantity or 0)
        if direction == 'وارد':
            qty_by_item[int(item_id)] += qty
        else:
            qty_by_item[int(item_id)] -= qty
    return qty_by_item


def main() -> int:
    parser = argparse.ArgumentParser(description='Reset tenant opening stock (OS documents)')
    parser.add_argument('--slug', default='jama', help='Organization slug')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--confirm', default='')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL — source /etc/liftcore/platform.env أولاً')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes --confirm RESET_OPENING_STOCK للتنفيذ أو --dry-run للمعاينة')
        return 2
    if args.yes and (args.confirm or '').strip() != CONFIRM_TOKEN:
        print(f'ERROR: --confirm يجب أن يكون {CONFIRM_TOKEN}')
        return 2

    from flask import g

    from app import app, db
    from inventory_warehouse import MOVEMENT_OPENING
    from models import InventoryItem, Organization, StockMovement

    slug = (args.slug or 'jama').strip().lower()
    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1

        g.organization = org
        g.organization_id = org.id

        opening_q = _opening_movement_filter(
            StockMovement.query.execution_options(skip_tenant=True).filter_by(organization_id=org.id)
        )
        opening_rows = opening_q.all()
        opening_qty = round(sum(float(m.quantity or 0) for m in opening_rows), 4)
        doc_codes = sorted({
            (m.reference or '').split(':')[1]
            for m in opening_rows
            if (m.reference or '').startswith('opening:') and ':item:' in (m.reference or '')
        })

        items = (
            InventoryItem.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .all()
        )
        qty_before = round(sum(float(i.current_qty or 0) for i in items), 4)

        print(f'==> {org.name} ({slug}) id={org.id}')
        print(f'مستندات OS: {len(doc_codes)} | حركات رصيد افتتاحي: {len(opening_rows)}')
        print(f'كمية رصيد أول المدة: {opening_qty:g}')
        print(f'إجمالي أرصدة الأصناف الآن: {qty_before:g}')
        if doc_codes[:8]:
            print('أرقام مستندات:', ', '.join(doc_codes[:8]) + (' …' if len(doc_codes) > 8 else ''))

        if args.dry_run:
            projected = recalculate_qty_from_movements(org.id)
            for m in opening_rows:
                projected[int(m.item_id)] -= float(m.quantity or 0)
            total_after = round(sum(projected.get(i.id, float(i.current_qty or 0)) for i in items), 4)
            print('DRY-RUN — سيتم: حذف حركات OS + إعادة حساب current_qty من باقي الحركات')
            print(f'إجمالي الأرصدة المتوقع بعد التصفير: {total_after:g}')
            return 0

        deleted = opening_q.delete(synchronize_session=False)
        projected = recalculate_qty_from_movements(org.id)
        updated = 0
        negative = []
        for item in items:
            new_qty = round(float(projected.get(item.id, 0.0)), 4)
            if new_qty < -1e-9:
                negative.append((item.code, item.name, new_qty))
            if float(item.current_qty or 0) != new_qty:
                item.current_qty = new_qty
                updated += 1

        db.session.commit()

        qty_after = round(
            float(
                db.session.query(db.func.coalesce(db.func.sum(InventoryItem.current_qty), 0))
                .execution_options(skip_tenant=True)
                .filter(InventoryItem.organization_id == org.id)
                .scalar()
                or 0
            ),
            4,
        )
        opening_left = _opening_movement_filter(
            StockMovement.query.execution_options(skip_tenant=True).filter_by(organization_id=org.id)
        ).count()

        print('')
        print(f'تم: حذف {deleted} حركة رصيد افتتاحي ({MOVEMENT_OPENING})')
        print(f'تحديث {updated} صنف | مستندات OS متبقية: {opening_left}')
        print(f'إجمالي الأرصدة بعد التصفير: {qty_after:g}')
        if negative:
            print('تحذير — أرصدة سالبة بعد إعادة الحساب:')
            for code, name, q in negative[:10]:
                print(f'  {code} {name}: {q:g}')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
