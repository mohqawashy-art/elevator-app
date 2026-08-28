"""اختبار توزيع قيمة العقد."""
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from contract_cost_allocation import contract_cost_allocation, contract_planned_visits, collection_gap_fields, collection_gap_status


class _ContractStub:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_year_contract_12_visits_monthly_and_per_visit():
    c = _ContractStub(
        total=12000,
        value=10434.78,
        duration_months=12,
        visits_per_month=12,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        maint_frequency='شهري',
    )
    a = contract_cost_allocation(c)
    assert a['monthly_accrual'] == 1000.0
    assert a['per_visit_value'] == 1000.0
    assert a['planned_visits'] == 12
    assert contract_planned_visits(c) == 12


def test_period_accrual_half_year():
    c = _ContractStub(
        total=12000,
        duration_months=12,
        visits_per_month=12,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        maint_frequency='شهري',
    )
    a = contract_cost_allocation(
        c,
        period_from=date(2026, 1, 1),
        period_to=date(2026, 6, 30),
    )
    # توزيع يومي: 181 يوم من 365
    assert a['period_accrued'] == round(12000 * 181 / 365, 2)
    assert a['period_overlap_days'] == 181


def test_visits_derived_from_frequency_when_missing():
    c = _ContractStub(
        total=6000,
        duration_months=12,
        visits_per_month=0,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        maint_frequency='ربع سنوي',
    )
    assert contract_planned_visits(c) == 4
    a = contract_cost_allocation(c, completed_visits=2)
    assert a['per_visit_value'] == 1500.0
    assert a['earned_by_visits'] == 3000.0


def test_collection_gap_fields():
    gap = collection_gap_fields(6000, 4000)
    assert gap['collected'] == 4000.0
    assert gap['collection_gap'] == 2000.0
    assert gap['collection_status'] == 'تحصيل جزئي'
    assert collection_gap_status(5000, 5000) == 'محصّل'
    assert collection_gap_status(5000, 0) == 'متأخر'
    assert collection_gap_status(0, 100) == '—'
