#!/usr/bin/env python3
"""تصفير عروض سعر الصيانة لمستأجر.

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/clear_maintenance_quotes.py --slug default --dry-run
  python scripts/clear_maintenance_quotes.py --slug default --confirm CLEAR_MQ
  python scripts/clear_maintenance_quotes.py --slug default --confirm CLEAR_MQ --include-contracts
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CONFIRM = 'CLEAR_MQ'


def main() -> int:
    parser = argparse.ArgumentParser(description='تصفير عروض صيانة مستأجر')
    parser.add_argument('--slug', default='default')
    parser.add_argument('--confirm', default='')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument(
        '--include-contracts',
        action='store_true',
        help='حذف العروض المقبولة المرتبطة بعقود أيضاً (العقود تبقى)',
    )
    parser.add_argument('--list', action='store_true', help='عرض المستأجرين وعدد العروض')
    parser.add_argument('--all-orgs', action='store_true', help='تصفير كل المستأجرين')
    args = parser.parse_args()

    from app import app, db
    from flask import g
    from models import MaintenanceQuote, Organization
    from sales.service import clear_maintenance_quotes

    with app.app_context():
        if args.list:
            for org in Organization.query.order_by(Organization.slug).all():
                n = (
                    MaintenanceQuote.query.execution_options(skip_tenant=True)
                    .filter_by(organization_id=org.id)
                    .count()
                )
                print(f'{org.slug}\tid={org.id}\tquotes={n}')
            return 0

        if args.all_orgs:
            if args.dry_run:
                print('dry-run all orgs — no changes')
                return 0
            if (args.confirm or '').strip() != CONFIRM:
                print(f'ERROR: pass --confirm {CONFIRM}')
                return 1
            total = 0
            for org in Organization.query.order_by(Organization.slug).all():
                g.organization_id = org.id
                n = clear_maintenance_quotes(include_with_contract=bool(args.include_contracts))
                total += n
                print(f'{org.slug}: deleted={n}')
            db.session.commit()
            print(f'total_deleted={total}')
            return 0

    slug = (args.slug or 'default').strip().lower()

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: org not found: {slug}')
            return 1
        g.organization_id = org.id

        before = (
            MaintenanceQuote.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .count()
        )
        print(f'org={slug} id={org.id} maintenance_quotes={before}')

        if args.dry_run:
            print('dry-run — no changes')
            return 0

        if (args.confirm or '').strip() != CONFIRM:
            print(f'ERROR: pass --confirm {CONFIRM}')
            return 1

        n = clear_maintenance_quotes(include_with_contract=bool(args.include_contracts))
        db.session.commit()
        after = (
            MaintenanceQuote.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .count()
        )
        print(f'deleted={n} remaining={after}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
