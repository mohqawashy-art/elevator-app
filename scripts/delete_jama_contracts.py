#!/usr/bin/env python3
"""حذف عقود مستأجر (افتراضي: jama) بنفس مسار واجهة العقود.

لا يعيد ترقيم العقود الأخرى. الترقيم التلقائي (next_code) = أعلى CN-##### + 1
بين العقود المتبقية؛ أكواد التجديد مثل CN-00021-2026 لا تدخل في الحساب أصلاً.

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/delete_jama_contracts.py --slug jama --codes 29,21-2026 --dry-run
  python3 scripts/delete_jama_contracts.py --slug jama --codes 29,21-2026 --yes
  python3 scripts/delete_jama_contracts.py --slug jama --all --dry-run
  python3 scripts/delete_jama_contracts.py --slug jama --all --yes
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _normalize_token(raw: str) -> str:
    return (raw or '').strip().upper().replace(' ', '')


def _code_matches(contract_code: str, token: str) -> bool:
    code = _normalize_token(contract_code)
    tok = _normalize_token(token)
    if not code or not tok:
        return False
    if code == tok or code == f'CN-{tok}':
        return True
    if re.fullmatch(r'\d+', tok):
        padded = f'CN-{int(tok):05d}'
        bare = f'CN-{int(tok)}'
        return (
            code == padded
            or code == bare
            or code.startswith(padded + '-')
            or code.startswith(padded + '/')
            or code.startswith(bare + '-')
            or code.startswith(bare + '/')
        )
    m = re.fullmatch(r'(?:CN-)?(\d+)[-/](20\d{2})(?:-(\d+))?', tok, re.I)
    if m:
        num, year, suf = m.group(1), m.group(2), m.group(3)
        padded = f'CN-{int(num):05d}-{year}'
        candidates = {
            padded,
            f'CN-{int(num)}-{year}',
            f'{int(num)}-{year}',
            f'CN-{int(num):05d}/{year}',
            f'CN-{int(num)}/{year}',
        }
        if suf:
            candidates |= {f'{padded}-{suf}', f'CN-{int(num)}-{year}-{suf}'}
        # تطابق تام فقط — لا يحذف CN-00017 عند طلب CN-00017-2026
        return code in candidates
    if not tok.startswith('CN-') and re.search(r'\d', tok):
        return _code_matches(code, f'CN-{tok}')
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description='حذف عقود محددة')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--codes', default='', help='مثل: 29,21-2026')
    parser.add_argument('--all', action='store_true', help='حذف كل عقود المستأجر')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL غير مضبوط — source /etc/liftcore/platform.env أولاً')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes للتأكيد أو --dry-run للمعاينة')
        return 2
    if not args.all and not (args.codes or '').strip():
        print('حدّد --codes أو --all')
        return 1

    tokens = [t.strip() for t in (args.codes or '').split(',') if t.strip()]

    from flask import g
    from app import app, _purge_contract_dependencies, _remove_contract_file
    from models import Contract, Organization, db
    from operations import next_code

    with app.app_context():
        slug = (args.slug or 'jama').strip().lower()
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
            return 1
        g.organization = org
        g.organization_id = org.id
        print(f'Tenant: {org.name} ({org.slug}) id={org.id}')

        contracts = (
            Contract.query.filter_by(organization_id=org.id)
            .order_by(Contract.id)
            .all()
        )
        matched = list(contracts) if args.all else [
            c
            for c in contracts
            if any(_code_matches(c.code or '', tok) for tok in tokens)
        ]
        if not matched:
            if args.all:
                print('لا توجد عقود لهذا المستأجر — لا شيء للحذف')
                return 0
            print('لم يُعثر على عقود مطابقة. عيّنة:')
            for c in contracts[:20]:
                print(f'  {c.code}  total={c.total}')
            print(f'... إجمالي: {len(contracts)}')
            return 1

        before_next = next_code(Contract, 'CN-', digits=5)
        print(f'next_code قبل الحذف: {before_next}')
        print(f'سيُحذف ({len(matched)}):')
        for c in matched:
            cust = c.customer.name if c.customer else '—'
            print(
                f'  id={c.id} code={c.code} customer={cust} '
                f'total={c.total} status={c.status}'
            )

        if args.dry_run:
            print('معاينة فقط — لم يُحذف شيء')
            return 0

        for c in matched:
            freed = c.code
            _remove_contract_file(c)
            _purge_contract_dependencies(c.id, keep_visits=bool(args.all))
            db.session.delete(c)
            print(f'حُذف {freed} — الكود متاح لإعادة الاستخدام')
        db.session.commit()

        after_next = next_code(Contract, 'CN-', digits=5)
        print(f'next_code بعد الحذف: {after_next}')
        left = Contract.query.filter_by(organization_id=org.id).count()
        if args.all:
            print(f'العقود المتبقية للمستأجر: {left}')
        else:
            remaining = []
            for tok in tokens:
                for c in Contract.query.filter_by(organization_id=org.id).all():
                    if _code_matches(c.code or '', tok):
                        remaining.append(c.code)
            if remaining:
                print('تحذير: ما زال موجوداً:', ', '.join(remaining))
            else:
                print('الكود/الأكواد محرَّرة ويمكن استخدامها من جديد.')
        if after_next != before_next:
            print(
                'تنبيه: انخفض الرقم التالي لأن أعلى CN-##### حُذف. '
                'العقود الأخرى لم تُعاد ترقيمها.'
            )
        print('تم الحذف.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
