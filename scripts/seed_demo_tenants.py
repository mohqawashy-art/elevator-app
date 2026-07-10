#!/usr/bin/env python3
"""إنشاء عملاء تجريبيين (مؤسسات + admin + عميل عيّنة) لتجربة multi-tenant.

  # على السيرفر (مع DATABASE_URL من platform.env):
  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/seed_demo_tenants.py

  # محلياً:
  python scripts/seed_demo_tenants.py

يطبع جدول الدخول وروابط العرض. آمن للإعادة (يتخطى الموجود).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# كلمة مرور موحّدة للتجربة — غيّرها بعد التجربة إن لزم
DEMO_PASSWORD = 'DemoPass123!'

DEMOS = (
    {
        'slug': 'najd',
        'company': 'نجد للمصاعد',
        'admin_name': 'مدير نجد',
        'admin_email': 'najd@demo.liftcoreapp.com',
        'customer': 'برج النخيل',
        'city': 'الرياض',
    },
    {
        'slug': 'hijaz',
        'company': 'حجاز للصيانة',
        'admin_name': 'مدير حجاز',
        'admin_email': 'hijaz@demo.liftcoreapp.com',
        'customer': 'مجمع الصفا',
        'city': 'مكة',
    },
    {
        'slug': 'sharq',
        'company': 'الشرق للمصاعد',
        'admin_name': 'مدير الشرق',
        'admin_email': 'sharq@demo.liftcoreapp.com',
        'customer': 'أبراج الخبر',
        'city': 'الدمام',
    },
)


def main() -> int:
    from app import app, db, hash_password
    from models import Customer, Organization, User
    from tenant_signup import create_tenant_signup, normalize_slug

    rows = []
    with app.app_context():
        pwd_hash = hash_password(DEMO_PASSWORD)
        for demo in DEMOS:
            slug = normalize_slug(demo['slug'])
            existing = Organization.query.filter_by(slug=slug).first()
            if existing:
                user = User.query.filter_by(organization_id=existing.id, username=slug).first()
                cust_count = Customer.query.filter_by(organization_id=existing.id).count()
                rows.append({
                    'slug': slug,
                    'company': existing.name,
                    'status': 'موجود مسبقاً',
                    'username': (user.username if user else slug),
                    'customers': cust_count,
                    'login': f'https://{slug}.liftcoreapp.com/login',
                })
                print(f'[skip] {slug} — موجود (id={existing.id})')
                continue

            result = create_tenant_signup(
                company_name=demo['company'],
                slug=slug,
                admin_email=demo['admin_email'],
                admin_name=demo['admin_name'],
                password_hash=pwd_hash,
                username=slug,
            )
            if not result.get('ok'):
                print(f"[fail] {slug}: {result.get('errors')}")
                rows.append({
                    'slug': slug,
                    'company': demo['company'],
                    'status': 'فشل',
                    'username': slug,
                    'customers': 0,
                    'login': f'https://{slug}.liftcoreapp.com/login',
                })
                continue

            org_id = result['organization_id']
            # عميل عيّنة داخل المؤسسة
            cust = Customer(
                organization_id=org_id,
                code='C-0001',
                name=demo['customer'],
                city=demo.get('city') or '',
                status='نشط',
                entity_type='شركة',
            )
            db.session.add(cust)
            org = db.session.get(Organization, org_id)
            if org:
                org.status = 'active'
                org.plan = 'basic'
            db.session.commit()

            rows.append({
                'slug': slug,
                'company': demo['company'],
                'status': 'أُنشئ',
                'username': slug,
                'customers': 1,
                'login': result.get('login_url') or f'https://{slug}.liftcoreapp.com/login',
            })
            print(f'[ok]   {slug} — {demo["company"]}')

        # ملخص المؤسسات كلها
        print('\n' + '=' * 72)
        print('عملاء التجربة — بيانات الدخول')
        print('=' * 72)
        print(f'{"المؤسسة":<18} {"المستخدم":<12} {"كلمة المرور":<14} {"الحالة":<14} الرابط')
        print('-' * 72)
        for r in rows:
            print(
                f'{r["company"]:<18} {r["username"]:<12} {DEMO_PASSWORD:<14} '
                f'{r["status"]:<14} {r["login"]}'
            )

        print('\nعرض كل العملاء من لوحة المنصة:')
        print('  https://admin.liftcoreapp.com/platform/orgs')
        print('  (دخول بـ admin مؤسسة default على admin.liftcoreapp.com)')
        print('\nمؤسسات موجودة حالياً في قاعدة البيانات:')
        for o in Organization.query.order_by(Organization.id).all():
            uc = User.query.filter_by(organization_id=o.id).count()
            cc = Customer.query.filter_by(organization_id=o.id).count()
            print(f'  - {o.slug:<12} {o.name:<28} users={uc} customers={cc} status={o.status}')
        print('=' * 72)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
