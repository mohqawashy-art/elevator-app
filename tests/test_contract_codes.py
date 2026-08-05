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


def test_build_superseded_contract_ids():
    from types import SimpleNamespace
    from datetime import date
    from contract_codes import build_superseded_contract_ids

    old = SimpleNamespace(id=1, code='CN-00010', start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
    new = SimpleNamespace(id=2, code='CN-00010-2026', start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    alone = SimpleNamespace(id=3, code='CN-00099', start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))
    ids = build_superseded_contract_ids([old, new, alone])
    assert ids == {1}
