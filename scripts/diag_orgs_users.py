#!/usr/bin/env python3
from app import app, verify_password
from models import Organization, User

PWD = 'Bf@123456'

with app.app_context():
    for slug in ('jama', 'test'):
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            continue
        print(f'== {slug} (id={org.id}) ==')
        for u in User.query.filter_by(organization_id=org.id).order_by(User.id):
            ok = verify_password(u.password_hash, PWD)
            print(u.id, u.username, u.full_name or '-', u.role, 'active=' + str(u.is_active), 'pwd_ok=' + str(ok))
