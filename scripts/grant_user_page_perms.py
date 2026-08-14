#!/usr/bin/env python3
"""منح صفحات لمستخدم مكتبي (مثال: Data لا يرى الإيرادات).

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python3 scripts/grant_user_page_perms.py --slug jama --username Data --pages revenues --dry-run
  python3 scripts/grant_user_page_perms.py --slug jama --username Data --pages revenues --yes
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PAGE_ALIASES = {
    'revenues': ('revenues', 'report_revenues'),
    'expenses': ('expenses', 'report_expenses'),
    'invoices': ('invoices', 'report_invoices'),
    'finance': ('revenues', 'expenses', 'invoices', 'report_revenues', 'report_expenses', 'report_invoices'),
}


def _expand_pages(raw: str) -> list[str]:
    pages: list[str] = []
    seen: set[str] = set()
    for token in (raw or 'revenues').split(','):
        key = token.strip().lower()
        if not key:
            continue
        for page in PAGE_ALIASES.get(key, (key,)):
            if page not in seen:
                pages.append(page)
                seen.add(page)
    return pages


def _grants_for_pages(pages: list[str]) -> list[str]:
    from liftcore_permissions import PAGE_SLUGS, PERM_CREATE, PERM_EDIT, PERM_READ, page_perm

    out: list[str] = []
    for page in pages:
        if page not in PAGE_SLUGS:
            raise SystemExit(f'صفحة غير معروفة: {page}')
        for action in (PERM_READ, PERM_CREATE, PERM_EDIT):
            out.append(page_perm(page, action))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='منح صفحات لمستخدم')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--username', required=True)
    parser.add_argument('--pages', default='revenues', help='مثل: revenues أو finance')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL غير مضبوط — source /etc/liftcore/platform.env أولاً')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes للتأكيد أو --dry-run للمعاينة')
        return 2

    pages = _expand_pages(args.pages)
    want = _grants_for_pages(pages)

    from flask import g
    from app import app
    from liftcore_permissions import (
        dump_permissions_extra,
        parse_permissions_extra,
        user_has_permission,
    )
    from liftcore_rbac import ROLE_CUSTOM
    from models import Organization, Revenue, User, db

    with app.app_context():
        slug = (args.slug or 'jama').strip().lower()
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
            return 1
        g.organization = org
        g.organization_id = org.id

        uname = (args.username or '').strip()
        users = User.query.filter(
            User.organization_id == org.id,
            db.func.lower(User.username) == uname.lower(),
        ).all()
        if not users:
            print(f'ERROR: لا يوجد مستخدم {uname!r} في {slug}')
            sample = (
                User.query.filter_by(organization_id=org.id)
                .order_by(User.username)
                .limit(20)
                .all()
            )
            print('عيّنة مستخدمين:', ', '.join(u.username for u in sample))
            return 1

        rev_count = Revenue.query.filter_by(organization_id=org.id).count()
        print(f'Tenant: {org.name} ({org.slug}) id={org.id}')
        print(f'إيرادات المستأجر: {rev_count}')

        for user in users:
            extra = parse_permissions_extra(user.permissions_extra)
            before = list(extra['grants'])
            print(
                f'User: {user.username} id={user.id} role={user.role} '
                f'active={user.is_active} name={user.full_name or "—"}'
            )
            print('  صلاحيات قبل:', ', '.join(before) or '—')
            print('  يرى الإيرادات الآن:', user_has_permission(user, 'revenues.read'))

            if user.role != ROLE_CUSTOM:
                print(
                    '  الدور ليس «مخصص» — الإيرادات تظهر تلقائياً لـ admin/manager/viewer. '
                    'إن كانت القائمة مخفية فالمستخدم على الأرجح custom باسم مختلف، '
                    'أو يحتاج تحديث الصفحة بعد منح الصلاحية.'
                )
                continue

            merged = list(dict.fromkeys(before + want))
            added = [item for item in want if item not in before]
            print('  سيُضاف:', ', '.join(added) or 'لا شيء جديد')
            if args.dry_run:
                print('  معاينة فقط')
                continue
            user.permissions_extra = dump_permissions_extra(merged)
            db.session.commit()
            print('  صلاحيات بعد:', ', '.join(parse_permissions_extra(user.permissions_extra)['grants']))
            print('  يرى الإيرادات بعد المنح:', user_has_permission(user, 'revenues.read'))
            print('  تم الحفظ — حدّث صفحة Data (F5).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
