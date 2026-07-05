"""Fixtures مشتركة — قاعدة in-memory لكل اختبار."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from app import app, db, hash_password
from models import Settings, User


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-not-default'
    with app.app_context():
        db.engine.dispose()
        db.session.remove()
        db.drop_all()
        db.create_all()
        if not Settings.query.first():
            db.session.add(Settings(company_name='LiftCore Test', tax_pct=15))
        users = {}
        for role in ('admin', 'manager', 'viewer'):
            u = User(
                username=f'test_{role}',
                password_hash=hash_password('TestPass123!'),
                full_name=role,
                role=role,
                is_active=True,
            )
            db.session.add(u)
            users[role] = u
        db.session.commit()
        user_ids = {role: users[role].id for role in users}
    with app.test_client() as c:
        c._user_ids = user_ids
        yield c


def login_as(client, role: str = 'admin'):
    uid = client._user_ids[role]
    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['lang'] = 'ar'
