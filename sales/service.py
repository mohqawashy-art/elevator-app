"""خدمات تحويل عروض المبيعات لعقود/تركيب."""
from __future__ import annotations

import calendar
from datetime import date, datetime

from contract_codes import CONTRACT_CODE_DIGITS, contract_prefix_for_type
from models import Contract, ContractElevator, MaintenanceQuote, db
from tenant_scope import assign_organization, tenant_query


def add_months(d: date, months: int) -> date:
    months = int(months or 0)
    if months <= 0:
        return d
    m0 = d.month - 1 + months
    y = d.year + m0 // 12
    m = m0 % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def money_round(n) -> float:
    try:
        return round(float(n or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def recalc_quote_totals(quote: MaintenanceQuote) -> None:
    value = money_round(quote.value)
    tax_pct = money_round(quote.tax_pct if quote.tax_pct is not None else 15)
    tax_amount = money_round(value * tax_pct / 100.0)
    quote.value = value
    quote.tax_pct = tax_pct
    quote.tax_amount = tax_amount
    quote.total = money_round(value + tax_amount)


def sync_quote_elevators(quote_id: int, elevator_ids: list) -> None:
    from models import MaintenanceQuoteElevator

    tenant_query(MaintenanceQuoteElevator).filter_by(quote_id=quote_id).delete(
        synchronize_session=False
    )
    seen: set[int] = set()
    for eid in elevator_ids or []:
        try:
            eid_i = int(eid)
        except (TypeError, ValueError):
            continue
        if eid_i in seen:
            continue
        seen.add(eid_i)
        row = MaintenanceQuoteElevator(quote_id=quote_id, elevator_id=eid_i)
        assign_organization(row)
        db.session.add(row)


def create_contract_from_maintenance_quote(quote: MaintenanceQuote, *, next_code_fn) -> Contract:
    """إنشاء عقد صيانة CN- من عرض مقبول."""
    if quote.result_contract_id:
        existing = tenant_query(Contract).filter_by(id=quote.result_contract_id).first()
        if existing:
            return existing

    start = quote.start_date or date.today()
    months = int(quote.duration_months or 12)
    end = quote.end_date or add_months(start, months)
    prefix = contract_prefix_for_type('عقد صيانة')
    code = next_code_fn(Contract, prefix, digits=CONTRACT_CODE_DIGITS)

    contract = Contract(
        code=code,
        customer_id=quote.customer_id,
        contract_type='عقد صيانة',
        start_date=start,
        end_date=end,
        duration_months=months,
        maint_frequency=quote.maint_frequency,
        visits_per_month=quote.visits_per_month or 1,
        value=money_round(quote.value),
        tax_pct=money_round(quote.tax_pct),
        tax_amount=money_round(quote.tax_amount),
        total=money_round(quote.total),
        payment_terms=quote.payment_terms,
        invoice_status='غير مدفوع',
        paid_amount=0,
        status='نشط',
        city=quote.city,
        district=quote.district,
        address=quote.address,
        notes=(quote.notes or '')[:2000] or None,
    )
    assign_organization(contract)
    db.session.add(contract)
    db.session.flush()

    from models import MaintenanceQuoteElevator
    for link in tenant_query(MaintenanceQuoteElevator).filter_by(quote_id=quote.id).all():
        ce = ContractElevator(contract_id=contract.id, elevator_id=link.elevator_id)
        assign_organization(ce)
        db.session.add(ce)

    quote.result_contract_id = contract.id
    quote.status = 'مقبول'
    quote.approved_at = datetime.utcnow()
    return contract


def create_install_contract_from_quotation(project, quotation, *, next_code_fn) -> Contract | None:
    """إنشاء عقد تركيب CI- عند قبول عرض تركيب (إن لم يكن مربوطاً بعقد)."""
    if getattr(project, 'contract_id', None):
        return tenant_query(Contract).filter_by(id=project.contract_id).first()
    customer_id = project.customer_id or getattr(quotation, 'customer_id', None)
    if not customer_id:
        return None
    prefix = contract_prefix_for_type('عقد تركيب')
    code = next_code_fn(Contract, prefix, digits=CONTRACT_CODE_DIGITS)
    total = money_round(getattr(quotation, 'grand_total', 0) or 0)
    value = money_round(getattr(quotation, 'subtotal', None) or total)
    tax_amount = money_round(getattr(quotation, 'tax_amount', None) or max(total - value, 0))
    tax_pct = 15.0
    if value:
        tax_pct = money_round((tax_amount / value) * 100.0) if value else 15.0
    start = date.today()
    contract = Contract(
        code=code,
        customer_id=customer_id,
        contract_type='عقد تركيب',
        start_date=start,
        end_date=add_months(start, 12),
        duration_months=12,
        value=value,
        tax_pct=tax_pct,
        tax_amount=tax_amount,
        total=total or money_round(value + tax_amount),
        payment_terms='حسب عرض السعر',
        invoice_status='غير مدفوع',
        paid_amount=0,
        status='نشط',
        notes=f'من عرض التركيب {quotation.code}',
    )
    assign_organization(contract)
    db.session.add(contract)
    db.session.flush()
    project.contract_id = contract.id
    return contract
