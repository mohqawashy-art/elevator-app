#!/usr/bin/env python3
"""ضبط مستخدم واحد + مسح قفل محاولات الدخول."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', required=True)
    parser.add_argument('--full-name', default='')
    parser.add_argument('--password', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    from app import app, db, hash_password
    from liftcore_security import is_weak_password
    from models import RateLimitEvent, User

    username = args.username.strip()
    full_name = (args.full_name or username).strip()
    password = args.password

    with app.app_context():
        cleared = RateLimitEvent.query.filter_by(scope='login').delete(synchronize_session=False)
        user = User.query.filter(
            db.or_(User.username == username, User.full_name == full_name)
        ).first()
        if not user:
            user = User.query.filter(User.full_name.ilike(full_name)).first()
        if not user:
            user = User(
                username=username,
                full_name=full_name,
                email='',
                role='admin',
                is_active=True,
            )
            db.session.add(user)
            action = 'created'
        else:
            action = 'updated'
        user.username = username
        user.full_name = full_name or user.full_name or username
        user.password_hash = hash_password(password)
        user.is_active = True
        user.must_change_password = is_weak_password(password)
        user.role = user.role or 'admin'
        db.session.commit()
        print(f'OK: {action} user id={user.id} username={user.username}')
        print(f'cleared_login_locks={cleared}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
