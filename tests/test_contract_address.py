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
