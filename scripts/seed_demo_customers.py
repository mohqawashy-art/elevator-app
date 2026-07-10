#!/usr/bin/env python3
"""إضافة عملاء تجريبيين داخل مؤسسة موجودة (صفحة /clients) — ليس مؤسسات المنصة.

  # على السيرفر — مؤسسة default (app.liftcoreapp.com):
  export DATABASE_URL="$(sudo grep '^DATABASE_URL=' /etc/liftcore/platform.env | cut -d= -f2-)"
  python3 scripts/seed_demo_customers.py --slug default

  # مؤسسة جما:
  python3 scripts/seed_demo_customers.py --slug jama

  # عرض فقط بدون إضافة:
  python3 scripts/seed_demo_customers.py --slug default --list
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# عملاء تجريبيون — أكواد DEMO-xx حتى لا تتعارض مع بيانات حقيقية
DEMO_CUSTOMERS = (
    dict(code='DEMO-01', name='برج الياسمين', city='مكة', district='العزيزية',
         address='شارع الأمير سلطان', phone='0501111001', entity_type='شركة'),
    dict(code='DEMO-02', name='مجمع النخيل', city='مكة', district='طريق المدينة',
         address='طريق مكة المدينة', phone='0501111002', entity_type='شركة'),
    dict(code='DEMO-03', name='فندق الأندلس', city='مكة', district='العبدية',
         address='حي العبدية', phone='0501111003', entity_type='شركة'),
    dict(code='DEMO-04', name='مستشفى السلام', city='مكة', district='النزهة',
         address='حي النزهة', phone='0501111004', entity_type='شركة'),
    dict(code='DEMO-05', name='برج المملكة', city='مكة', district='الروضة',
         address='حي الروضة', phone='0501111005', entity_type='شركة'),
    dict(code='DEMO-06', name='مجمع التجارة', city='مكة', district='أجياد',
         address='أجياد', phone='0501111006', entity_type='شركة'),
    dict(code='DEMO-07', name='مركز الملك عبدالله', city='مكة', district='الشوقية',
         address='الشوقية', phone='0501111007', entity_type='شركة'),
    dict(code='DEMO-08', name='برج الفيصلية', city='مكة', district='الزاهر',
         address='الزاهر', phone='0501111008', entity_type='شركة'),
)


def main() -> int:
    parser = argparse.ArgumentParser(description='Seed demo customers inside a tenant')
    parser.add_argument('--slug', default='default', help='Organization slug (default, jama, …)')
    parser.add_argument('--list', action='store_true', help='List customers only')
    parser.add_argument('--with-elevators', action='store_true', help='Add one elevator per new customer')
    args = parser.parse_args()

    from app import app, db
    from flask import g
    from models import Customer, Elevator, Organization

    slug = (args.slug or 'default').strip().lower()

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'FAIL: لا توجد مؤسسة slug={slug!r}')
            print('المؤسسات المتاحة:')
            for o in Organization.query.order_by(Organization.id).all():
                print(f'  - {o.slug}')
            return 1

        g.organization = org
        g.organization_id = org.id

        existing = Customer.query.filter_by(organization_id=org.id).order_by(Customer.id).all()
        print(f'المؤسسة: {org.name} ({org.slug}) — عملاء حاليون: {len(existing)}')
        if args.list or existing:
            for c in existing[:30]:
                print(f'  {c.code:<10} {c.name} — {c.city or "—"} / {c.district or "—"}')
            if len(existing) > 30:
                print(f'  … و {len(existing) - 30} آخرين')
        if args.list:
            return 0

        added = 0
        for row in DEMO_CUSTOMERS:
            found = Customer.query.filter_by(organization_id=org.id, code=row['code']).first()
            if found:
                continue
            cust = Customer(
                organization_id=org.id,
                code=row['code'],
                name=row['name'],
                city=row.get('city') or '',
                district=row.get('district') or '',
                address=row.get('address') or '',
                phone=row.get('phone') or '',
                status='نشط',
                entity_type=row.get('entity_type') or 'شركة',
                notes='عميل تجريبي — seed_demo_customers',
            )
            db.session.add(cust)
            db.session.flush()
            added += 1
            if args.with_elevators:
                el_code = f"EL-D{row['code'].split('-')[-1]}"
                if not Elevator.query.filter_by(organization_id=org.id, code=el_code).first():
                    db.session.add(Elevator(
                        organization_id=org.id,
                        code=el_code,
                        customer_id=cust.id,
                        building_name=row['name'],
                        elev_type='مصعد ركاب',
                        status='نشط',
                    ))
        db.session.commit()

        total = Customer.query.filter_by(organization_id=org.id).count()
        print(f'\nأُضيف: {added} عميل(اء) تجريبي')
        print(f'الإجمالي الآن: {total}')
        print('\nاعرضهم من:')
        if slug == 'default':
            print('  https://app.liftcoreapp.com/clients')
        else:
            print(f'  https://{slug}.liftcoreapp.com/clients')
        print('سجّل الدخول كـ admin ثم افتح «العملاء».')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
