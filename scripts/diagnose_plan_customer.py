#!/usr/bin/env python3
"""تشخيص: لماذا عميل/مصعد غير ظاهر في خطة شهر معيّن؟

الاستخدام:
  export DATABASE_URL="sqlite:///$HOME/liftcore/jama-elevator-app/instance/jama.db"
  python scripts/diagnose_plan_customer.py --plan-month 2026-07 --customer "حمدي"
  python scripts/diagnose_plan_customer.py --plan-month 2026-07 --customer-code C-0051
  python scripts/diagnose_plan_customer.py --plan-month 2026-07 --customer-code C-0051 --fix-tags
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import Contract, Customer, Elevator, MaintenanceVisit
from operations import (
    _is_maintenance_contract,
    _month_bounds,
    _parse_plan_month,
    _periodic_visit_in_month,
    _visits_for_plan_month,
    _visit_in_plan_month,
)


def _contracts_for_month(customer_id: int, year: int, month: int) -> list[Contract]:
    start, end = _month_bounds(year, month)
    rows = Contract.query.filter(
        Contract.customer_id == customer_id,
        Contract.start_date <= end,
        Contract.end_date >= start,
    ).order_by(Contract.end_date.desc()).all()
    return [c for c in rows if _is_maintenance_contract(c)]


def diagnose(*, plan_month: str, customer: Customer, fix_tags: bool = False) -> None:
    year, month = _parse_plan_month(plan_month)
    start, end = _month_bounds(year, month)
    elevs = Elevator.query.filter_by(customer_id=customer.id).order_by(Elevator.code).all()
    contracts = _contracts_for_month(customer.id, year, month)

    print(f'\n=== {customer.code} — {customer.name} ===')
    print(f'شهر الخطة: {plan_month} ({start} → {end})')
    print(f'المصاعد: {len(elevs)}')

    if not contracts:
        print('⚠ لا يوجد عقد صيانة نشط يغطي هذا الشهر.')
        all_c = Contract.query.filter_by(customer_id=customer.id).order_by(Contract.end_date.desc()).all()
        for c in all_c[:5]:
            maint = 'صيانة' if _is_maintenance_contract(c) else 'غير صيانة'
            print(
                f'  · {c.code} [{maint}] {c.start_date} → {c.end_date} — حالة: {c.status or "—"}'
            )
        print('  الحل: مدّد تاريخ انتهاء العقد أو أنشئ عقد صيانة جديد.')
    else:
        for c in contracts:
            print(
                f'✓ عقد {c.code}: {c.start_date} → {c.end_date} — {c.contract_type or "—"} / {c.maint_frequency or "—"}'
            )

    plan_visits = [
        v for v in _visits_for_plan_month(plan_month)
        if v.elevator and v.elevator.customer_id == customer.id
    ]
    print(f'زيارات في خطة {plan_month}: {len(plan_visits)}')

    fixed = 0
    for elev in elevs:
        in_plan = [v for v in plan_visits if v.elevator_id == elev.id]
        periodic = _periodic_visit_in_month(elev.id, year, month)
        if in_plan:
            for v in in_plan:
                print(
                    f'  ✓ {elev.code}: {v.code} {v.visit_date} plan_month={v.plan_month or "—"}'
                )
            continue

        if periodic:
            pm = (periodic.plan_month or '').strip()
            wrong_tag = pm and pm != plan_month and _visit_in_plan_month(periodic.visit_date, plan_month)
            if wrong_tag:
                print(
                    f'  ⚠ {elev.code}: زيارة {periodic.code} بتاريخ {periodic.visit_date} '
                    f'موسومة بخطة {pm} بدل {plan_month}'
                )
                if fix_tags:
                    periodic.plan_month = plan_month
                    fixed += 1
            else:
                print(
                    f'  ⚠ {elev.code}: زيارة دورية {periodic.code} {periodic.visit_date} '
                    f'خارج عرض الخطة (plan_month={pm or "—"})'
                )
        else:
            print(f'  ✗ {elev.code}: لا زيارة دورية في {plan_month} — شغّل «تشغيل الخطة»')

    if fix_tags and fixed:
        db.session.commit()
        print(f'\nتم تصحيح وسوم plan_month لـ {fixed} زيارة.')
    elif fix_tags:
        print('\nلا وسوم للتصحيح.')


def main() -> int:
    parser = argparse.ArgumentParser(description='Diagnose customer in maintenance plan month')
    parser.add_argument('--plan-month', required=True, help='مثل 2026-07')
    parser.add_argument('--customer', default='')
    parser.add_argument('--customer-code', default='')
    parser.add_argument('--fix-tags', action='store_true', help='إصلاح زيارات بتاريخ الشهر ووسم خطة خاطئ')
    args = parser.parse_args()

    with app.app_context():
        print('Database:', app.config.get('SQLALCHEMY_DATABASE_URI', ''))
        q = Customer.query
        if args.customer_code:
            q = q.filter(Customer.code == args.customer_code.strip())
        elif args.customer:
            q = q.filter(Customer.name.contains(args.customer.strip()))
        else:
            print('حدد --customer أو --customer-code')
            return 1

        customers = q.order_by(Customer.id).all()
        if not customers:
            print('لم يُعثر على عميل.')
            return 1
        for customer in customers:
            diagnose(plan_month=args.plan_month, customer=customer, fix_tags=args.fix_tags)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
