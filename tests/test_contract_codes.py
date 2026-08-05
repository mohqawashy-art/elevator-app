"""اختبارات ترقيم عقود التجديد."""
from contract_codes import (
    contract_base_code,
    contract_year_from_code,
    renewal_contract_code,
    unique_renewal_contract_code,
)


def test_contract_base_code_strips_year():
    assert contract_base_code('CN-00042') == 'CN-00042'
    assert contract_base_code('CN-00042-2025') == 'CN-00042'
    assert contract_base_code('CN-00042/2025') == 'CN-00042'
    assert contract_base_code('CN-00042-2025-2') == 'CN-00042'


def test_renewal_contract_code_appends_year():
    assert renewal_contract_code('CN-00042', 2026) == 'CN-00042-2026'
    assert renewal_contract_code('CN-00042-2025', 2026) == 'CN-00042-2026'
    assert renewal_contract_code('CN-00042/2024', 2026) == 'CN-00042-2026'


def test_unique_renewal_adds_suffix_on_collision():
    taken = {'CN-00042-2026'}
    assert unique_renewal_contract_code('CN-00042', 2026, taken) == 'CN-00042-2026-2'
    taken.add('CN-00042-2026-2')
    assert unique_renewal_contract_code('CN-00042-2025', 2026, taken) == 'CN-00042-2026-3'


def test_contract_year_from_code():
    assert contract_year_from_code('CN-00042') is None
    assert contract_year_from_code('CN-00042-2026') == 2026
