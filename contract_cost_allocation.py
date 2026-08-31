"""توزيع قيمة العقد على مدة العقد والزيارات المخططة."""
from __future__ import annotations

import math
from datetime import date

MAINT_FREQ_INTERVAL_MONTHS = {
    'شهري': 1,
    'كل شهرين': 2,
    'ربع سنوي': 3,
    'نصف سنوي': 6,
    'سنوي': 12,
}


def contract_duration_months(contract) -> int:
    """مدة العقد بالأشهر (من الحقل أو من التواريخ)."""
    dm = int(getattr(contract, 'duration_months', None) or 0)
    if dm > 0:
        return dm
    start = getattr(contract, 'start_date', None)
    end = getattr(contract, 'end_date', None)
    if start and end and end > start:
        return max(1, (end.year - start.year) * 12 + (end.month - start.month))
    return 1


def contract_planned_visits(contract) -> int:
    """إجمالي الزيارات المخططة (visits_per_month = إجمالي العقد وليس شهرياً)."""
    v = int(getattr(contract, 'visits_per_month', None) or 0)
    if v > 0:
        return v
    duration = contract_duration_months(contract)
    freq = (getattr(contract, 'maint_frequency', None) or '').strip()
    interval = MAINT_FREQ_INTERVAL_MONTHS.get(freq, 1)
    return max(1, math.ceil(duration / interval))


def _contract_total(contract) -> float:
    return float(getattr(contract, 'total', None) or getattr(contract, 'value', None) or 0)


def _contract_days(contract) -> int:
    start = getattr(contract, 'start_date', None)
    end = getattr(contract, 'end_date', None)
    if not start or not end or end < start:
        return 0
    return (end - start).days + 1


def _overlap_days(period_start: date, period_end: date, range_start: date, range_end: date) -> int:
    s = max(period_start, range_start)
    e = min(period_end, range_end)
    if e < s:
        return 0
    return (e - s).days + 1


def contract_cost_allocation(
    contract,
    *,
    period_from: date | None = None,
    period_to: date | None = None,
    completed_visits: int | None = None,
) -> dict:
    """حساب توزيع قيمة العقد: استحقاق شهري، قيمة/زيارة، و(اختياري) استحقاق الفترة."""
    total = _contract_total(contract)
    duration = contract_duration_months(contract)
    visits = contract_planned_visits(contract)
    contract_days = _contract_days(contract)

    monthly = round(total / duration, 2) if duration and total else 0.0
    per_visit = round(total / visits, 2) if visits and total else 0.0

    result = {
        'contract_total': round(total, 2),
        'duration_months': duration,
        'planned_visits': visits,
        'monthly_accrual': monthly,
        'per_visit_value': per_visit,
        'contract_days': contract_days,
    }

    start = getattr(contract, 'start_date', None)
    end = getattr(contract, 'end_date', None)
    if period_from and period_to and contract_days > 0 and start and end:
        overlap = _overlap_days(period_from, period_to, start, end)
        result['period_accrued'] = round(total * overlap / contract_days, 2)
        result['period_overlap_days'] = overlap

    if completed_visits is not None:
        cv = int(completed_visits or 0)
        result['completed_visits'] = cv
        result['earned_by_visits'] = round(per_visit * cv, 2)

    return result


def collection_gap_status(accrued: float, collected: float) -> str:
    """حالة التحصيل مقابل المستحق."""
    accrued = float(accrued or 0)
    collected = float(collected or 0)
    if accrued <= 0.01:
        return '—'
    if collected >= accrued - 0.01:
        return 'محصّل'
    if collected > 0:
        return 'تحصيل جزئي'
    return 'متأخر'


def collection_gap_fields(accrued: float, collected: float) -> dict:
    """المحصّل، فجوة التحصيل (مستحق − محصّل)، والحالة."""
    accrued = round(float(accrued or 0), 2)
    collected = round(float(collected or 0), 2)
    return {
        'collected': collected,
        'collection_gap': round(accrued - collected, 2),
        'collection_status': collection_gap_status(accrued, collected),
    }
