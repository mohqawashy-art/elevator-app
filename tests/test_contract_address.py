"""عنوان موقع الخدمة — من العقد فقط."""
from __future__ import annotations

from contract_print import customer_address_line, customer_address_parts, format_phone_local


class _FakeContract:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeCustomer:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_contract_address_ignores_customer_record():
    cust = _FakeCustomer(
        address='عنوان قديم من صفحة العميل',
        district='حي العميل',
        city='جدة',
    )
    contract = _FakeContract(
        address='شارع العقد 12',
        district='حي العقد',
        city='جدة',
    )
    line = customer_address_line(cust, contract)
    assert 'عنوان قديم' not in line
    assert 'شارع العقد 12' not in line
    assert 'جدة' in line
    assert 'حي العقد' in line


def test_customer_address_parts_splits_city_and_district():
    contract = _FakeContract(address='شارع 1', district='حي النزهة', city='جدة')
    main, tail = customer_address_parts(None, contract)
    assert main == 'جدة'
    assert tail == 'حي النزهة'


def test_mecca_address_uses_city_and_district():
    contract = _FakeContract(city='MECCA', district='AZIZ', address='street')
    contract.city = '\u0645\u0643\u0629'
    contract.district = '\u062d\u064a \u0627\u0644\u0639\u0632\u064a\u0632\u064a\u0629'
    main, tail = customer_address_parts(None, contract)
    assert main == '\u0645\u0643\u0629 \u0627\u0644\u0645\u0643\u0631\u0645\u0629'
    assert tail == '\u062d\u064a \u0627\u0644\u0639\u0632\u064a\u0632\u064a\u0629'


def test_format_phone_local_strips_country_code():
    assert format_phone_local('+966501234567') == '0501234567'
    assert format_phone_local('966501234567') == '0501234567'
    assert format_phone_local('0501234567') == '0501234567'
    assert format_phone_local('', placeholder='0000000000') == '0000000000'


def test_contract_address_empty_when_contract_has_no_site():
    cust = _FakeCustomer(address='عنوان عميل', city='جدة')
    contract = _FakeContract(address='', district='', city='')
    assert customer_address_line(cust, contract) == '—'


def test_contract_print_amount_uses_total_inclusive_vat(client):
    from datetime import date

    from app import app, db
    from contract_print import contract_print_payload
    from models import Contract, Customer, Settings
    from tests.conftest import login_as

    login_as(client, 'admin')
    with app.app_context():
        org_id = Settings.query.first().organization_id
        cust = Customer(code='C-AMT1', name='عميل مبلغ', status='نشط', organization_id=org_id)
        db.session.add(cust)
        db.session.flush()
        contract = Contract(
            code='CN-AMT1',
            customer_id=cust.id,
            contract_type='صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            value=24000,
            total=27600,
            status='نشط',
            organization_id=org_id,
        )
        db.session.add(contract)
        db.session.commit()
        payload = contract_print_payload(contract.id)

    assert payload['amount'] == 27600
    assert 'ستة' in payload['amount_words'] or 'سبعة' in payload['amount_words']
