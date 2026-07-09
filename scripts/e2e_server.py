#!/usr/bin/env python3
"""سيرفر E2E — قاعدة نظيفة + بيانات اختبار + تشغيل على :5001."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

instance = os.path.join(ROOT, 'instance')
os.makedirs(instance, exist_ok=True)
e2e_db = os.path.join(instance, 'e2e.db')
if os.path.isfile(e2e_db):
    try:
        os.remove(e2e_db)
    except OSError:
        # ملف مقفول من تشغيل سابق — استخدم اسماً جديداً
        e2e_db = os.path.join(instance, f'e2e-{os.getpid()}.db')

os.environ['DATABASE_URL'] = 'sqlite:///' + e2e_db.replace('\\', '/')
os.environ.setdefault('SECRET_KEY', 'e2e-test-secret-key-not-default')
os.environ.pop('LIFTCORE_HTTPS', None)

from app import app, db, hash_password  # noqa: E402
from models import (  # noqa: E402
    Customer,
    Elevator,
    Organization,
    Settings,
    Technician,
    User,
)

E2E_PASSWORD = 'E2ePass123!'


def seed() -> None:
    with app.app_context():
        db.create_all()
        org = Organization.query.filter_by(slug='default').first()
        if not org:
            org = Organization(
                slug='default',
                name='LiftCore E2E',
                status='active',
                plan='basic',
            )
            db.session.add(org)
            db.session.flush()
        oid = org.id

        if not Settings.query.filter_by(organization_id=oid).first():
            db.session.add(Settings(
                organization_id=oid,
                company_name='LiftCore E2E',
                tax_pct=15,
                city='مكة المكرمة',
            ))
        if not User.query.filter_by(organization_id=oid, username='admin').first():
            db.session.add(User(
                organization_id=oid,
                username='admin',
                password_hash=hash_password(E2E_PASSWORD),
                full_name='مدير E2E',
                role='admin',
                is_active=True,
                must_change_password=False,
            ))
        if not Customer.query.filter_by(organization_id=oid).first():
            c = Customer(
                organization_id=oid,
                code='C-E2E01',
                name='عميل اختبار E2E',
                phone='+966512345678',
                city='مكة المكرمة',
                district='العزيزية',
                status='نشط',
            )
            db.session.add(c)
            db.session.flush()
            db.session.add(Elevator(
                organization_id=oid,
                code='EL-E2E01',
                customer_id=c.id,
                building_name='برج E2E',
                status='نشط',
            ))
        if not Technician.query.filter_by(organization_id=oid).first():
            db.session.add(Technician(
                organization_id=oid,
                code='TECH-E2E',
                name='فني E2E',
                phone='512999888',
                status='متاح',
            ))
        db.session.commit()
        print('[e2e] DB ready — admin /', E2E_PASSWORD)


if __name__ == '__main__':
    seed()
    port = int(os.environ.get('E2E_PORT', '5001'))
    print(f'[e2e] http://127.0.0.1:{port}')
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
