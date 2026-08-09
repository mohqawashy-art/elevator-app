#!/usr/bin/env python3
"""إضافة مصعد EL-0043 لعميل «عبد الرحمن باقيس» (موجود مسبقاً) وربطه بعقد CN-00043 إن وُجد.

يفترض أن EL-0043 شاغر (بعد تشغيل shift_elevator_codes.py --from 43).

  cd ~/liftcore/jama-elevator-app
  source .venv/bin/activate
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/add_elevator_baqees_43.py --slug jama --dry-run
  python scripts/add_elevator_baqees_43.py --slug jama --yes
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CUSTOMER_NAME = 'عبد الرحمن باقيس'
ELEVATOR_CODE = 'EL-0043'
CONTRACT_CODE = 'CN-00043'  # العقد القديم لنفس العميل


def main() -> int:
    parser = argparse.ArgumentParser(description='إضافة EL-0043 لعبد الرحمن باقيس')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL غير مضبوط')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes للتأكيد أو --dry-run للمعاينة')
        return 2

    from flask import g
    from app import app, sync_customer_from_elevators
    from models import Contract, ContractElevator, Customer, Elevator, Organization, db
    from tenant_scope import assign_organization

    with app.app_context():
        slug = (args.slug or 'jama').strip().lower()
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
            return 1
        g.organization = org
        g.organization_id = org.id
        print(f'Tenant: {org.name} ({org.slug})')

        existing = Elevator.query.filter_by(
            organization_id=org.id, code=ELEVATOR_CODE
        ).first()
        if existing:
            cust = existing.customer.name if existing.customer else '—'
            print(f'ERROR: {ELEVATOR_CODE} موجود مسبقاً (عميل: {cust})')
            print('شغّل أولاً: python scripts/shift_elevator_codes.py --slug jama --from 43 --yes')
            return 1

        customers = (
            Customer.query.filter_by(organization_id=org.id)
            .filter(Customer.name.contains(CUSTOMER_NAME))
            .order_by(Customer.id)
            .all()
        )
        if not customers:
            print(f'ERROR: لم يُعثر على عميل باسم «{CUSTOMER_NAME}»')
            return 1
        if len(customers) > 1:
            print(f'تحذير: وُجد {len(customers)} عملاء مطابقين — يُستخدم الأول:')
            for c in customers:
                print(f'  id={c.id} code={c.code} name={c.name}')
        customer = customers[0]
        print(f'عميل: id={customer.id} code={customer.code} name={customer.name}')

        # انسخ مواصفات من مصعد آخر لنفس العميل إن وُجد، مع قيم عقد CN-00043 من المصدر
        sibling = (
            Elevator.query.filter_by(organization_id=org.id, customer_id=customer.id)
            .order_by(Elevator.code)
            .first()
        )
        contract = Contract.query.filter_by(
            organization_id=org.id, code=CONTRACT_CODE
        ).first()
        if contract:
            print(f'عقد للربط: {contract.code} status={contract.status}')
        else:
            print(f'تحذير: العقد {CONTRACT_CODE} غير موجود — سيُضاف المصعد بدون ربط عقد')

        # مواصفات من سجل CN-00043 في ملف المصاعد: نصف اتوماتيك، 5 وقفات، 630 كجم
        elev_type = 'نصف اتوماتيك'
        stops = 5
        capacity_kg = 630
        status = 'نشط'
        building = CUSTOMER_NAME
        city = (sibling.city if sibling else '') or (customer.city or '')
        district = (sibling.district if sibling else '') or (customer.district or '')
        address = (sibling.address if sibling else '') or (customer.address or '')
        brand = sibling.brand if sibling else ''
        machine_type = sibling.machine_type if sibling else ''
        door_type = 'نصف أوتوماتيك'

        print('سيُضاف:')
        print(f'  code={ELEVATOR_CODE}')
        print(f'  building_name={building}')
        print(f'  elev_type={elev_type} stops={stops} capacity_kg={capacity_kg}')
        print(f'  city={city or "—"} district={district or "—"}')
        print(f'  link_contract={CONTRACT_CODE if contract else "—"}')

        if args.dry_run:
            print('معاينة فقط — لم يُضف شيء')
            return 0

        elev = Elevator(
            code=ELEVATOR_CODE,
            customer_id=customer.id,
            building_name=building,
            city=city,
            district=district,
            address=address,
            elev_type=elev_type,
            brand=brand or None,
            capacity_kg=capacity_kg,
            stops=stops,
            floors=stops,
            machine_type=machine_type or None,
            door_type=door_type,
            status=status,
            notes=f'مضاف يدوياً — مربوط بعقد {CONTRACT_CODE}' if contract else 'مضاف يدوياً',
        )
        assign_organization(elev)
        db.session.add(elev)
        db.session.flush()

        if contract:
            exists_link = ContractElevator.query.filter_by(
                contract_id=contract.id, elevator_id=elev.id
            ).first()
            if not exists_link:
                link = ContractElevator(contract_id=contract.id, elevator_id=elev.id)
                assign_organization(link)
                db.session.add(link)

        if sync_customer_from_elevators:
            try:
                sync_customer_from_elevators(customer)
            except Exception as exc:
                print(f'تحذير sync_customer_from_elevators: {exc}')

        db.session.commit()
        print(f'تم: أُضيف {ELEVATOR_CODE} id={elev.id} لعميل {customer.name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
