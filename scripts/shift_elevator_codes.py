#!/usr/bin/env python3
"""ترحيل أرقام المصاعد لإفراغ كود معيّن (افتراضي: EL-0043).

مثال: --from 43
  EL-0043 → EL-0044
  EL-0044 → EL-0045
  ...
  ويبقى EL-0043 شاغراً.

يُنفَّذ من الأعلى للأسفل لتفادي تعارض القيد الفريد.
يحدّث أيضاً building_name إن احتوى كود المصعد القديم.

  cd ~/liftcore/jama-elevator-app
  source .venv/bin/activate
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/shift_elevator_codes.py --slug jama --from 43 --dry-run
  python scripts/shift_elevator_codes.py --slug jama --from 43 --yes
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _code_num(code: str) -> int | None:
    m = re.match(r'^EL-(\d+)$', (code or '').strip().upper())
    return int(m.group(1)) if m else None


def _fmt(n: int, digits: int) -> str:
    return f'EL-{n:0{digits}d}'


def main() -> int:
    parser = argparse.ArgumentParser(description='ترحيل أرقام المصاعد لإفراغ كود')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--from', dest='from_num', type=int, default=43,
                        help='رقم المصعد الذي يُفرَّغ (افتراضي 43)')
    parser.add_argument('--digits', type=int, default=4, help='عرض الأرقام في الكود (افتراضي 4)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL غير مضبوط — source /etc/liftcore/platform.env أولاً')
        return 1
    if args.from_num < 1:
        print('ERROR: --from يجب أن يكون >= 1')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes للتأكيد أو --dry-run للمعاينة')
        return 2

    from flask import g
    from app import app
    from models import Elevator, Organization, db
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

        elevs = Elevator.query.filter_by(organization_id=org.id).all()
        numbered: list[tuple[int, Elevator]] = []
        for e in elevs:
            n = _code_num(e.code or '')
            if n is not None:
                numbered.append((n, e))

        to_shift = [(n, e) for n, e in numbered if n >= args.from_num]
        to_shift.sort(key=lambda x: x[0], reverse=True)  # الأعلى أولاً

        vacant = _fmt(args.from_num, args.digits)
        occupied = {_code_num(e.code or '') for e in elevs}
        already_vacant = args.from_num not in occupied

        print(f'إجمالي المصاعد: {len(elevs)}')
        print(f'سيُرحَّل (>= {args.from_num}): {len(to_shift)}')
        print(f'الكود المستهدف إفراغه: {vacant}'
              + (' (شاغر أصلاً)' if already_vacant else ''))
        print(f'next_code قبل: {next_code(Elevator, "EL-", digits=args.digits)}')

        if not to_shift:
            print('لا توجد مصاعد للترحيل.')
            return 0

        print('عيّنة (حتى 15 من الأعلى):')
        for n, e in to_shift[:15]:
            cust = e.customer.name if e.customer else '—'
            print(f'  {e.code} → {_fmt(n + 1, args.digits)}  | {cust}')

        if args.dry_run:
            print('معاينة فقط — لم يُغيَّر شيء')
            return 0

        # ممرّان: أولاً إلى أكواد مؤقتة، ثم إلى النهائية (أمان ضد أي تعارض)
        temp_prefix = '__TMP__'
        mapping: list[tuple[Elevator, str, str]] = []
        for n, e in to_shift:
            old = e.code
            new = _fmt(n + 1, args.digits)
            mapping.append((e, old, new))

        for e, old, new in mapping:
            e.code = f'{temp_prefix}{old}'
            bn = e.building_name or ''
            if old in bn:
                e.building_name = bn.replace(old, f'{temp_prefix}{old}')
        db.session.flush()

        for e, old, new in mapping:
            e.code = new
            bn = e.building_name or ''
            tmp = f'{temp_prefix}{old}'
            if tmp in bn:
                e.building_name = bn.replace(tmp, new)
            elif old in bn:
                e.building_name = bn.replace(old, new)

        db.session.commit()

        still = Elevator.query.filter_by(organization_id=org.id, code=vacant).first()
        after_next = next_code(Elevator, 'EL-', digits=args.digits)
        print(f'تم ترحيل {len(mapping)} مصعد.')
        print(f'{vacant}: {"ما زال موجوداً!" if still else "شاغر ✓"}')
        print(f'next_code بعد: {after_next}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
