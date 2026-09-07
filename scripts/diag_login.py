#!/usr/bin/env python3
"""محاكاة تسجيل الدخول على السيرفر."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

USERNAME = 'محمد عبدالعزيز'
PASSWORD = 'Bf@123456'


def main():
    from app import app, verify_password
    from models import Organization, RateLimitEvent, User

    with app.app_context():
        print('=== DB users matching login ===')
        for u in User.query.filter(
            User.is_active.is_(True),
            (User.username == USERNAME) | (User.full_name == USERNAME),
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
    for host in hosts:
        print(f'\n=== POST /login host={host} ===')
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'diag-csrf'
        r = client.post(
            '/login',
            data={
                'csrf_token': 'diag-csrf',
                'username': USERNAME,
                'password': PASSWORD,
            },
            headers={'Host': host},
            follow_redirects=False,
        )
        print('status', r.status_code)
        print('location', r.headers.get('Location', '-'))
        body = r.get_data(as_text=True)
        if 'محاولات كثيرة' in body:
            print('error: rate limited')
        elif 'غير صحيحة' in body or 'غير صحيح' in body:
            print('error: bad credentials')
        elif r.status_code in (302, 303):
            print('ok: redirect login success')
        else:
            print('body_snip', body[:300].replace('\n', ' '))

    with app.app_context():
        cleared = RateLimitEvent.query.filter_by(scope='login').delete(synchronize_session=False)
        from models import db
        db.session.commit()
        print(f'\ncleared_login_locks={cleared}')


if __name__ == '__main__':
    main()
