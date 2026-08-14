#!/usr/bin/env python3
"""تصفير المبلغ المسدد لكل عقود مستأجر (افتراضي: jama) → غير مدفوع.

لا يحذف العقود ولا يمسّ العملاء. لا يعيد حساب السداد من الإيرادات.

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/zero_jama_contract_payments.py --slug jama --dry-run
  python3 scripts/zero_jama_contract_payments.py --slug jama --yes
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description='Zero contract paid_amount for a tenant')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL — source /etc/liftcore/platform.env أولاً')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes أو --dry-run')
        return 2

    from flask import g
    from app import app, db
    from billing_consistency import _contract_invoice_status
    from models import Contract, Organization

    slug = (args.slug or 'jama').strip().lower()
    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1
        g.organization = org
        g.organization_id = org.id
        rows = (
            Contract.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .all()
        )
        paid_now = sum(1 for c in rows if (c.paid_amount or 0) > 0.01)
        print(f'Tenant: {org.name} ({org.slug}) id={org.id}')
        print(f'عقود: {len(rows)} — منها مسددة/جزئياً: {paid_now}')
        if args.dry_run:
            for c in rows[:8]:
                print(f'  {c.code}  paid={c.paid_amount or 0}  {c.invoice_status}')
            if len(rows) > 8:
                print(f'  ... و {len(rows) - 8} أخرى')
            return 0
        for c in rows:
            c.paid_amount = 0
            c.invoice_status = _contract_invoice_status(c, 0)
        db.session.commit()
        print(f'تم تصفير {len(rows)} عقداً → غير مدفوع')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
