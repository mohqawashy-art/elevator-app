#!/usr/bin/env python3
"""تشخيص: لماذا عقد/منطقة غير ظاهر في تخطيط الزيارات؟"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import Contract, ContractElevator
from operations import (
    _elevators_for_maintenance_plan,
    _is_maintenance_contract,
    _month_bounds,
    _periodic_visit_in_month,
    _visit_site_district,
    list_districts,
    plan_candidates_for_district,
)
from maintenance_teams import visit_site_district


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--contract', default='30', help='كود العقد أو جزء منه أو id')
    parser.add_argument('--district', default='جبل النور')
    parser.add_argument('--plan-month', default='')
    args = parser.parse_args()

    with app.app_context():
        today = date.today()
        ym = (args.plan_month or '').strip() or f'{today.year}-{today.month:02d}'
        year, month = map(int, ym.split('-', 1))
        start, end = _month_bounds(year, month)
        key = args.contract.strip()

        q = Contract.query
        if key.isdigit():
            rows = q.filter(db.or_(Contract.id == int(key), Contract.code.like(f'%{key}%'))).all()
        else:
            rows = q.filter(Contract.code.like(f'%{key}%')).all()

        print(f'plan_month={ym} district={args.district!r}')
        print(f'=== contracts matching {key!r}: {len(rows)} ===')
        for c in rows:
            cust = c.customer
            dist = visit_site_district(c, None, cust)
            maint = _is_maintenance_contract(c)
            elevs = _elevators_for_maintenance_plan(c)
            links = ContractElevator.query.filter_by(contract_id=c.id).count()
            active_month = c.start_date <= end and c.end_date >= start
            status_ok = (c.status or 'نشط') in ('نشط', '', 'على وشك الانتهاء')
            print(f'id={c.id} code={c.code} customer={cust.name if cust else "?"}')
            print(f'  type={c.contract_type!r} freq={c.maint_frequency!r} status={c.status!r}')
            print(f'  district={c.district!r} city={c.city!r}')
            print(f'  address={(c.address or "")[:100]!r}')
            print(f'  site_district={dist!r} maint={maint} active_month={active_month} status_ok={status_ok}')
            print(f'  elev_links={links} plan_elevs={[e.code for e in elevs]}')
            for e in elevs:
                d2 = _visit_site_district(c, e, cust)
                periodic = _periodic_visit_in_month(e.id, year, month)
                match = d2 == args.district
                print(f'    elev {e.code}: district={d2!r} match={match} already_planned={periodic}')
            print()

        dists = list_districts(ym)
        related = [d for d in dists if 'جبل' in d or 'نور' in d]
        print('districts (jabal):', related)
        print('exact district in list:', args.district in dists)
        cand = plan_candidates_for_district(ym, args.district)
        print('candidates count:', cand.get('count'))
        for row in cand.get('candidates') or []:
            print(' ', row.get('contract_code'), '|', row.get('customer'), '|', row.get('elevator_code'))


if __name__ == '__main__':
    main()
