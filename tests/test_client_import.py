"""اختبارات استيراد العملاء بالجملة + مطابقة أعمدة جما."""
from __future__ import annotations

from client_bulk_import import normalize_import_row
from models import Customer
from tests.conftest import login_as


def test_normalize_spaceless_headers():
    row = {
        'الاسم(عربي)': 'عميل تجريبي',
        'رقمالهاتف': '512345678',
        'المدينة': 'جدة',
        'الحي': 'الروضة',
    }
    out = normalize_import_row(row)
    assert out['name'] == 'عميل تجريبي'
    assert out['phone'] == '512345678'
    assert out['city'] == 'جدة'


def test_normalize_jama_excel_aliases():
    row = {
        'اسم العميل | رقم العميل': 'تجاهل',
        'رقم العميل': 'C-0001',
        'اسم العميل': 'عمر احمد العمودي',
        'المدينة': 'مكة المكرمة',
        'الحي أو المنطقة': 'الشرائع',
        'العنوان': '3181 العتابي',
        'الجوال': '+966 55 551 4201',
        'رقم الهوية': '1019726726',
        'البريد الالكتروني': 'a@b.com',
        'حالة العميل': 'نشط',
    }
    out = normalize_import_row(row)
    assert out['name'] == 'عمر احمد العمودي'
    assert out['phone'] == '+966 55 551 4201'
    assert out['city'] == 'مكة المكرمة'
    assert out['district'] == 'الشرائع'
    assert out['code'] == 'C-0001'
    assert out['email'] == 'a@b.com'
    assert out['national_id'] == '1019726726'


def test_clients_import_jama_rows(client):
    login_as(client, 'admin')
    r = client.post('/clients/import', json={
        'rows': [
            {
                'اسم العميل': 'بندر أحمد محمد',
                'الجوال': '+966 55 551 4201',
                'المدينة': 'مكة المكرمة',
                'الحي أو المنطقة': 'الشرائع',
            },
            {
                'اسم العميل': 'علي عمر السهلي',
                'الجوال': '0545615207',
                'المدينة': 'مكة المكرمة',
                'الحي أو المنطقة': 'العزيزية',
            },
        ],
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data['imported'] == 2
    assert data['failed'] == 0
    with client.application.app_context():
        assert Customer.query.filter_by(name='بندر أحمد محمد').first() is not None
        assert Customer.query.filter_by(name='علي عمر السهلي').first() is not None


def test_clients_import_reports_missing_phone(client):
    login_as(client, 'admin')
    r = client.post('/clients/import', json={
        'rows': [{'اسم العميل': 'بدون جوال', 'المدينة': 'جدة'}],
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data['imported'] == 0
    assert data['failed'] == 1
    assert data['errors']
    assert 'جوال' in data['errors'][0]['error']


def test_clients_import_allows_shared_phone_with_warning(client):
    login_as(client, 'admin')
    r = client.post('/clients/import', json={
        'rows': [
            {'اسم العميل': 'عميل أ', 'الجوال': '0555123456', 'المدينة': 'مكة المكرمة'},
            {'اسم العميل': 'عميل ب', 'الجوال': '0 55 512 3456', 'المدينة': 'مكة المكرمة'},
        ],
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data['imported'] == 2, data
    assert data['failed'] == 0, data
    assert data.get('warnings')


def test_clients_import_template_columns(client):
    login_as(client, 'admin')
    r = client.post('/clients/import', json={
        'rows': [{
            'الاسم (عربي)': 'عميل النموذج',
            'رقم الهاتف': '512345678',
            'المدينة': 'الرياض',
            'الحي': 'الملز',
        }],
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data['imported'] == 1


def test_clients_import_avoids_global_code_collision(client):
    """C-0001 في مؤسسة أخرى لا يمنع الاستيراد عند وجود customers_code_key القديم."""
    from flask import g
    from sqlalchemy import text

    from app import app, db, hash_password
    from client_bulk_import import import_customer_rows
    from models import Customer, Organization, User
    from tests.conftest import ensure_test_organization

    with app.app_context():
        default_id = ensure_test_organization()
        existing = Customer(
            code='C-0001',
            name='عميل افتراضي',
            phone='+966500000001',
            organization_id=default_id,
        )
        db.session.add(existing)
        db.session.commit()
        # محاكاة قيد الإنتاج العالمي
        db.session.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS customers_code_key ON customers (code)'
        ))
        db.session.commit()

        jama = Organization(slug='jama-test', name='Jama Test', status='active')
        db.session.add(jama)
        db.session.flush()
        admin = User(
            username='jama_admin',
            password_hash=hash_password('TestPass123!'),
            full_name='jama',
            role='admin',
            is_active=True,
            organization_id=jama.id,
        )
        db.session.add(admin)
        db.session.commit()
        jama_id = jama.id

        g.organization_id = jama_id
        g.pop('_legacy_code_unique', None) if hasattr(g, 'pop') else None
        if hasattr(g, '_legacy_code_unique'):
            del g._legacy_code_unique

        result = import_customer_rows([
            {'اسم العميل': 'عميل جما', 'الجوال': '511111111'},
            {'اسم العميل': 'عميل جما 2', 'الجوال': '522222222', 'رقم العميل': 'C-0001'},
        ])
        assert result['imported'] == 2, result
        assert result['failed'] == 0, result
        codes = {
            c.code for c in Customer.query.filter_by(organization_id=jama_id).all()
        }
        assert len(codes) == 2
        assert 'C-0001' not in codes
