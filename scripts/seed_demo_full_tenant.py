#!/usr/bin/env python3
"""ملء مستأجر demo بالكامل — كل الصفحات والتقارير — دون المساس بـ jama.

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/seed_demo_full_tenant.py

  # معاينة فقط:
  python3 scripts/seed_demo_full_tenant.py --dry-run

  # إعادة ضبط demo ثم ملء كامل:
  python3 scripts/seed_demo_full_tenant.py --reset --confirm JAMA_WIPE

  # طبقة التشغيل فقط (بعد استيراد Excel يدوياً):
  python3 scripts/seed_demo_full_tenant.py --ops-only

يُشترط: LIFTCORE_APP_ORG_SLUG=demo على app.liftcoreapp.com
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEMO_SLUG = 'demo'
DATA_DIR = ROOT / 'deploy' / 'data' / 'demo_makkah'


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Seed full demo tenant (all pages/reports) — demo slug only',
    )
    parser.add_argument('--slug', default=DEMO_SLUG, help='Must be demo (default)')
    parser.add_argument('--data-dir', default=str(DATA_DIR), help='demo_makkah folder')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--ops-only', action='store_true', help='Skip Excel import; ops layer only')
    parser.add_argument('--skip-import', action='store_true', help='Alias: ops only')
    parser.add_argument('--reset', action='store_true', help='Wipe demo tenant data first')
    parser.add_argument('--confirm', default='', help='JAMA_WIPE when using --reset')
    args = parser.parse_args()

    slug = (args.slug or DEMO_SLUG).strip().lower()
    ops_only = args.ops_only or args.skip_import

    from demo_full_seed import (
        assert_safe_demo_slug,
        bind_tenant,
        import_makkah_base_pack,
        seed_full_demo_operations,
        tenant_summary,
    )

    try:
        assert_safe_demo_slug(slug)
    except ValueError as exc:
        print(f'ERROR: {exc}')
        return 1

    from app import app, db, hash_password

    with app.app_context():
        if args.reset:
            if (args.confirm or '').strip() != 'JAMA_WIPE':
                print('ERROR: --reset requires --confirm JAMA_WIPE')
                return 1
            from models import Organization
            from tenant_lifecycle import wipe_tenant

            org = Organization.query.filter_by(slug=slug).first()
            if not org:
                print(f'ERROR: no org slug={slug}')
                return 1
            bind_tenant(slug)
            print(f'==> wiping tenant {slug} (id={org.id}) — keep users')
            wipe_tenant(org, keep_users=True, delete_organization=False)
            db.session.commit()
            print('[ok] demo data wiped')

        org = bind_tenant(slug)
        print(f'==> tenant: {org.name} ({org.slug}) id={org.id}')
        print('Before:', tenant_summary(org))

        if not ops_only:
            print('\n==> [1/2] demo_makkah base (clients, elevators, contracts, inventory)')
            try:
                base_stats = import_makkah_base_pack(
                    org,
                    args.data_dir,
                    dry_run=args.dry_run,
                )
                for key, val in base_stats.items():
                    print(f'  {key}: {val}')
            except FileNotFoundError as exc:
                print(f'ERROR: {exc}')
                return 1

        print('\n==> [2/2] operations layer (techs, visits, faults, finance, warehouse)')
        ops_stats = seed_full_demo_operations(
            org.id,
            password_hasher=hash_password,
            dry_run=args.dry_run,
        )
        for key, val in ops_stats.items():
            print(f'  {key}: {val}')

        if not args.dry_run:
            db.session.commit()
            print('\n[committed]')
        else:
            db.session.rollback()
            print('\n[dry-run] rolled back')

        print('After:', tenant_summary(org))

        jama = __import__('models', fromlist=['Organization']).Organization.query.filter_by(slug='jama').first()
        if jama:
            print(f'\njama untouched: org_id={jama.id} customers='
                  f'{__import__("models", fromlist=["Customer"]).Customer.query.execution_options(skip_tenant=True).filter_by(organization_id=jama.id).count()}')

        print('\n=== login ===')
        print('  https://app.liftcoreapp.com/login')
        print('  user: demo')
        pwd = os.environ.get('LIFTCORE_APP_DEMO_PASSWORD', 'DemoShow2026!')
        print(f'  pass: {pwd}')
        print('  field PIN (technicians): 123456')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
