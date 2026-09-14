#!/usr/bin/env python3
"""مستأجر العرض على app.liftcoreapp.com — منفصل عن jama (الإنتاج).

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/ensure_app_demo_tenant.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEMO_SLUG = 'demo'
DEMO_COMPANY = 'LiftCore — عرض تجريبي'
DEMO_ADMIN = 'مدير العرض'
DEMO_EMAIL = 'demo@app.liftcoreapp.com'
DEMO_USERNAME = 'demo'
DEMO_PASSWORD = os.environ.get('LIFTCORE_APP_DEMO_PASSWORD', 'DemoShow2026!')
DEMO_NOTES = '[PLATFORM_DEMO] حساب العرض على app.liftcoreapp.com — ليس إنتاجاً.'


def main() -> int:
    from app import app, db, hash_password
    from demo_provisioning import DEMO_NOTE_MARKER, seed_lightweight_demo
    from models import Customer, Organization, Settings, User

    with app.app_context():
        org = Organization.query.filter_by(slug=DEMO_SLUG).first()
        created = False
        if not org:
            org = Organization(
                slug=DEMO_SLUG,
                name=DEMO_COMPANY,
                status='active',
                plan='basic',
                admin_email=DEMO_EMAIL,
                trial_ends_at=datetime.utcnow() + timedelta(days=3650),
                notes=DEMO_NOTES,
                billing_status='complimentary',
            )
            db.session.add(org)
            db.session.flush()
            db.session.add(Settings(
                organization_id=org.id,
                company_name=DEMO_COMPANY,
                email=DEMO_EMAIL,
                tax_pct=15,
                currency='SAR',
                language='ar',
                city='مكة المكرمة',
            ))
            db.session.add(User(
                organization_id=org.id,
                username=DEMO_USERNAME,
                password_hash=hash_password(DEMO_PASSWORD),
                full_name=DEMO_ADMIN,
                email=DEMO_EMAIL,
                role='admin',
                is_active=True,
                language='ar',
            ))
            db.session.commit()
            created = True
            print(f'[created] organization slug={DEMO_SLUG} id={org.id}')
        else:
            print(f'[exists] organization slug={DEMO_SLUG} id={org.id} name={org.name!r}')

        cust_n = Customer.query.filter_by(organization_id=org.id).count()
        if cust_n == 0:
            stats = seed_lightweight_demo(org.id)
            db.session.commit()
            print(f'[seeded] demo data: {stats}')
        else:
            print(f'[skip seed] customers={cust_n}')

        jama = Organization.query.filter_by(slug='jama').first()
        if jama and jama.id == org.id:
            print('ERROR: demo and jama share the same organization_id — abort')
            return 1

        settings = Settings.query.filter_by(organization_id=org.id).first()
        print('')
        print('=== app demo tenant ===')
        print(f'slug:      {DEMO_SLUG}')
        print(f'org_id:    {org.id}')
        print(f'company:   {settings.company_name if settings else org.name}')
        print(f'logo:      {getattr(settings, "logo_path", None) or "(none)"}')
        print(f'login:     https://app.liftcoreapp.com/login')
        print(f'username:  {DEMO_USERNAME}')
        print(f'password:  {DEMO_PASSWORD}')
        print(f'created:   {created}')
        if jama:
            print(f'jama id:   {jama.id} (production — separate)')
        print('')
        print('Set in /etc/liftcore/platform.env:')
        print('  LIFTCORE_APP_ORG_SLUG=demo')
        print('Then: sudo systemctl restart liftcore')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
