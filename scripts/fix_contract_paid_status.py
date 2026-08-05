#!/usr/bin/env python3
"""تشخيص وإصلاح حالة سداد عقد واحد (مثل CN-00015).

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/fix_contract_paid_status.py --slug jama --code CN-00015 --dry-run
  python3 scripts/fix_contract_paid_status.py --slug jama --code CN-00015 --yes
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description='إصلاح سداد عقد محدد')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--code', required=True, help='مثل CN-00015 أو 15')
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
    from billing_consistency import refresh_contract_cache
    from contract_codes import contract_base_code
    from customer_billing import (
        COLLECTED_REVENUE_STATUSES,
        contract_paid_amount,
        is_receipt_voucher,
        repair_contract_payment_links,
    )
    from models import Contract, Invoice, Organization, Revenue

    raw = (args.code or '').strip().upper().replace(' ', '')
    if raw.isdigit():
        raw = f'CN-{int(raw):05d}'
    elif not raw.startswith('CN-') and raw.replace('-', '').replace('/', '').isalnum():
        if not raw.startswith('CN'):
            raw = f'CN-{raw}' if not raw[0].isdigit() else f'CN-{raw}'

    with app.app_context():
        org = Organization.query.filter_by(slug=(args.slug or 'jama').strip().lower()).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة {args.slug!r}')
            return 1
        g.organization = org
        g.organization_id = org.id
        print(f'Tenant: {org.name} ({org.slug})')

        base = contract_base_code(raw) or raw
        contracts = (
            Contract.query.filter_by(organization_id=org.id)
            .order_by(Contract.id)
            .all()
        )
        matched = [
            c for c in contracts
            if (c.code or '').strip().upper() == raw
            or contract_base_code(c.code) == base
            or (c.code or '').upper().startswith(base + '-')
            or (c.code or '').upper().startswith(base + '/')
        ]
        # فضّل المطابقة التامة أولاً
        exact = [c for c in matched if (c.code or '').strip().upper() == raw]
        targets = exact or matched
        if not targets:
            print(f'لم يُعثر على عقد {raw!r}. عيّنة:')
            for c in contracts[:15]:
                print(f'  {c.code}')
            return 1

        links = repair_contract_payment_links(commit=False)
        print(f'روابط مرشّحة للإصلاح (إيرادات/فواتير بلا عقد): {links}')

        for c in targets:
            print('─' * 60)
            print(
                f'عقد id={c.id} code={c.code} customer='
                f'{c.customer.name if c.customer else "—"}'
            )
            print(
                f'  total={c.total}  paid_amount(cache)={c.paid_amount}  '
                f'invoice_status(cache)={c.invoice_status!r}'
            )
            revs = Revenue.query.filter_by(
                organization_id=org.id, contract_id=c.id
            ).order_by(Revenue.id).all()
            print(f'  إيرادات مربوطة ({len(revs)}):')
            for r in revs:
                flag = '✓' if (r.status or '') in COLLECTED_REVENUE_STATUSES else '·'
                print(
                    f'    {flag} {r.code} status={r.status!r} total={r.total} '
                    f'invoice_id={r.invoice_id}'
                )

            # إيرادات يتيمة بنفس العميل تذكر الكود
            orphans = Revenue.query.filter(
                Revenue.organization_id == org.id,
                Revenue.customer_id == c.customer_id,
                Revenue.contract_id.is_(None),
            ).all()
            mention = [
                r for r in orphans
                if (c.code or '') in f'{r.reference or ""} {r.notes or ""}'
            ]
            if mention:
                print(f'  إيرادات يتيمة تذكر الكود ({len(mention)}):')
                for r in mention:
                    print(f'    {r.code} status={r.status!r} total={r.total} ref={r.reference!r}')

            invs = Invoice.query.filter_by(
                organization_id=org.id, contract_id=c.id
            ).order_by(Invoice.id).all()
            print(f'  فواتير/سندات ({len(invs)}):')
            for inv in invs:
                skip = is_receipt_voucher(inv.invoice_type) or bool(inv.revenue_id)
                print(
                    f'    {"سند" if skip else "فاتورة"} {inv.code} '
                    f'type={inv.invoice_type!r} status={inv.status!r} '
                    f'total={inv.total} paid={inv.paid_amount} revenue_id={inv.revenue_id}'
                )

            computed = contract_paid_amount(c.id)
            print(f'  المحسوب الآن contract_paid_amount={computed}')

            if args.dry_run:
                continue

            # اربط الإيرادات اليتيمة التي تذكر هذا العقد
            for r in mention:
                r.contract_id = c.id
                print(f'  ربط الإيراد {r.code} → {c.code}')

            refresh_contract_cache(c)
            print(
                f'  بعد الإصلاح: paid_amount={c.paid_amount} '
                f'invoice_status={c.invoice_status!r}'
            )

        if args.dry_run:
            print('معاينة فقط')
            return 0

        db.session.commit()
        print('تم الحفظ.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
