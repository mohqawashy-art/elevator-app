#!/usr/bin/env python3
"""تفريغ حقل اسم المبنى لكل مصاعد مستأجر (افتراضي: jama).

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/clear_tenant_elevator_buildings.py --slug jama --dry-run
  python scripts/clear_tenant_elevator_buildings.py --slug jama --yes
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description='Clear elevator building_name for a tenant')
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
    from models import Elevator, Organization

    slug = (args.slug or 'jama').strip().lower()
    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1

        g.organization = org
        g.organization_id = org.id

        rows = (
            Elevator.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .order_by(Elevator.code)
            .all()
        )
        filled = [e for e in rows if (e.building_name or '').strip()]
        print(f'==> {org.name} ({org.slug}) id={org.id}')
        print(f'مصاعد: {len(rows)} — فيها اسم مبنى: {len(filled)}')

        if args.dry_run:
            for e in filled[:12]:
                print(f'  {e.code}: «{(e.building_name or "").strip()}»')
            if len(filled) > 12:
                print(f'  ... و {len(filled) - 12} أخرى')
            print('DRY-RUN — بدون تعديل')
            return 0

        for e in rows:
            e.building_name = ''
        db.session.commit()
        remaining = sum(
            1
            for e in (
                Elevator.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=org.id)
                .all()
            )
            if (e.building_name or '').strip()
        )
        print(f'تم تفريغ {len(rows)} مصعد — المتبقي باسم مبنى: {remaining}')
        return 0 if remaining == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
