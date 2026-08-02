#!/usr/bin/env python3
"""مسح إيرادات مستأجر جما + سندات القبض المرتبطة (حتى لا يفشل الحذف بـ FK).

على السيرفر:
  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/clear_jama_revenues.py --slug jama --dry-run
  python3 scripts/clear_jama_revenues.py --slug jama --yes
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _mask_db(url: str) -> str:
    if not url:
        return '(empty)'
    # إخفاء كلمة المرور في الطباعة
    if '@' in url and '://' in url:
        try:
            head, rest = url.split('://', 1)
            if '@' in rest:
                creds, host = rest.rsplit('@', 1)
                user = creds.split(':', 1)[0]
                return f'{head}://{user}:***@{host}'
        except Exception:
            pass
    return url[:48] + ('…' if len(url) > 48 else '')


def clear_tenant_revenues(*, org_id: int, dry_run: bool = False) -> dict:
    """يمسح سندات القبض ثم الإيرادات لمؤسسة واحدة، ويعيد ضبط المدفوع على العقود."""
    from sqlalchemy import or_

    from app import db, sync_contract_invoice_status
    from models import Contract, Invoice, PartsBilling, Revenue

    rev_q = Revenue.query.filter_by(organization_id=org_id)
    receipt_q = Invoice.query.filter(
        Invoice.organization_id == org_id,
        or_(
            Invoice.invoice_type.contains('سند'),
            Invoice.revenue_id.isnot(None),
        ),
    )

    rev_rows = rev_q.order_by(Revenue.id).all()
    receipt_rows = receipt_q.order_by(Invoice.id).all()
    contract_ids = sorted({
        *(r.contract_id for r in rev_rows if r.contract_id),
        *(i.contract_id for i in receipt_rows if i.contract_id),
    })

    rev_total = sum((r.total or 0) for r in rev_rows)
    receipt_total = sum((i.total or 0) for i in receipt_rows)

    from flask import current_app

    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    info = {
        'revenues': len(rev_rows),
        'revenue_total': rev_total,
        'receipts': len(receipt_rows),
        'receipt_total': receipt_total,
        'contracts': len(contract_ids),
        'database': _mask_db(db_uri),
        'org_id': org_id,
    }

    if dry_run:
        info['dry_run'] = True
        # عيّنة أكواد للتأكد أننا على المستأجر الصحيح
        info['sample_revenues'] = [r.code for r in rev_rows[:5]]
        info['sample_receipts'] = [i.code for i in receipt_rows[:5]]
        return info

    # 1) سندات القبض أولاً (FK: invoices.revenue_id → revenues.id)
    for inv in receipt_rows:
        db.session.delete(inv)
    db.session.flush()

    # 2) أي فاتورة ما زالت تشير لإيراد (احتياط)
    Invoice.query.filter(
        Invoice.organization_id == org_id,
        Invoice.revenue_id.isnot(None),
    ).update({Invoice.revenue_id: None}, synchronize_session=False)
    db.session.flush()

    # 3) الإيرادات
    for r in rev_rows:
        db.session.delete(r)
    db.session.flush()

    # 4) إعادة ضبط المدفوع على فواتير/قطع غير السندات
    Invoice.query.filter(
        Invoice.organization_id == org_id,
        ~Invoice.invoice_type.contains('سند'),
    ).update(
        {Invoice.paid_amount: 0, Invoice.status: 'غير مدفوعة'},
        synchronize_session=False,
    )
    PartsBilling.query.filter_by(organization_id=org_id).update(
        {PartsBilling.paid_amount: 0},
        synchronize_session=False,
    )
    db.session.flush()

    # 5) تحديث كاش العقود
    all_contracts = (
        Contract.query.filter_by(organization_id=org_id).with_entities(Contract.id).all()
    )
    for (cid,) in all_contracts:
        sync_contract_invoice_status(cid)

    db.session.commit()

    info['dry_run'] = False
    info['deleted_revenues'] = len(rev_rows)
    info['deleted_receipts'] = len(receipt_rows)
    info['remaining_revenues'] = Revenue.query.filter_by(organization_id=org_id).count()
    info['remaining_receipts'] = Invoice.query.filter(
        Invoice.organization_id == org_id,
        or_(
            Invoice.invoice_type.contains('سند'),
            Invoice.revenue_id.isnot(None),
        ),
    ).count()
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description='مسح إيرادات + سندات قبض لمستأجر')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument(
        '--allow-sqlite',
        action='store_true',
        help='السماح بقاعدة sqlite (للتطوير فقط)',
    )
    args = parser.parse_args()

    db_url = (os.environ.get('DATABASE_URL') or '').strip()
    if not db_url:
        print('ERROR: DATABASE_URL غير مضبوط.')
        print('شغّل أولاً: set -a; source /etc/liftcore/platform.env; set +a')
        return 1
    if db_url.startswith('sqlite') and not args.allow_sqlite and not args.dry_run:
        print(f'ERROR: رفض المسح على sqlite بدون --allow-sqlite: {_mask_db(db_url)}')
        print('جما الحية على PostgreSQL — تأكد من تحميل platform.env')
        return 1

    print(f'DATABASE_URL = {_mask_db(db_url)}')

    if not args.dry_run and not args.yes:
        print('أضف --yes لتأكيد الحذف، أو --dry-run للمعاينة فقط')
        return 2

    from flask import g
    from models import Organization
    from app import app

    try:
        with app.app_context():
            slug = (args.slug or 'jama').strip().lower()
            org = Organization.query.filter_by(slug=slug).first()
            if not org:
                print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
                orgs = Organization.query.order_by(Organization.id).all()
                print('المؤسسات الموجودة:', ', '.join(f'{o.slug}#{o.id}' for o in orgs) or '(لا يوجد)')
                return 1
            g.organization = org
            g.organization_id = org.id
            print(f'Tenant: {org.name} ({org.slug}) id={org.id}')
            result = clear_tenant_revenues(org_id=org.id, dry_run=args.dry_run)
    except Exception as exc:
        print(f'فشل: {exc}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    if result.get('dry_run'):
        print(f"معاينة إيرادات: {result['revenues']} بإجمالي {result['revenue_total']:,.2f}")
        print(f"معاينة سندات قبض: {result['receipts']} بإجمالي {result['receipt_total']:,.2f}")
        print(f"عقود مرتبطة: {result['contracts']}")
        if result.get('sample_revenues'):
            print('عيّنة إيرادات:', ', '.join(result['sample_revenues']))
        if result.get('sample_receipts'):
            print('عيّنة سندات:', ', '.join(result['sample_receipts']))
        print(f"قاعدة البيانات: {result['database']}")
        if result['revenues'] == 0 and result['receipts'] == 0:
            print('تحذير: لا يوجد شيء للحذف على هذا المستأجر/القاعدة')
        return 0

    print(f"حُذف إيرادات: {result['deleted_revenues']} (إجمالي {result['revenue_total']:,.2f})")
    print(f"حُذف سندات قبض: {result['deleted_receipts']} (إجمالي {result['receipt_total']:,.2f})")
    print(f"متبقي إيرادات: {result['remaining_revenues']}")
    print(f"متبقي سندات: {result['remaining_receipts']}")
    print(f"قاعدة البيانات: {result['database']}")
    ok = result['remaining_revenues'] == 0 and result['remaining_receipts'] == 0
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
