#!/usr/bin/env python3
"""تعيين تكرار الصيانة «شهري» وإعادة حساب إجمالي الزيارات لكل العقود.

  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/set_contracts_monthly_frequency.py --slug jama --dry-run
  python scripts/set_contracts_monthly_frequency.py --slug jama --yes
"""
from __future__ import annotations

import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MONTHLY = 'شهري'
CONFIRM_TOKEN = 'SET_MONTHLY_FREQ'


def _duration_months(contract) -> int:
    dm = int(getattr(contract, 'duration_months', None) or 0)
    if dm > 0:
        return dm
    start = getattr(contract, 'start_date', None)
    end = getattr(contract, 'end_date', None)
    if start and end and end > start:
        return max(1, (end.year - start.year) * 12 + (end.month - start.month))
    return 12


def _total_visits_for_monthly(contract) -> int:
    """إجمالي زيارات العقد عند التكرار الشهري = عدد أشهر مدة العقد."""
    return max(1, _duration_months(contract))


def main() -> int:
    parser = argparse.ArgumentParser(description='Set all contracts to monthly maintenance frequency')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--confirm', default='')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL — source /etc/liftcore/platform.env أولاً')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes --confirm SET_MONTHLY_FREQ للتنفيذ أو --dry-run للمعاينة')
        return 2
    if args.yes and args.confirm != CONFIRM_TOKEN:
        print(f'ERROR: --confirm يجب أن يكون {CONFIRM_TOKEN}')
        return 2

    from flask import g

    from app import app, db
    from models import Contract, Organization

    slug = (args.slug or 'jama').strip().lower()
    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1
        g.organization = org
        g.organization_id = org.id

        contracts = Contract.query.filter_by(organization_id=org.id).order_by(Contract.id).all()
        updated = 0
        already = 0
        samples: list[str] = []

        for c in contracts:
            months = _duration_months(c)
            visits = _total_visits_for_monthly(c)
            freq = (c.maint_frequency or '').strip()
            old_visits = int(c.visits_per_month or 0)
            if freq == MONTHLY and old_visits == visits:
                already += 1
                continue
            if len(samples) < 8:
                samples.append(
                    f'{c.code}: {freq or "—"} / زيارات {old_visits} → {MONTHLY} / {visits}'
                )
            if not args.dry_run:
                c.maint_frequency = MONTHLY
                c.visits_per_month = visits
                if not c.duration_months:
                    c.duration_months = months
            updated += 1

        print(f'==> {org.name} ({slug}) — عقود: {len(contracts)}')
        print(f'سيُحدَّث: {updated} | كان شهري مسبقاً: {already}')
        for line in samples:
            print(f'  {line}')
        if updated > len(samples):
            print(f'  ... و {updated - len(samples)} أخرى')

        if not args.dry_run:
            db.session.commit()
            print('تم الحفظ.')
        else:
            print('DRY-RUN — بدون تعديل')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
