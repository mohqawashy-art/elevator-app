#!/usr/bin/env python3
"""مسح جميع سجلات الإيرادات من قاعدة جما (مع تحديث حالة العقود)."""

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
    from app import app, db, sync_contract_invoice_status
    from models import Revenue

    with app.app_context():
        rows = Revenue.query.order_by(Revenue.id).all()
        count = len(rows)
        contract_ids = sorted({r.contract_id for r in rows if r.contract_id})
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        total = sum((r.total or 0) for r in rows)

        if dry_run:
            return {
                'dry_run': True,
                'count': count,
                'total': total,
                'contracts': len(contract_ids),
                'database': db_uri,
            }

        for r in rows:
            db.session.delete(r)
        db.session.flush()

        for cid in contract_ids:
            sync_contract_invoice_status(cid)

        db.session.commit()
        remaining = Revenue.query.count()
        return {
            'dry_run': False,
            'deleted': count,
            'total': total,
            'contracts_updated': len(contract_ids),
            'remaining': remaining,
            'database': db_uri,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description='مسح جميع الإيرادات من قاعدة جما')
    parser.add_argument('--dry-run', action='store_true', help='عرض العدد فقط دون حذف')
    parser.add_argument('--yes', action='store_true', help='تأكيد الحذف دون سؤال')
    args = parser.parse_args()

    db_url = _resolve_database_url()
    if db_url:
        os.environ['DATABASE_URL'] = db_url
        print(f'DATABASE_URL = {db_url}')
    else:
        print('تحذير: لم يُعثر على jama.db — سيُستخدم مسار التطبيق الافتراضي')

    if not args.dry_run and not args.yes:
        print('أضف --yes لتأكيد الحذف، أو --dry-run للمعاينة فقط')
        return 2

    try:
        result = clear_all_revenues(dry_run=args.dry_run)
    except Exception as exc:
        print(f'فشل: {exc}', file=sys.stderr)
        return 1

    if result.get('dry_run'):
        print(f"معاينة: {result['count']} إيراد بإجمالي {result['total']:,.2f}")
        print(f"عقود مرتبطة: {result['contracts']}")
        print(f"قاعدة البيانات: {result['database']}")
        return 0

    print(f"تم حذف {result['deleted']} إيراد بإجمالي {result['total']:,.2f}")
    print(f"عقود محدّثة: {result['contracts_updated']}")
    print(f"متبقي في القاعدة: {result['remaining']}")
    print(f"قاعدة البيانات: {result['database']}")
    return 0 if result['remaining'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
