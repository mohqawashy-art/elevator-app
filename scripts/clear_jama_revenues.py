#!/usr/bin/env python3
"""مسح جميع سجلات الإيرادات لمستأجر (افتراضي: jama) مع تحديث حالة العقود.

أمثلة على السيرفر (PostgreSQL multi-tenant):
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

DEFAULT_JAMA_DBS = (
    os.path.expanduser('~/liftcore/jama-elevator-app/instance/jama.db'),
    os.path.expanduser('~/jama-elevator-app/instance/jama.db'),
)


def _resolve_database_url() -> str:
    explicit = (os.environ.get('DATABASE_URL') or '').strip()
    if explicit:
        return explicit
    for path in DEFAULT_JAMA_DBS:
        if os.path.isfile(path):
            abs_path = os.path.abspath(path).replace('\\', '/')
            return f'sqlite:////{abs_path}'
    return ''


def clear_all_revenues(*, dry_run: bool = False) -> dict:
    """يجب استدعاؤها داخل app.app_context() مع ضبط g.organization إن وُجد."""
    from flask import g
    from app import db, sync_contract_invoice_status
    from models import Revenue
    from tenant_scope import tenant_query

    rows = tenant_query(Revenue).order_by(Revenue.id).all()
    count = len(rows)
    contract_ids = sorted({r.contract_id for r in rows if r.contract_id})
    from flask import current_app

    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    total = sum((r.total or 0) for r in rows)
    org = getattr(g, 'organization', None)
    org_label = f'{org.slug}#{org.id}' if org else '(no-org)'

    if dry_run:
        return {
            'dry_run': True,
            'count': count,
            'total': total,
            'contracts': len(contract_ids),
            'database': db_uri,
            'tenant': org_label,
        }

    for r in rows:
        db.session.delete(r)
    db.session.flush()

    for cid in contract_ids:
        sync_contract_invoice_status(cid)

    db.session.commit()
    remaining = tenant_query(Revenue).count()
    return {
        'dry_run': False,
        'deleted': count,
        'total': total,
        'contracts_updated': len(contract_ids),
        'remaining': remaining,
        'database': db_uri,
        'tenant': org_label,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='مسح جميع الإيرادات لمستأجر جما')
    parser.add_argument('--slug', default='jama', help='Organization slug (default: jama)')
    parser.add_argument('--dry-run', action='store_true', help='عرض العدد فقط دون حذف')
    parser.add_argument('--yes', action='store_true', help='تأكيد الحذف دون سؤال')
    args = parser.parse_args()

    db_url = _resolve_database_url()
    if db_url:
        os.environ['DATABASE_URL'] = db_url
        print(f'DATABASE_URL = {db_url}')
    else:
        print('تحذير: لم يُضبط DATABASE_URL — سيُستخدم إعداد التطبيق الافتراضي')

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
                print(f'ERROR: لا توجد مؤسسة slug={slug!r} — لن يتم المسح')
                return 1
            g.organization = org
            g.organization_id = org.id
            print(f'Tenant: {org.name} ({org.slug}) id={org.id}')
            result = clear_all_revenues(dry_run=args.dry_run)
    except Exception as exc:
        print(f'فشل: {exc}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    if result.get('dry_run'):
        print(f"معاينة: {result['count']} إيراد بإجمالي {result['total']:,.2f}")
        print(f"عقود مرتبطة: {result['contracts']}")
        print(f"المستأجر: {result.get('tenant')}")
        print(f"قاعدة البيانات: {result['database']}")
        return 0

    print(f"تم حذف {result['deleted']} إيراد بإجمالي {result['total']:,.2f}")
    print(f"عقود محدّثة: {result['contracts_updated']}")
    print(f"متبقي في القاعدة: {result['remaining']}")
    print(f"المستأجر: {result.get('tenant')}")
    print(f"قاعدة البيانات: {result['database']}")
    return 0 if result['remaining'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
