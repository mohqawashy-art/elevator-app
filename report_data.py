"""بيانات التقارير — مصدر واحد للصفحات وواجهات API."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import extract, case


def get_report_clients(db, Customer, contract_display_status):
    customers = Customer.query.order_by(Customer.id).all()
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
    elevs = Elevator.query.order_by(Elevator.id).all()
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
    contracts = Contract.query.order_by(Contract.id).all()
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
    techs = Technician.query.order_by(Technician.id).all()
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
    visits = MaintenanceVisit.query.order_by(MaintenanceVisit.visit_date.desc()).all()
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
    faults = Fault.query.order_by(Fault.reported_at.desc()).all()
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
    q = Revenue.query
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
    q = Expense.query
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
    invs = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
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


def get_report_inventory(db, InventoryItem):
    items = InventoryItem.query.order_by(InventoryItem.id).all()
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
    movements = StockMovement.query.order_by(StockMovement.movement_date.desc()).all()
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


def get_report_parts(db, PartsBilling):
    parts = PartsBilling.query.order_by(PartsBilling.billing_date.desc()).all()
    return [{
        'code': p.code,
        'customer': p.customer.name if p.customer else '—',
        'contract': p.contract.code if p.contract else '—',
        'date': str(p.billing_date or ''),
        'description': p.description or '',
        'cost_price': p.cost_price or 0,
        'sell_price': p.sell_price or 0,
        'profit': p.profit or 0,
        'pay_method': p.payment_method or '',
        'status': p.status or '',
    } for p in parts]


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
    if et == 'قطع غيار':
        return 'parts'
    if et in ('محروقات', 'صيانة سيارات', 'رواتب', 'وقود', 'أدوات'):
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


def _filter_revenues(Revenue, *, year=None, month=None, on_date=None):
    q = Revenue.query
    if year is not None:
        q = q.filter(extract('year', Revenue.revenue_date) == int(year))
    if month is not None:
        q = q.filter(extract('month', Revenue.revenue_date) == int(month))
    if on_date is not None:
        q = q.filter(Revenue.revenue_date == on_date)
    return q.all()


def _filter_expenses(Expense, *, year=None, month=None, on_date=None):
    q = Expense.query
    if year is not None:
        q = q.filter(extract('year', Expense.expense_date) == int(year))
    if month is not None:
        q = q.filter(extract('month', Expense.expense_date) == int(month))
    if on_date is not None:
        q = q.filter(Expense.expense_date == on_date)
    return q.all()


def get_financial_report(db, Revenue, Expense, year=None, month=None, today=None):
    """ملخص مالي سنوي + يومي + شهري حسب التصنيفات المعتمدة في النظام."""
    if today is None:
        today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    year = int(year)
    month = int(month)

    annual_revenues = _filter_revenues(Revenue, year=year)
    annual_expenses = _filter_expenses(Expense, year=year)
    monthly_revenues = _filter_revenues(Revenue, year=year, month=month)
    monthly_expenses = _filter_expenses(Expense, year=year, month=month)
    today_revenues = _filter_revenues(Revenue, on_date=today)
    today_expenses = _filter_expenses(Expense, on_date=today)

    annual_rev = _sum_revenues(annual_revenues)
    annual_exp = _sum_expenses(annual_expenses)
    monthly_rev = _sum_revenues(monthly_revenues)
    monthly_exp = _sum_expenses(monthly_expenses)
    today_rev_total = _round_money(sum(_revenue_total(r) for r in today_revenues))
    today_exp_total = _round_money(sum(float(e.amount or 0) for e in today_expenses))

    return {
        'year': year,
        'month': month,
        'month_label': AR_MONTHS[month] if 1 <= month <= 12 else str(month),
        'today': str(today),
        'annual': {
            'revenues': annual_rev,
            'expenses': annual_exp,
            'net': _round_money(annual_rev['total'] - annual_exp['total']),
        },
        'monthly': {
            'revenues': monthly_rev,
            'expenses': monthly_exp,
            'net': _round_money(monthly_rev['total'] - monthly_exp['total']),
        },
        'today_summary': {
            'revenues': today_rev_total,
            'expenses': today_exp_total,
            'net': _round_money(today_rev_total - today_exp_total),
        },
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
    'report-inventory': lambda ctx: get_report_inventory(ctx['db'], ctx['InventoryItem']),
    'report-stock': lambda ctx: get_report_stock(ctx['db'], ctx['StockMovement']),
    'report-parts': lambda ctx: get_report_parts(ctx['db'], ctx['PartsBilling']),
}


def fetch_report_rows(report_id, ctx):
    fn = REPORT_FETCHERS.get(report_id)
    if not fn:
        return []
    return fn(ctx)
