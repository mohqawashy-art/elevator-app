#!/usr/bin/env python3
"""ضبط مستخدم واحد + مسح قفل محاولات الدخول (يدعم تعدد المنشآت)."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _target_orgs(db, org_slugs: list[str]):
    from models import Organization

    if not org_slugs or 'all' in org_slugs:
        return Organization.query.order_by(Organization.id).all()
    orgs = []
    for slug in org_slugs:
        org = Organization.query.filter_by(slug=slug.strip()).first()
        if org:
            orgs.append(org)
    return orgs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', required=True)
    parser.add_argument('--full-name', default='')
    parser.add_argument('--email', default='')
    parser.add_argument('--password', required=True)
    parser.add_argument(
        '--org-slug',
        action='append',
        default=None,
        help='منشأة محددة (default) أو all لكل المنشآت',
    )
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    if not args.apply:
        print('أضف --apply لتنفيذ التغيير')
        return 1

    from app import app, db, hash_password, verify_password
    from liftcore_security import is_weak_password
    from models import Organization, RateLimitEvent, User

    username = args.username.strip()
    full_name = (args.full_name or username).strip()
    email = (args.email or '').strip()
    password = args.password
    pwd_hash = hash_password(password)
    must_change = is_weak_password(password)

    with app.app_context():
        cleared = RateLimitEvent.query.filter_by(scope='login').delete(synchronize_session=False)
        org_slugs = args.org_slug if args.org_slug else ['default']
        orgs = _target_orgs(db, org_slugs)
        if not orgs:
            print('ERROR: no organizations matched')
            return 1

        updated = 0
        for org in orgs:
            user = User.query.filter(
                User.organization_id == org.id,
                db.or_(User.username == username, User.full_name == full_name),
            ).first()
            if not user:
                user = User.query.filter(
                    User.organization_id == org.id,
                    User.full_name.ilike(full_name),
                ).first()
            if not user:
                user = User(
                    organization_id=org.id,
                    username=username,
                    full_name=full_name,
                    email=email or '',
                    role='admin',
                    is_active=True,
                )
                db.session.add(user)
                action = 'created'
            else:
                action = 'updated'
            user.username = username
            user.full_name = full_name or user.full_name or username
            if email:
                user.email = email
            user.password_hash = pwd_hash
            user.is_active = True
            user.must_change_password = must_change
            if not user.role or user.role == 'viewer':
                user.role = 'admin'
            ok = verify_password(user.password_hash, password)
            print(f'OK: {action} org={org.slug} user_id={user.id} verify={ok}')
            updated += 1

        db.session.commit()
        print(f'cleared_login_locks={cleared}')
        print(f'orgs_updated={updated}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
