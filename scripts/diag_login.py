#!/usr/bin/env python3
"""محاكاة تسجيل الدخول على السيرفر."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

USERNAMES = ('mohammed', 'محمد عبدالعزيز', 'mohammed@jama.local')
PASSWORD = 'Bf@123456'


def main():
    from app import app, verify_password
    from models import Organization, RateLimitEvent, User

    with app.app_context():
        print('=== DB users matching login ===')
        for u in User.query.filter(
            User.is_active.is_(True),
            (User.username.in_(USERNAMES)) | (User.full_name.in_(USERNAMES)),
        ).all():
            org = Organization.query.get(u.organization_id)
            print(
                'id', u.id,
                'org', org.slug if org else '?',
                'username', repr(u.username),
                'full_name', repr(u.full_name),
                'role', u.role,
                'verify', verify_password(u.password_hash, PASSWORD),
                'must_change', u.must_change_password,
            )

    client = app.test_client()
    hosts = [
        'app.liftcoreapp.com',
        'jama.liftcoreapp.com',
    ]
    for login_name in USERNAMES:
        print(f'\n=== POST /login user={login_name!r} host=app.liftcoreapp.com ===')
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'diag-csrf'
        r = client.post(
            '/login',
            data={
                'csrf_token': 'diag-csrf',
                'username': login_name,
                'password': PASSWORD,
            },
            headers={'Host': 'app.liftcoreapp.com'},
            follow_redirects=False,
        )
        print('status', r.status_code, 'location', r.headers.get('Location', '-'))

    with app.app_context():
        cleared = RateLimitEvent.query.filter_by(scope='login').delete(synchronize_session=False)
        from models import db
        db.session.commit()
        print(f'\ncleared_login_locks={cleared}')


if __name__ == '__main__':
    main()
