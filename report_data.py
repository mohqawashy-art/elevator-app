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
        'door_type': e.door_type or '',
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
        'due_date': str(getattr(c, 'due_date', None) or ''),
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
    from entity_links import natural_code_key

    visits = tenant_query(MaintenanceVisit).all()
    visits = sorted(
        visits,
        key=lambda v: (
            natural_code_key(v.code),
            v.visit_date or date.min,
            v.id or 0,
        ),
    )
    return [{
        'code': v.code,
        'customer': v.elevator.customer.name if v.elevator and v.elevator.customer else '—',
        'elevator': v.elevator.code if v.elevator else '—',
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


_COLLECTED_REVENUE_STATUSES = frozenset({'محصّل', 'محصل', 'مدفوع', 'مدفوعة'})
_PENDING_REVENUE_STATUSES = frozenset({'معلق', 'غير محصّل', 'غير محصل'})


def summarize_revenue_rows(rows):
    """إجماليات الإيرادات — مصدر واحد لصفحة الإيرادات وتقرير الإيرادات."""
    total = 0.0
    collected = 0.0
    pending = 0.0
    cancelled = 0.0
    count = len(rows)
    cancelled_count = 0
    for row in rows:
        if isinstance(row, dict):
            st = (row.get('status') or '').strip()
            amt = float(row.get('total') or 0)
        else:
            st = (getattr(row, 'status', None) or '').strip()
            amt = float(getattr(row, 'total', None) or 0)
        total += amt
        if st == 'ملغي':
            cancelled += amt
            cancelled_count += 1
            continue
        if st in _COLLECTED_REVENUE_STATUSES:
            collected += amt
        if st in _PENDING_REVENUE_STATUSES:
            pending += amt
    return {
        'total': _round_money(total),
        'collected': _round_money(collected),
        'pending': _round_money(pending),
        'cancelled': _round_money(cancelled),
        'count': count,
        'cancelled_count': cancelled_count,
    }


def _revenues_report_query(Revenue, year=None, month=None):
    from sqlalchemy.orm import joinedload

    q = tenant_query(Revenue).options(
        joinedload(Revenue.customer),
        joinedload(Revenue.contract),
    )
    if year is not None:
        q = q.filter(extract('year', Revenue.revenue_date) == int(year))
    if month is not None:
        q = q.filter(extract('month', Revenue.revenue_date) == int(month))
    return q.order_by(Revenue.revenue_date.desc())


def _revenue_report_row_dict(r):
    return {
        'code': r.code,
        'customer': r.customer.name if r.customer else '—',
        'contract': r.contract.code if r.contract else '—',
        'date': str(r.revenue_date or ''),
        'title': getattr(r, 'title', None) or '',
        'revenue_type': r.revenue_type or '',
        'pay_method': r.payment_method or '',
        'amount': r.amount or 0,
        'tax': r.tax_amount or 0,
        'total': r.total or 0,
        'status': r.status or '',
        'created_by': (getattr(r, 'created_by_name', None) or '—'),
    }


def get_revenue_report_payload(db, Revenue, year=None, month=None):
    revs = _revenues_report_query(Revenue, year=year, month=month).all()
    rows = [_revenue_report_row_dict(r) for r in revs]
    return {
        'rows': rows,
        'summary': summarize_revenue_rows(rows),
    }


def get_report_revenues(db, Revenue, year=None, month=None):
    return get_revenue_report_payload(db, Revenue, year=year, month=month)['rows']


def get_report_expenses(db, Expense, year=None, month=None):
    q = tenant_query(Expense)
    if year is not None:
        q = q.filter(extract('year', Expense.expense_date) == int(year))
    if month is not None:
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
        'created_by': (getattr(e, 'created_by_name', None) or '—'),
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
    if rt in ('عقد جديد', 'عقد تركيب', 'عقد تحديث') or ('جديد' in rt and 'عقد' in rt):
        return 'new'
    if 'قطع غيار' in rt or rt in ('زيارة', 'أعمال إضافية', 'بيع قطع غيار'):
        return 'parts'
    if rt in (
        'تجديد عقد', 'الدفعات المستحقة', 'عقد صيانة', 'عقد ضمان', 'صيانة',
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


_MONTH_NAMES_AR = (
    'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
)


def _parse_report_date(raw):
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw).strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _month_keys_between(date_from: date, date_to: date) -> list[tuple[int, int]]:
    """قائمة (سنة، شهر) من تاريخ البداية إلى النهاية شاملة."""
    if date_to < date_from:
        date_from, date_to = date_to, date_from
    keys = []
    y, m = date_from.year, date_from.month
    while (y, m) <= (date_to.year, date_to.month):
        keys.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return keys


def _period_monthly_totals(
    db, extract, func, date_from, date_to, date_col, value_col,
    exclude_cancelled=False, status_col=None,
):
    """مجاميع شهرية لفترة من→إلى مع تسميات عربية."""
    month_keys = _month_keys_between(date_from, date_to)
    index = {k: i for i, k in enumerate(month_keys)}
    result = [0.0] * len(month_keys)
    multi_year = date_from.year != date_to.year
    labels = [
        f'{_MONTH_NAMES_AR[m - 1]} {y}' if multi_year else _MONTH_NAMES_AR[m - 1]
        for y, m in month_keys
    ]

    q = db.session.query(
        extract('year', date_col).label('y'),
        extract('month', date_col).label('m'),
        func.sum(value_col),
    ).filter(
        date_col >= date_from,
        date_col <= date_to,
    )
    if exclude_cancelled and status_col is not None:
        q = q.filter(status_col != 'ملغي')
    rows = q.group_by('y', 'm').all()
    for y, m, val in rows:
        key = (int(y), int(m))
        if key in index:
            result[index[key]] = round(float(val or 0), 2)
    return labels, result


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
        elif et == 'قطع غيار' or 'قطع غيار' in et:
            buckets['parts'] += amt
        elif et in ('رواتب',) or 'راتب' in (e.description or ''):
            buckets['salaries'] += amt
        elif et in ('مصروفات أساسية', 'مصروفات اساسية'):
            buckets['other'] += amt
        elif et in ('صيانة سيارات', 'صيانه سيارات'):
            buckets['vehicles'] += amt
        else:
            buckets['other'] += amt
    return {k: _round_money(v) for k, v in buckets.items()}


def _build_health_tips(
    *,
    health_text,
    health_level,
    margin_pct,
    net_profit,
    total_revenue,
    total_expenses,
    maint,
    pricing,
    visits_done,
    visits_planned,
    active_contracts_count,
    avg_contract_value,
):
    """نصائح واقتراحات دائمة — تُبرز دائماً في التقرير."""
    tips = []
    maint_total = float(maint.get('total') or 0)
    maint_pct = float(maint.get('pct_of_expenses') or 0)
    cost_visit = float(pricing.get('cost_per_visit') or 0)
    price_gap = float(pricing.get('price_gap') or 0)
    suggested = float(pricing.get('suggested_elevator_price') or 0)
    avg_elev = float(pricing.get('avg_elevator_value') or 0)

    if health_level == 'danger' and net_profit < -0.01:
        tips.append({
            'priority': 'high',
            'category': 'وضع مالي',
            'title': 'الوضع الحالي: خسارة',
            'text': (
                f'صافي الفترة سالب بمقدار {abs(net_profit):,.2f} ريال. '
                'ركّز على زيادة التحصيل أو خفض مصروفات الصيانة المباشرة أولاً.'
            ),
            'action': 'راجع قائمة العقود غير المحصّلة وبنود المحروقات وقطع الغيار',
        })
    elif health_level == 'warning':
        tips.append({
            'priority': 'medium',
            'category': 'وضع مالي',
            'title': f'الوضع: {health_text} — هامش ضعيف',
            'text': (
                f'هامش الربح {margin_pct:.1f}% فقط. الهدف التشغيلي المعتاد حوالي 15–20% '
                'لتغطية الطوارئ والتجديدات.'
            ),
            'action': 'ارفع تسعير العقود الجديدة أو راجع تكاليف الزيارة',
        })
    else:
        tips.append({
            'priority': 'low',
            'category': 'وضع مالي',
            'title': f'الوضع: {health_text}',
            'text': (
                f'صافي الربح {net_profit:,.2f} ريال بهامش {margin_pct:.1f}%. '
                'حافظ على السيطرة على مصروفات الصيانة ولا تُهمل التحصيل.'
            ),
            'action': 'تابع المستحقات شهرياً وراقب تكلفة الزيارة',
        })

    tips.append({
        'priority': 'high' if maint_pct >= 70 else ('medium' if maint_pct >= 45 else 'low'),
        'category': 'مصروفات صيانة',
        'title': 'مصروفات الصيانة التشغيلية',
        'text': (
            f'مصروفات الصيانة في الفترة: {maint_total:,.2f} ريال '
            f'({maint_pct:.0f}% من إجمالي المصروفات). '
            f'تشمل محروقات {maint.get("fuel", 0):,.2f}، '
            f'قطع غيار {maint.get("parts", 0):,.2f}، '
            f'صيانة سيارات {maint.get("vehicles", 0):,.2f}، '
            f'ورواتب فنيين {maint.get("salaries", 0):,.2f}.'
        ),
        'action': 'قارن تكلفة الزيارة مع إيراد العقد لكل مصعد',
    })

    if cost_visit > 0:
        tips.append({
            'priority': 'medium' if cost_visit > 150 else 'low',
            'category': 'كفاءة الصيانة',
            'title': 'تكلفة الزيارة',
            'text': (
                f'متوسط تكلفة الزيارة من مصروفات الصيانة المباشرة '
                f'(محروقات + قطع غيار) ≈ {cost_visit:,.2f} ريال. '
                f'الزيارات المكتملة: {visits_done} من المخطط {visits_planned}.'
            ),
            'action': 'حسّن مسارات الفنيين وقلّل الزيارات غير الضرورية',
        })

    if price_gap > 50:
        tips.append({
            'priority': 'high',
            'category': 'تسعير',
            'title': 'فجوة تسعير الصيانة',
            'text': (
                f'متوسط قيمة المصعد الحالية {avg_elev:,.2f} ريال أقل من السعر المقترح '
                f'{suggested:,.2f} ريال (بفارق {price_gap:,.2f}). '
                'العقود الحالية قد لا تغطي تكلفة التشغيل بهامش آمن.'
            ),
            'action': 'راجع أسعار التجديد والعقود الجديدة',
        })

    if visits_planned > 0 and visits_done < visits_planned * 0.7:
        tips.append({
            'priority': 'medium',
            'category': 'تشغيل',
            'title': 'نقص في إنجاز الزيارات',
            'text': (
                f'أُنجز {visits_done} زيارة فقط من أصل {visits_planned} مخططة في الفترة '
                f'({_round_money(visits_done / visits_planned * 100) if visits_planned else 0}%). '
                'انخفاض الإنجاز يضعف جودة الخدمة ويزيد الأعطال لاحقاً.'
            ),
            'action': 'راجع جدول الصيانة الدورية وتوزيع الفنيين',
        })

    if net_profit < -0.01:
        gap = abs(net_profit)
        if avg_contract_value > 0:
            import math
            need = math.ceil(gap / avg_contract_value)
            tips.append({
                'priority': 'high',
                'category': 'تعافٍ',
                'title': 'زيادة العقود للتعادل',
                'text': (
                    f'لتغطية الخسارة تحتاج تقريباً {need} عقداً جديداً '
                    f'بمتوسط قيمة {avg_contract_value:,.2f} ريال.'
                ),
                'action': 'فعّل عروض التجديد والمبيعات على العملاء المحتملين',
            })
        if active_contracts_count > 0:
            inc = _round_money(gap / active_contracts_count)
            tips.append({
                'priority': 'medium',
                'category': 'تعافٍ',
                'title': 'رفع أسعار العقود النشطة',
                'text': (
                    f'رفع متوسط كل عقد من العقود النشطة ({active_contracts_count}) '
                    f'بمقدار {inc:,.2f} ريال يغطي فجوة الفترة.'
                ),
                'action': 'طبّق الزيادة عند التجديد أو بملاحق تعاقدية',
            })
        if total_expenses > 0:
            pct = _round_money(gap / total_expenses * 100)
            tips.append({
                'priority': 'medium',
                'category': 'تعافٍ',
                'title': 'خفض المصروفات',
                'text': f'خفض إجمالي المصروفات بنسبة {pct:.1f}% يصل بك لنقطة التعادل.',
                'action': 'ابدأ بمحروقات وقطع الغيار غير الضرورية',
            })
    elif margin_pct < 10 and total_revenue > 0:
        tips.append({
            'priority': 'medium',
            'category': 'تحسين',
            'title': 'تحسين الهامش',
            'text': (
                'الهامش أقل من 10%. راقب مصروفات الصيانة نسبةً للإيراد، '
                'وارفع أسعار العقود الجديدة تدريجياً.'
            ),
            'action': 'حدد سقفاً شهرياً للمحروقات وقطع الغيار',
        })

    order = {'high': 0, 'medium': 1, 'low': 2}
    tips.sort(key=lambda t: order.get(t.get('priority'), 9))
    return tips


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
    year=None, date_from=None, date_to=None, today=None,
    contract_status_fn=None, target_margin=0.20,
):
    """تقرير الصحة المالية: رسوم، ربحية، توصيات التعافي، وتسعير العقود.

    يدعم فترة من→إلى. إن وُجدت سنة فقط (توافق قديم) تُستخدم كامل تلك السنة.
    """
    from sqlalchemy import extract, func

    if today is None:
        today = date.today()

    df = _parse_report_date(date_from)
    dt = _parse_report_date(date_to)
    if df is None and dt is None and year is not None:
        year = int(year)
        df = date(year, 1, 1)
        dt = date(year, 12, 31)
    if df is None:
        df = date(today.year, 1, 1)
    if dt is None:
        dt = today
    if dt < df:
        df, dt = dt, df

    months_in_period = max(1, len(_month_keys_between(df, dt)))

    month_labels, monthly_revenue = _period_monthly_totals(
        db, extract, func, df, dt, Revenue.revenue_date, Revenue.total,
        exclude_cancelled=True, status_col=Revenue.status,
    )
    _, monthly_expenses = _period_monthly_totals(
        db, extract, func, df, dt, Expense.expense_date, Expense.amount,
    )
    monthly_profit = [
        _round_money(monthly_revenue[i] - monthly_expenses[i])
        for i in range(len(monthly_revenue))
    ]

    total_revenue = _round_money(sum(monthly_revenue))
    total_expenses = _round_money(sum(monthly_expenses))
    net_profit = _round_money(total_revenue - total_expenses)
    margin_pct = _round_money(net_profit / total_revenue * 100) if total_revenue else 0.0
    health_text, health_level = _health_label(margin_pct, net_profit)

    period_expenses = tenant_query(Expense).filter(
        Expense.expense_date >= df,
        Expense.expense_date <= dt,
    ).all()
    exp_buckets = _expense_buckets(period_expenses)

    tech_salaries_annual = _round_money(sum(
        float(t.salary or 0) for t in tenant_query(Technician).filter(
            Technician.status.in_(['نشط', 'متاح', 'مشغول'])
        ).all()
    ))
    if tech_salaries_annual > 0:
        tech_salaries_period = _round_money(tech_salaries_annual * (months_in_period / 12.0))
        exp_buckets['salaries'] = _round_money(exp_buckets['salaries'] + tech_salaries_period)

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

    # زيارات مخططة تناسب طول الفترة (شهري × عدد الأشهر)
    annual_visits_planned = sum((c.visits_per_month or 1) * months_in_period for c in active_contracts)
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
        MaintenanceVisit.visit_date >= df,
        MaintenanceVisit.visit_date <= dt,
        MaintenanceVisit.status == 'مكتملة',
    ).scalar() or 0)
    visits_for_pricing = annual_visits_planned or visits_done or 1

    variable_cost = exp_buckets['fuel'] + exp_buckets['parts']
    # مصروفات الصيانة التشغيلية (مباشرة + أسطول + رواتب فنيين)
    maintenance_total = _round_money(
        exp_buckets['fuel'] + exp_buckets['parts']
        + exp_buckets['vehicles'] + exp_buckets['salaries']
    )
    other_expenses = _round_money(exp_buckets['other'])
    # إجمالي المصروفات المعروض = المسجّل + رواتب تقديرية إن وُجدت
    expenses_for_pct = max(total_expenses, maintenance_total + other_expenses) or 1.0
    maintenance_costs = {
        'total': maintenance_total,
        'pct_of_expenses': _round_money(maintenance_total / expenses_for_pct * 100),
        'fuel': exp_buckets['fuel'],
        'parts': exp_buckets['parts'],
        'vehicles': exp_buckets['vehicles'],
        'salaries': exp_buckets['salaries'],
        'other': other_expenses,
        'items': [
            {
                'key': 'fuel',
                'label': 'محروقات ووقود',
                'hint': 'تنقل الفنيين لمواقع الصيانة',
                'amount': exp_buckets['fuel'],
                'is_maintenance': True,
            },
            {
                'key': 'parts',
                'label': 'قطع غيار وزيوت',
                'hint': 'قطع مستخدمة في الصيانة والأعطال',
                'amount': exp_buckets['parts'],
                'is_maintenance': True,
            },
            {
                'key': 'vehicles',
                'label': 'صيانة سيارات',
                'hint': 'أسطول خدمة الصيانة الميدانية',
                'amount': exp_buckets['vehicles'],
                'is_maintenance': True,
            },
            {
                'key': 'salaries',
                'label': 'رواتب الفنيين',
                'hint': 'تكلفة العمالة للصيانة الدورية',
                'amount': exp_buckets['salaries'],
                'is_maintenance': True,
            },
            {
                'key': 'other',
                'label': 'مصروفات أخرى (غير صيانة)',
                'hint': 'إدارية وضيافة ومتنوعة',
                'amount': other_expenses,
                'is_maintenance': False,
            },
        ],
    }

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
        visits_period = (c.visits_per_month or 1) * months_in_period
        visits_per_elevator.append(round(visits_period / n_elev, 1))
        contract_cost = cost_per_visit * visits_period + fixed_per_contract
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

    tips = _build_health_tips(
        health_text=health_text,
        health_level=health_level,
        margin_pct=margin_pct,
        net_profit=net_profit,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        maint=maintenance_costs,
        pricing=pricing,
        visits_done=visits_done,
        visits_planned=annual_visits_planned,
        active_contracts_count=len(active_contracts),
        avg_contract_value=avg_contract_value,
    )
    # توافق قديم للواجهة السابقة
    recommendations = [
        {
            'icon': t.get('category'),
            'title': t.get('title'),
            'text': t.get('text'),
            'value': None,
            'priority': t.get('priority'),
            'action': t.get('action'),
            'category': t.get('category'),
        }
        for t in tips
    ]

    period_label = f'{df.isoformat()} → {dt.isoformat()}'
    return {
        'year': df.year if df.year == dt.year else None,
        'date_from': df.isoformat(),
        'date_to': dt.isoformat(),
        'period_label': period_label,
        'summary': {
            'revenue': total_revenue,
            'expenses': total_expenses,
            'profit': net_profit,
            'margin_pct': margin_pct,
            'health': health_text,
            'health_level': health_level,
            'maintenance_expenses': maintenance_total,
            'other_expenses': other_expenses,
            'parts_profit_note': None,
        },
        'monthly': {
            'labels': month_labels,
            'revenue': monthly_revenue,
            'expenses': monthly_expenses,
            'profit': monthly_profit,
        },
        'expense_breakdown': expense_breakdown,
        'maintenance_costs': maintenance_costs,
        'pricing': pricing,
        'tips': tips,
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
