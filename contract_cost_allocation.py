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
    duration = contract_duration_months(contract)
    freq = (getattr(contract, 'maint_frequency', None) or '').strip()
    interval = MAINT_FREQ_INTERVAL_MONTHS.get(freq, 1)
    from_frequency = max(1, math.ceil(duration / interval))
    if v <= 0:
        return from_frequency
    # استيراد قديم: visits_per_month=1 رغم برنامج صيانة أكثر (مثلاً شهري × 12 شهر)
    if v == 1 and from_frequency > 1:
        return from_frequency
    return v


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


def _is_maintenance_contract(contract) -> bool:
    """عقود صيانة/ضمان — لا تشمل تركيب أو تحديث."""
    ct = (getattr(contract, 'contract_type', None) or '').strip()
    if not ct:
        return False
    if 'تركيب' in ct or 'تحديث' in ct:
        return False
    return any(k in ct for k in ('صيانة', 'ضمان', 'دوري'))


def count_completed_visits(
    contract,
    *,
    period_from: date | None = None,
    period_to: date | None = None,
) -> int:
    """عد الزيارات المكتملة لعقد — اختيارياً ضمن فترة."""
    from sqlalchemy import and_, or_

    from models import MaintenanceVisit
    from tenant_scope import tenant_query

    elev_ids = [
        int(ce.elevator_id) for ce in (getattr(contract, 'elevators', None) or [])
        if getattr(ce, 'elevator_id', None)
    ]
    q = tenant_query(MaintenanceVisit).filter(MaintenanceVisit.status == 'مكتملة')
    if period_from:
        q = q.filter(MaintenanceVisit.visit_date >= period_from)
    if period_to:
        q = q.filter(MaintenanceVisit.visit_date <= period_to)
    if elev_ids:
        q = q.filter(or_(
            MaintenanceVisit.contract_id == contract.id,
            and_(
                MaintenanceVisit.contract_id.is_(None),
                MaintenanceVisit.elevator_id.in_(elev_ids),
            ),
        ))
    else:
        q = q.filter(MaintenanceVisit.contract_id == contract.id)
    return q.count()


def _visit_counts_for_contracts(
    contracts: list,
    *,
    period_from: date | None = None,
    period_to: date | None = None,
) -> tuple[dict[int, int], dict[int, int]]:
    """عد زيارات مكتملة لكل عقد: (ضمن الفترة، حتى تاريخ النهاية)."""
    from sqlalchemy import and_, or_

    from models import MaintenanceVisit
    from tenant_scope import tenant_query

    contract_ids: list[int] = []
    elev_to_contract: dict[int, int] = {}
    for contract in contracts:
        cid = int(contract.id)
        contract_ids.append(cid)
        for ce in (getattr(contract, 'elevators', None) or []):
            eid = getattr(ce, 'elevator_id', None)
            if eid:
                elev_to_contract[int(eid)] = cid

    in_period = {cid: 0 for cid in contract_ids}
    to_date = {cid: 0 for cid in contract_ids}
    if not contract_ids:
        return in_period, to_date

    def owner(contract_id, elevator_id):
        if contract_id:
            return int(contract_id)
        if elevator_id and int(elevator_id) in elev_to_contract:
            return elev_to_contract[int(elevator_id)]
        return None

    clauses = []
    if contract_ids:
        clauses.append(MaintenanceVisit.contract_id.in_(contract_ids))
    if elev_to_contract:
        clauses.append(and_(
            MaintenanceVisit.contract_id.is_(None),
            MaintenanceVisit.elevator_id.in_(list(elev_to_contract.keys())),
        ))
    if not clauses:
        return in_period, to_date

    q = tenant_query(MaintenanceVisit).filter(
        MaintenanceVisit.status == 'مكتملة',
        or_(*clauses),
    )
    end = period_to or date.today()
    q = q.filter(MaintenanceVisit.visit_date <= end)

    for cid, eid, vdate in q.with_entities(
        MaintenanceVisit.contract_id,
        MaintenanceVisit.elevator_id,
        MaintenanceVisit.visit_date,
    ).all():
        key = owner(cid, eid)
        if key is None:
            continue
        to_date[key] = to_date.get(key, 0) + 1
        if period_from and vdate and vdate < period_from:
            continue
        in_period[key] = in_period.get(key, 0) + 1

    return in_period, to_date


def maintenance_contracts_pnl_summary(
    *,
    period_from: date | None = None,
    period_to: date | None = None,
) -> dict:
    """إيراد عقود الصيانة المستحق بالزيارات + المتبقي غير المكتسب."""
    from sqlalchemy.orm import joinedload

    from models import Contract
    from tenant_scope import tenant_query

    today = period_to or date.today()
    earned_in_period = 0.0
    unearned_total = 0.0
    contract_lines: list[dict] = []

    all_contracts = (
        tenant_query(Contract)
        .options(joinedload(Contract.elevators))
        .all()
    )
    maintenance_contracts = [c for c in all_contracts if _is_maintenance_contract(c)]
    visits_in_period, visits_to_date = _visit_counts_for_contracts(
        maintenance_contracts,
        period_from=period_from,
        period_to=period_to or today,
    )

    for contract in maintenance_contracts:
        alloc = contract_cost_allocation(contract)
        total = float(alloc.get('contract_total') or 0)
        per_visit = float(alloc.get('per_visit_value') or 0)
        planned = int(alloc.get('planned_visits') or 0)
        if total <= 0 or per_visit <= 0:
            continue

        cid = int(contract.id)
        visits_in_period_n = visits_in_period.get(cid, 0)
        visits_to_date_n = visits_to_date.get(cid, 0)
        earned_period = round(per_visit * visits_in_period_n, 2)
        earned_total = round(per_visit * visits_to_date_n, 2)
        unearned = round(max(total - earned_total, 0), 2)

        earned_in_period += earned_period
        unearned_total += unearned
        if earned_period > 0 or unearned > 0 or visits_to_date_n > 0:
            contract_lines.append({
                'code': contract.code,
                'contract_type': contract.contract_type or 'عقد صيانة',
                'contract_total': total,
                'planned_visits': planned,
                'completed_visits': visits_to_date_n,
                'visits_in_period': visits_in_period_n,
                'per_visit_value': per_visit,
                'earned_in_period': earned_period,
                'earned_total': earned_total,
                'unearned': unearned,
            })

    return {
        'earned_in_period': round(earned_in_period, 2),
        'unearned_total': round(unearned_total, 2),
        'contract_lines': contract_lines,
    }
