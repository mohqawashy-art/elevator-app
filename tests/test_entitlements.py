"""اختبارات كتالوج الباقات وتفعيل الحدود/الإضافات."""
from datetime import datetime, timedelta

from app import app, db, hash_password
from entitlements import assert_capacity, resolve_entitlements, set_custom_package, upsert_org_addon
from models import Elevator, Organization, Settings, Technician, User
from plan_catalog import CUSTOM_PLAN_KEY, PLAN_CATALOG, normalize_plan


def _ctx():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-not-default'
    with app.app_context():
        db.engine.dispose()
        db.session.remove()
        db.drop_all()
        db.create_all()
        org = Organization(slug='packco', name='Pack Co', status='active', plan='basic')
        db.session.add(org)
        db.session.flush()
        db.session.add(Settings(organization_id=org.id, company_name='Pack Co', tax_pct=15))
        db.session.add(User(
            organization_id=org.id,
            username='admin',
            password_hash=hash_password('Pass123!'),
            full_name='Admin',
            role='admin',
            is_active=True,
        ))
        db.session.commit()
        yield org.id


def test_plan_catalog_has_plus():
    assert 'plus' in PLAN_CATALOG
    assert PLAN_CATALOG['plus']['yearly_sar'] == 4590
    assert normalize_plan('PLUS') == 'plus'


def test_basic_limits_and_addon_elevators():
    gen = _ctx()
    org_id = next(gen)
    with app.app_context():
        org = db.session.get(Organization, org_id)
        ent = resolve_entitlements(org=org)
        assert ent['limits']['elevators'] == 50
        assert ent['limits']['technicians'] == 2
        assert ent['features']['inventory'] is False

        result = upsert_org_addon(org, addon_key='elevators_10', quantity=2)
        assert result['ok']
        ent2 = resolve_entitlements(org=org)
        assert ent2['limits']['elevators'] == 70  # 50 + 20

        result2 = upsert_org_addon(org, addon_key='inventory_pack')
        assert result2['ok']
        ent3 = resolve_entitlements(org=org)
        assert ent3['features']['inventory'] is True
        assert ent3['features']['excel_import'] is True


def test_custom_package_features_and_limits():
    gen = _ctx()
    org_id = next(gen)
    with app.app_context():
        org = db.session.get(Organization, org_id)
        result = set_custom_package(
            org,
            features={
                'maintenance_core': True,
                'inventory': True,
                'purchasing': False,
                'advanced_finance': False,
                'excel_import': False,
                'installation': False,
                'zatca_phase2': False,
                'priority_support': False,
            },
            elevators=25,
            office_users=4,
            technicians=3,
            storage_gb=5,
            amount=750.0,
            cycle='monthly',
        )
        assert result['ok']
        assert org.plan == CUSTOM_PLAN_KEY
        ent = resolve_entitlements(org=org)
        assert ent['is_custom']
        assert ent['features']['inventory'] is True
        assert ent['features']['purchasing'] is False
        assert ent['limits']['elevators'] == 25


def test_assert_capacity_blocks_when_full():
    gen = _ctx()
    org_id = next(gen)
    with app.app_context():
        org = db.session.get(Organization, org_id)
        # مستخدم واحد موجود — Basic يسمح بـ 3
        ok = assert_capacity('office_users', org_id=org_id)
        assert ok['ok']

        # املأ حد الفنيين (2)
        for i in range(2):
            db.session.add(Technician(
                organization_id=org_id,
                code=f'T-{i}',
                name=f'Tech {i}',
            ))
        db.session.commit()
        blocked = assert_capacity('technicians', org_id=org_id)
        assert blocked['ok'] is False
        assert 'الفنيون' in (blocked.get('error') or '')
