"""بيانات التقارير — مصدر واحد للصفحات وواجهات API."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import extract, case
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query


def get_report_clients(db, Customer, contract_display_status):
    customers = tenant_query(Customer).order_by(Customer.id).all()
    return [{
        'code': c.code,
        'name': c.name,
        'city': c.city or '',
        'district': c.district or '',
        'phone': c.phone or '',
        'elevators': len(c.elevators),
        'contracts': len(c.contracts),
        'contract_status': contract_display_status(c.contracts[0]) if c.contracts else 'بدون عقد',
        'status': c.status,
    } for c in customers]


def get_report_elevators(db, Elevator):
    elevs = tenant_query(Elevator).order_by(Elevator.id).all()
    return [{
        'code': e.code,
        'customer': e.customer.name,
        'building': e.building_name or '',
        'city': e.city or '',
        'elev_type': e.elev_type or '',
        'brand': e.brand or '',
        'capacity': str(e.capacity_kg or '') + ' كجم' if e.capacity_kg else '',
        'status': e.status,
        'next_maint': str(e.next_maintenance or ''),
    } for e in elevs]


def get_report_contracts(db, Contract):
    contracts = tenant_query(Contract).order_by(Contract.id).all()
    return [{
        'code': c.code,
        'customer': c.customer.name,
        'contract_type': c.contract_type or '',
        'start_date': str(c.start_date or ''),
        'end_date': str(c.end_date or ''),
        'elevators': len(c.elevators),
        'value': c.value or 0,
        'total': c.total or 0,
        'status': c.status,
        'inv_status': c.invoice_status or '',
    } for c in contracts]


def get_report_technicians(db, Technician):
    techs = tenant_query(Technician).order_by(Technician.id).all()
    return [{
        'code': t.code,
        'name': t.name,
        'phone': t.phone or '',
        'job_title': t.job_title or '',
        'specialization': t.specialization or '',
        'city': t.city or '',
        'status': t.status,
        'emergency': 'نعم' if t.emergency else 'لا',
        'visits': len(t.visits),
    } for t in techs]


def get_report_visits(db, MaintenanceVisit):
    visits = tenant_query(MaintenanceVisit).order_by(MaintenanceVisit.visit_date.desc()).all()
    return [{
        'code': v.code,
        'customer': v.elevator.customer.name,
        'elevator': v.elevator.code,
        'technician': v.technician.name if v.technician else '—',
        'visit_type': v.visit_type or '',
        'visit_date': str(v.visit_date or ''),
        'visit_time': str(v.visit_time or '') if v.visit_time else '—',
        'priority': v.priority or '',
        'status': v.status,
    } for v in visits]


def get_report_faults(db, Fault):
    faults = tenant_query(Fault).order_by(Fault.reported_at.desc()).all()
    return [{
        'code': f.code,
        'customer': f.elevator.customer.name,
        'elevator': f.elevator.code,
        'fault_type': f.fault_type or '',
        'priority': f.priority or '',
        'technician': f.technician.name if f.technician else '—',
        'response': f.response_time or '—',
        'status': f.status,
        'billed': 'مفوتر' if f.billed else 'غير مفوتر',
        'reported_date': f.reported_at.strftime('%Y-%m-%d') if f.reported_at else '',
    } for f in faults]


def get_report_revenues(db, Revenue, year=None, month=None):
    if year is None:
        year = datetime.now().year
    q = tenant_query(Revenue)
    if year:
        q = q.filter(extract('year', Revenue.revenue_date) == int(year))
    if month:
        q = q.filter(extract('month', Revenue.revenue_date) == int(month))
    revs = q.order_by(Revenue.revenue_date.desc()).all()
    return [{
        'code': r.code,
        'customer': r.customer.name if r.customer else '—',
        'contract': r.contract.code if r.contract else '—',
        'date': str(r.revenue_date or ''),
        'revenue_type': r.revenue_type or '',
        'pay_method': r.payment_method or '',
        'amount': r.amount or 0,
        'tax': r.tax_amount or 0,
        'total': r.total or 0,
        'status': r.status or '',
    } for r in revs]


def get_report_expenses(db, Expense, year=None, month=None):
    if year is None:
        year = datetime.now().year
    q = tenant_query(Expense)
    if year:
        q = q.filter(extract('year', Expense.expense_date) == int(year))
    if month:
        q = q.filter(extract('month', Expense.expense_date) == int(month))
    exps = q.order_by(Expense.expense_date.desc()).all()
    return [{
        'code': e.code,
        'date': str(e.expense_date or ''),
        'expense_type': e.expense_type or '',
        'description': e.description or '',
        'responsible': e.responsible or '',
        'pay_method': e.payment_method or '',
        'amount': e.amount or 0,
    } for e in exps]


def get_report_invoices(db, Invoice):
    invs = tenant_query(Invoice).order_by(Invoice.invoice_date.desc()).all()
    return [{
        'code': i.code,
        'invoice_type': i.invoice_type or '',
        'customer': i.customer.name if i.customer else '—',
        'contract': i.contract.code if i.contract else '—',
        'date': str(i.invoice_date or ''),
        'description': i.description or '',
        'amount': i.amount or 0,
        'tax': i.tax_amount or 0,
        'total': i.total or 0,
        'pay_method': i.payment_method or '',
        'status': i.status or '',
    } for i in invs]


def get_report_parts_billing(db, PartsBilling):
    rows = tenant_query(PartsBilling).order_by(PartsBilling.billing_date.desc()).all()
    return [{
        'code': p.code,
        'customer': p.customer.name if p.customer else '—',
        'contract': p.contract.code if p.contract else '—',
        'elevator': p.elevator.code if p.elevator else '—',
        'technician': p.technician.name if p.technician else '—',
        'date': str(p.billing_date or ''),
        'description': (p.description or '')[:120],
        'cost_price': p.cost_price or 0,
        'sell_price': p.sell_price or 0,
        'paid_amount': p.paid_amount or 0,
        'profit': p.profit or 0,
        'pay_method': p.payment_method or '',
        'status': p.status or '',
    } for p in rows]


def get_report_inventory(db, InventoryItem):
    items = tenant_query(InventoryItem).order_by(InventoryItem.id).all()
    return [{
        'code': i.code,
        'name': i.name,
        'category': i.category or '',
        'current_qty': i.current_qty or 0,
        'unit': i.unit or '',
        'min_qty': i.min_qty or 0,
        'buy_price': i.buy_price or 0,
        'stock_value': i.stock_value,
        'supplier': i.supplier or '',
        'order_status': i.order_status,
    } for i in items]


def get_report_stock(db, StockMovement):
    movements = tenant_query(StockMovement).order_by(StockMovement.movement_date.desc()).all()
    return [{
        'code': m.code,
        'date': str(m.movement_date or ''),
        'direction': m.direction or '',
        'movement_type': m.movement_type or '',
        'item': m.item.name,
        'item_code': m.item.code,
        'quantity': m.quantity or 0,
        'unit_price': m.unit_price or 0,
        'total_value': m.total_value or 0,
        'technician': m.technician.name if m.technician else '—',
        'reason': m.reason or '',
    } for m in movements]



AR_MONTHS = [
    '', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
]


def _round_money(value):
    return round(float(value or 0), 2)


def _revenue_total(revenue):
    if (revenue.status or '').strip() == 'ملغي':
        return 0.0
    return float(revenue.total or 0)


def _classify_revenue(revenue_type):
    rt = (revenue_type or '').strip()
    if rt in ('عقد جديد', 'عقد تركيب') or ('جديد' in rt and 'عقد' in rt):
        return 'new'
    if 'قطع غيار' in rt or rt in ('زيارة', 'أعمال إضافية', 'بيع قطع غيار'):
        return 'parts'
    if rt in (
        'تجديد عقد', 'عقد صيانة', 'عقد ضمان', 'صيانة',
    ) or ('عقد' in rt and 'جديد' not in rt):
        return 'renewed'
    return 'renewed'


def _classify_expense(expense_type):
    et = (expense_type or '').strip()
    if et == 'قطع غيار' or 'قطع غيار' in et:
        return 'parts'
    if et in (
        'محروقات', 'صيانة سيارات', 'صيانه سيارات', 'رواتب', 'وقود', 'أدوات',
        'مصروفات أساسية', 'مصروفات اساسية',
    ):
        return 'basic'
    return 'other'


def _sum_revenues(revenues):
    buckets = {'renewed': 0.0, 'parts': 0.0, 'new': 0.0}
    for r in revenues:
        key = _classify_revenue(r.revenue_type)
        buckets[key] += _revenue_total(r)
    total = sum(buckets.values())
    return {
        'total': _round_money(total),
        'renewed': _round_money(buckets['renewed']),
        'parts': _round_money(buckets['parts']),
        'new': _round_money(buckets['new']),
    }


def _sum_expenses(expenses):
    buckets = {'basic': 0.0, 'parts': 0.0, 'other': 0.0}
    for e in expenses:
        key = _classify_expense(e.expense_type)
        buckets[key] += float(e.amount or 0)
    total = sum(buckets.values())
    return {
        'total': _round_money(total),
        'basic': _round_money(buckets['basic']),
        'parts': _round_money(buckets['parts']),
        'other': _round_money(buckets['other']),
    }


def _filter_revenues(Revenue, *, year=None, month=None, on_date=None, date_from=None, date_to=None):
    q = tenant_query(Revenue)
    if year is not None:
        q = q.filter(extract('year', Revenue.revenue_date) == int(year))
    if month is not None:
        q = q.filter(extract('month', Revenue.revenue_date) == int(month))
    if on_date is not None:
        q = q.filter(Revenue.revenue_date == on_date)
    if date_from is not None:
        q = q.filter(Revenue.revenue_date >= date_from)
    if date_to is not None:
        q = q.filter(Revenue.revenue_date <= date_to)
    return q.all()


def _filter_expenses(Expense, *, year=None, month=None, on_date=None, date_from=None, date_to=None):
    q = tenant_query(Expense)
    if year is not None:
        q = q.filter(extract('year', Expense.expense_date) == int(year))
    if month is not None:
        q = q.filter(extract('month', Expense.expense_date) == int(month))
    if on_date is not None:
        q = q.filter(Expense.expense_date == on_date)
    if date_from is not None:
        q = q.filter(Expense.expense_date >= date_from)
    if date_to is not None:
        q = q.filter(Expense.expense_date <= date_to)
    return q.all()


def _parse_report_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip()[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def get_financial_report(db, Revenue, Expense, date_from=None, date_to=None, today=None):
    """ملخص مالي لفترة محددة (من — إلى)."""
    if today is None:
        today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date(today.year, 1, 1)
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    revenues = _filter_revenues(Revenue, date_from=date_from, date_to=date_to)
    expenses = _filter_expenses(Expense, date_from=date_from, date_to=date_to)

    rev = _sum_revenues(revenues)
    exp = _sum_expenses(expenses)

    return {
        'date_from': str(date_from),
        'date_to': str(date_to),
        'revenues': rev,
        'expenses': exp,
        'net': _round_money(rev['total'] - exp['total']),
    }


def _month_bounds(year, month):
    from calendar import monthrange
    year, month = int(year), int(month)
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _contract_forecast_amount(contract):
    return float(contract.total or contract.value or 0)


def _collected_for_contract_in_period(Revenue, contract_id, date_from, date_to):
    revs = tenant_query(Revenue).filter(
        Revenue.contract_id == contract_id,
        Revenue.revenue_date >= date_from,
        Revenue.revenue_date <= date_to,
    ).all()
    return _round_money(sum(_revenue_total(r) for r in revs))


def _renewal_collection_status(expected, collected):
    if expected <= 0.01:
        return '—'
    if collected >= expected - 0.01:
        return 'محصّل'
    if collected > 0:
        return 'محصّل جزئياً'
    return 'متوقع'


def get_contract_renewal_forecast(Contract, Revenue, year, month, contract_status_fn=None):
    """توقع تحصيل تجديد العقود — العقود المنتهية في الشهر المحدد."""
    year, month = int(year), int(month)
    first, last = _month_bounds(year, month)

    contracts = tenant_query(Contract).filter(
        Contract.end_date >= first,
        Contract.end_date <= last,
        Contract.status != 'ملغي',
    ).order_by(Contract.end_date).all()

    rows = []
    total_expected = 0.0
    total_collected = 0.0

    for c in contracts:
        expected = _contract_forecast_amount(c)
        collected = _collected_for_contract_in_period(Revenue, c.id, first, last)
        pending = _round_money(max(expected - collected, 0))
        total_expected += expected
        total_collected += collected
        rows.append({
            'code': c.code,
            'customer': c.customer.name if c.customer else '—',
            'customer_id': c.customer_id,
            'contract_type': c.contract_type or '',
            'end_date': str(c.end_date or ''),
            'status': contract_status_fn(c) if contract_status_fn else (c.status or ''),
            'elevators': len(c.elevators),
            'expected': _round_money(expected),
            'collected': collected,
            'pending': pending,
            'collection_status': _renewal_collection_status(expected, collected),
        })

    return {
        'year': year,
        'month': month,
        'month_label': AR_MONTHS[month] if 1 <= month <= 12 else str(month),
        'date_from': str(first),
        'date_to': str(last),
        'contracts': rows,
        'summary': {
            'count': len(rows),
            'expected': _round_money(total_expected),
            'collected': _round_money(total_collected),
            'pending': _round_money(max(total_expected - total_collected, 0)),
        },
    }


def get_contract_renewal_overview(Contract, Revenue, months_ahead=12, today=None, contract_status_fn=None):
    """ملخص شهري لتحصيلات التجديد للأشهر القادمة."""
    if today is None:
        today = date.today()
    months_ahead = max(1, min(int(months_ahead or 12), 24))

    y, m = today.year, today.month
    overview = []
    for _ in range(months_ahead):
        block = get_contract_renewal_forecast(
            Contract, Revenue, y, m, contract_status_fn=contract_status_fn,
        )
        overview.append({
            'year': y,
            'month': m,
            'month_label': block['month_label'],
            'count': block['summary']['count'],
            'expected': block['summary']['expected'],
            'collected': block['summary']['collected'],
            'pending': block['summary']['pending'],
        })
        m += 1
        if m > 12:
            m = 1
            y += 1
    return overview


def _monthly_totals(db, extract, func, year, date_col, value_col, exclude_cancelled=False, status_col=None):
    """مجاميع شهرية (12 شهراً) لعمود قيمة."""
    result = [0.0] * 12
    q = db.session.query(
        extract('month', date_col).label('m'),
        func.sum(value_col),
    ).filter(extract('year', date_col) == int(year))
    if exclude_cancelled and status_col is not None:
        q = q.filter(status_col != 'ملغي')
    rows = q.group_by('m').all()
    for m, val in rows:
        result[int(m) - 1] = round(float(val or 0), 2)
    return result


def _expense_buckets(expenses):
    buckets = {
        'fuel': 0.0, 'parts': 0.0, 'salaries': 0.0,
        'vehicles': 0.0, 'other': 0.0,
    }
    for e in expenses:
        et = (e.expense_type or '').strip()
        amt = float(e.amount or 0)
        if et in ('محروقات', 'وقود'):
            buckets['fuel'] += amt
        elif et == 'قطع غيار':
            buckets['parts'] += amt
        elif et in ('رواتب',) or 'راتب' in (e.description or ''):
            buckets['salaries'] += amt
        elif et in ('مصروفات أساسية', 'مصروفات اساسية'):
            buckets['other'] += amt
        elif et == 'صيانة سيارات':
            buckets['vehicles'] += amt
        else:
            buckets['other'] += amt
    return {k: _round_money(v) for k, v in buckets.items()}


def _health_label(margin_pct, net):
    if net < -0.01:
        return 'خسارة', 'danger'
    if margin_pct >= 15:
        return 'ممتاز', 'success'
    if margin_pct >= 5:
        return 'جيد', 'success'
    if margin_pct >= 0:
        return 'متوازن', 'warning'
    return 'ضعيف', 'danger'


def get_financial_health_report(
    db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit,
    year=None, today=None, contract_status_fn=None, target_margin=0.20,
):
    """تقرير الصحة المالية: رسوم، ربحية، توصيات التعافي، وتسعير العقود."""
    from sqlalchemy import extract, func

    if today is None:
        today = date.today()
    if year is None:
        year = today.year
    year = int(year)

    monthly_revenue = _monthly_totals(
        db, extract, func, year, Revenue.revenue_date, Revenue.total,
        exclude_cancelled=True, status_col=Revenue.status,
    )
    monthly_expenses = _monthly_totals(
        db, extract, func, year, Expense.expense_date, Expense.amount,
    )
    monthly_profit = [
        _round_money(monthly_revenue[i] - monthly_expenses[i]) for i in range(12)
    ]

    total_revenue = _round_money(sum(monthly_revenue))
    total_expenses = _round_money(sum(monthly_expenses))
    net_profit = _round_money(total_revenue - total_expenses)
    margin_pct = _round_money(net_profit / total_revenue * 100) if total_revenue else 0.0
    health_text, health_level = _health_label(margin_pct, net_profit)

    year_expenses = tenant_query(Expense).filter(extract('year', Expense.expense_date) == year).all()
    exp_buckets = _expense_buckets(year_expenses)

    tech_salaries = _round_money(sum(
        float(t.salary or 0) for t in tenant_query(Technician).filter(
            Technician.status.in_(['نشط', 'متاح', 'مشغول'])
        ).all()
    ))
    if tech_salaries > 0:
        exp_buckets['salaries'] = _round_money(exp_buckets['salaries'] + tech_salaries)

    expense_breakdown = {
        'محروقات ووقود': exp_buckets['fuel'],
        'قطع غيار وزيوت': exp_buckets['parts'],
        'رواتب وأجور': exp_buckets['salaries'],
        'صيانة سيارات': exp_buckets['vehicles'],
        'مصروفات أخرى': exp_buckets['other'],
    }

    active_contracts = []
    for c in tenant_query(Contract).filter(Contract.status != 'ملغي').all():
        st = contract_status_fn(c) if contract_status_fn else (c.status or '')
        if st in ('نشط', 'على وشك الانتهاء'):
            active_contracts.append(c)

    elevators_under_contract = sum(len(c.elevators) for c in active_contracts)
    if elevators_under_contract == 0:
        elevators_under_contract = tenant_query(Elevator).filter(
            Elevator.status.in_(['نشط', 'تحت الصيانة'])
        ).count()

    annual_visits_planned = sum((c.visits_per_month or 1) * 12 for c in active_contracts)
    contract_values = [_contract_forecast_amount(c) for c in active_contracts]
    elevator_values = []
    for c in active_contracts:
        n = len(c.elevators) or 1
        elevator_values.append(_contract_forecast_amount(c) / n)
    avg_elevator_value = _round_money(
        sum(elevator_values) / len(elevator_values) if elevator_values else 0
    )
    avg_contract_value = _round_money(
        sum(contract_values) / len(contract_values) if contract_values else 0
    )
    avg_elevators_per_contract = (
        round(elevators_under_contract / len(active_contracts), 2)
        if active_contracts else 0
    )

    visits_done = int(db.session.query(func.count(MaintenanceVisit.id)).filter(
        extract('year', MaintenanceVisit.visit_date) == year,
        MaintenanceVisit.status == 'مكتملة',
    ).scalar() or 0)
    visits_for_pricing = annual_visits_planned or visits_done or 1

    variable_cost = exp_buckets['fuel'] + exp_buckets['parts']
    fixed_cost = exp_buckets['salaries'] + exp_buckets['vehicles'] + exp_buckets['other']
    operating_cost = _round_money(max(total_expenses, variable_cost + fixed_cost))
    cost_per_visit = _round_money(variable_cost / visits_for_pricing) if visits_for_pricing else 0.0
    cost_per_elevator_year = _round_money(
        operating_cost / elevators_under_contract
    ) if elevators_under_contract else 0.0

    elevator_cost_estimates = []
    fixed_per_contract = (
        fixed_cost / len(active_contracts) if active_contracts else 0
    )
    visits_per_elevator = []
    for c in active_contracts:
        n_elev = len(c.elevators) or 1
        visits_y = (c.visits_per_month or 1) * 12
        visits_per_elevator.append(round(visits_y / n_elev, 1))
        contract_cost = cost_per_visit * visits_y + fixed_per_contract
        elevator_cost_estimates.append(contract_cost / n_elev)
    avg_visits_per_elevator = (
        round(sum(visits_per_elevator) / len(visits_per_elevator), 1)
        if visits_per_elevator else 0
    )
    estimated_cost_per_elevator = _round_money(
        sum(elevator_cost_estimates) / len(elevator_cost_estimates)
        if elevator_cost_estimates else cost_per_elevator_year
    )
    suggested_elevator_price = _round_money(
        (estimated_cost_per_elevator or cost_per_elevator_year) * (1 + target_margin)
    )

    pricing = {
        'annual_operating_cost': operating_cost,
        'variable_cost': _round_money(variable_cost),
        'fixed_cost': _round_money(fixed_cost),
        'active_contracts': len(active_contracts),
        'elevators_under_contract': elevators_under_contract,
        'annual_visits_planned': annual_visits_planned,
        'visits_completed': visits_done,
        'cost_per_visit': cost_per_visit,
        'cost_per_elevator_year': cost_per_elevator_year,
        'avg_elevator_value': avg_elevator_value,
        'avg_contract_value': avg_contract_value,
        'avg_elevators_per_contract': avg_elevators_per_contract,
        'avg_visits_per_elevator': avg_visits_per_elevator,
        'estimated_cost_per_elevator': estimated_cost_per_elevator,
        'suggested_elevator_price': suggested_elevator_price,
        'target_margin_pct': round(target_margin * 100, 1),
        'price_gap': _round_money(suggested_elevator_price - avg_elevator_value),
    }

    recommendations = []
    if net_profit < -0.01:
        gap = abs(net_profit)
        if avg_contract_value > 0:
            import math
            need = math.ceil(gap / avg_contract_value)
            recommendations.append({
                'icon': 'contracts',
                'title': 'زيادة عدد العقود',
                'text': f'تحتاج نحو {need} عقداً جديداً بمتوسط قيمة {avg_contract_value:,.2f} ريال لتغطية الخسارة.',
                'value': need,
            })
        if active_contracts:
            inc = _round_money(gap / len(active_contracts))
            recommendations.append({
                'icon': 'price',
                'title': 'رفع أسعار العقود',
                'text': f'رفع قيمة كل عقد نشط ({len(active_contracts)} عقد) بمقدار {inc:,.2f} ريال سنوياً.',
                'value': inc,
            })
        if total_expenses > 0:
            pct = _round_money(gap / total_expenses * 100)
            recommendations.append({
                'icon': 'cost',
                'title': 'خفض المصروفات',
                'text': f'خفض إجمالي المصروفات بنسبة {pct:.1f}% للوصول لنقطة التعادل.',
                'value': pct,
            })
        if pricing['price_gap'] > 0:
            recommendations.append({
                'icon': 'pricing',
                'title': 'مراجعة تسعير الصيانة',
                'text': (
                    f'متوسط قيمة المصعد الحالية ({avg_elevator_value:,.2f} ريال) أقل من التكلفة المقترحة '
                    f'({suggested_elevator_price:,.2f} ريال للمصعد) — راجع أسعار العقود.'
                ),
                'value': pricing['price_gap'],
            })
    elif margin_pct < 5 and active_contracts:
        recommendations.append({
            'icon': 'pricing',
            'title': 'تحسين الهامش',
            'text': 'الهامش منخفض — راجع تكاليف المحروقات وقطع الغيار أو ارفع قيمة العقود تدريجياً.',
            'value': margin_pct,
        })

    return {
        'year': year,
        'summary': {
            'revenue': total_revenue,
            'expenses': total_expenses,
            'profit': net_profit,
            'margin_pct': margin_pct,
            'health': health_text,
            'health_level': health_level,
            'parts_profit_note': None,
        },
        'monthly': {
            'revenue': monthly_revenue,
            'expenses': monthly_expenses,
            'profit': monthly_profit,
        },
        'expense_breakdown': expense_breakdown,
        'pricing': pricing,
        'recommendations': recommendations,
        'is_loss': net_profit < -0.01,
    }


REPORT_FETCHERS = {
    'report-clients': lambda ctx: get_report_clients(ctx['db'], ctx['Customer'], ctx['contract_display_status']),
    'report-elevators': lambda ctx: get_report_elevators(ctx['db'], ctx['Elevator']),
    'report-contracts': lambda ctx: get_report_contracts(ctx['db'], ctx['Contract']),
    'report-technicians': lambda ctx: get_report_technicians(ctx['db'], ctx['Technician']),
    'report-maintenance': lambda ctx: get_report_visits(ctx['db'], ctx['MaintenanceVisit']),
    'report-faults': lambda ctx: get_report_faults(ctx['db'], ctx['Fault']),
    'report-revenues': lambda ctx: get_report_revenues(ctx['db'], ctx['Revenue']),
    'report-expenses': lambda ctx: get_report_expenses(ctx['db'], ctx['Expense']),
    'report-invoices': lambda ctx: get_report_invoices(ctx['db'], ctx['Invoice']),
    'report-parts': lambda ctx: get_report_parts_billing(ctx['db'], ctx['PartsBilling']),
    'report-inventory': lambda ctx: get_report_inventory(ctx['db'], ctx['InventoryItem']),
    'report-stock': lambda ctx: get_report_stock(ctx['db'], ctx['StockMovement']),
}


def fetch_report_rows(report_id, ctx):
    fn = REPORT_FETCHERS.get(report_id)
    if not fn:
        return []
    return fn(ctx)
