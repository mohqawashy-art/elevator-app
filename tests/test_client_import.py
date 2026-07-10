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
