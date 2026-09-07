#!/usr/bin/env python3
"""مسح بيانات المصاعد لمستأجر: المصاعد، روابط العقود، الزيارات والأعطال المرتبطة.

  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/clear_tenant_elevators.py --slug jama --dry-run
  python scripts/clear_tenant_elevators.py --slug jama --yes --confirm CLEAR_ELEVATORS
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

CONFIRM_TOKEN = 'CLEAR_ELEVATORS'


def main() -> int:
    parser = argparse.ArgumentParser(description='Clear tenant elevator data')
    parser.add_argument('--slug', default='jama', help='Organization slug')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--confirm', default='')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL — source /etc/liftcore/platform.env أولاً')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes --confirm CLEAR_ELEVATORS للتنفيذ أو --dry-run للمعاينة')
        return 2
    if args.yes and args.confirm != CONFIRM_TOKEN:
        print(f'ERROR: --confirm يجب أن يكون {CONFIRM_TOKEN}')
        return 2

    from flask import g

    from app import app
    from models import Elevator, Fault, MaintenanceVisit, Organization
    from replace_tenant_elevators_from_xlsx import _delete_tenant_elevators

    slug = (args.slug or 'jama').strip().lower()
    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1
        g.organization = org
        g.organization_id = org.id

        before_e = Elevator.query.filter_by(organization_id=org.id).count()
        before_v = MaintenanceVisit.query.filter_by(organization_id=org.id).count()
        before_f = Fault.query.filter_by(organization_id=org.id).count()
        print(f'==> {org.name} ({slug}) id={org.id}')
        print(f'قبل: مصاعد {before_e} | زيارات {before_v} | أعطال {before_f}')

        stats = _delete_tenant_elevators(org.id, dry_run=args.dry_run)
        print('==> مسح')
        for k, v in stats.items():
            print(f'  {k}: {v}')

        after_e = Elevator.query.filter_by(organization_id=org.id).count()
        after_v = MaintenanceVisit.query.filter_by(organization_id=org.id).count()
        after_f = Fault.query.filter_by(organization_id=org.id).count()
        print(f'بعد: مصاعد {after_e} | زيارات {after_v} | أعطال {after_f}')
        if args.dry_run:
            print('DRY-RUN — بدون تعديل')
        return 0 if after_e == 0 or args.dry_run else 1


if __name__ == '__main__':
    raise SystemExit(main())
