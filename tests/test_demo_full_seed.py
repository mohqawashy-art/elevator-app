"""Tests for demo full seed safety and idempotency."""

from __future__ import annotations

import pytest


def test_assert_safe_demo_slug_rejects_jama():
    from demo_full_seed import assert_safe_demo_slug

    with pytest.raises(ValueError, match='demo'):
        assert_safe_demo_slug('jama')


def test_assert_safe_demo_slug_allows_demo():
    from demo_full_seed import assert_safe_demo_slug

    assert_safe_demo_slug('demo')


def test_seed_ops_idempotent_on_empty_org(client):
    from app import app, db
    from demo_full_seed import seed_full_demo_operations
    from models import Customer, Elevator, Organization, Technician

    with app.app_context():
        org = Organization(
            slug='demo-test-seed',
            name='Demo Test Seed',
            status='active',
            plan='basic',
        )
        db.session.add(org)
        db.session.flush()
        c = Customer(
            organization_id=org.id,
            code='DEMO-T1',
            name='عميل تجريبي',
            city='مكة المكرمة',
            status='نشط',
        )
        db.session.add(c)
        db.session.flush()
        db.session.add(Elevator(
            organization_id=org.id,
            code='EL-T1',
            customer_id=c.id,
            building_name='برج',
            city='مكة المكرمة',
            elev_type='مصعد ركاب',
            status='نشط',
        ))
        db.session.commit()

        stats1 = seed_full_demo_operations(org.id, password_hasher=lambda p: f'hash:{p}')
        db.session.commit()
        assert stats1.get('technicians_added', 0) >= 1

        tech_n = Technician.query.filter_by(organization_id=org.id).count()
        stats2 = seed_full_demo_operations(org.id, password_hasher=lambda p: f'hash:{p}')
        db.session.commit()
        assert stats2.get('technicians_added', 0) == 0
        assert Technician.query.filter_by(organization_id=org.id).count() == tech_n
