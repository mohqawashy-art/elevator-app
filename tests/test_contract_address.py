"""عنوان موقع الخدمة — من العقد فقط."""
from __future__ import annotations

from contract_print import customer_address_line


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
        city='مكة',
    )
    line = customer_address_line(cust, contract)
    assert 'عنوان قديم' not in line
    assert 'شارع العقد 12' in line
    assert 'حي العقد' in line


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
