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
    """إنشاء عقد تركيب/تحديث CI- عند قبول العرض.

    ليس عقد صيانة: لا مدة تقويمية للتجديد — ينتهي بتسليم الأعمال عند إغلاق المشروع.
    """
    if getattr(project, 'contract_id', None):
        return tenant_query(Contract).filter_by(id=project.contract_id).first()
    customer_id = project.customer_id or getattr(quotation, 'customer_id', None)
    if not customer_id:
        return None
    qtype = (getattr(quotation, 'quote_type', None) or 'new').strip().lower()
    ctype = 'عقد تحديث' if qtype in ('upgrade', 'extend') else 'عقد تركيب'
    prefix = contract_prefix_for_type(ctype)
    code = next_code_fn(Contract, prefix, digits=CONTRACT_CODE_DIGITS)
    total = money_round(getattr(quotation, 'grand_total', 0) or 0)
    value = money_round(getattr(quotation, 'subtotal', None) or total)
    tax_amount = money_round(getattr(quotation, 'tax_amount', None) or max(total - value, 0))
    tax_pct = 15.0
    if value:
        tax_pct = money_round((tax_amount / value) * 100.0) if value else 15.0
    start = date.today()
    # end_date مؤقت (= البداية) حتى يُغلق المشروع ويُثبت تاريخ التسليم
    contract = Contract(
        code=code,
        customer_id=customer_id,
        contract_type=ctype,
        start_date=start,
        end_date=start,
        duration_months=None,
        reminder_date=None,
        value=value,
        tax_pct=tax_pct,
        tax_amount=tax_amount,
        total=total or money_round(value + tax_amount),
        payment_terms='حسب عرض السعر',
        invoice_status='غير مدفوع',
        paid_amount=0,
        status='نشط',
        install_warranty='بعد المشروع',
        notes=f'من عرض التركيب {quotation.code} — ينتهي بتسليم الأعمال',
    )
    assign_organization(contract)
    db.session.add(contract)
    db.session.flush()
    project.contract_id = contract.id
    return contract


def create_install_project_and_quote_from_estimate(estimate, *, next_project_code_fn, next_quote_code_fn):
    """تقدير تكلفة → مشروع تركيب + عرض سعر قابل للإرسال/القبول."""
    import json

    from installation.models import InstallProject, InstallQuotation, InstallQuotationLine
    from models import Customer

    if estimate.result_project_id and estimate.result_quotation_id:
        return {
            'project_id': estimate.result_project_id,
            'quotation_id': estimate.result_quotation_id,
            'created': False,
        }

    customer = None
    if estimate.customer_id:
        customer = tenant_query(Customer).filter_by(id=estimate.customer_id).first()

    title = (estimate.project_name or '').strip() or f'تقدير {estimate.code}'
    notes_parts = [f'من تقدير التكلفة {estimate.code}']
    if estimate.city:
        notes_parts.append(f'المدينة: {estimate.city}')
    project = InstallProject(
        code=next_project_code_fn(InstallProject, 'PRJ-', 4),
        title=title,
        status='تسعير',
        customer_id=estimate.customer_id,
        notes=' — '.join(notes_parts),
    )
    assign_organization(project)
    db.session.add(project)
    db.session.flush()

    materials = money_round(estimate.cost_subtotal)
    margin_pct = float(estimate.margin_pct or 12)
    cost = materials
    profit = money_round(cost * margin_pct / 100.0)
    before = money_round(cost + profit)
    vat_pct = float(estimate.vat_pct if estimate.vat_pct is not None else 15)
    vat = money_round(before * vat_pct / 100.0)
    # إن وُجدت مجاميع محفوظة في التقدير نفضّلها
    if estimate.subtotal:
        before = money_round(estimate.subtotal)
    if estimate.vat_amount is not None and estimate.total:
        vat = money_round(estimate.vat_amount)
        profit = money_round(estimate.margin_amount)
    grand = money_round(estimate.total) if estimate.total else money_round(before + vat)

    q = InstallQuotation(
        code=next_quote_code_fn(InstallQuotation, 'Q-', 4),
        project_id=project.id,
        customer_id=estimate.customer_id,
        quote_type='new',
        status='مسودة',
        client_name=(customer.name if customer else None),
        client_phone=(getattr(customer, 'phone', None) if customer else None),
        client_address=(getattr(customer, 'address', None) if customer else None),
        valid_days=30,
        spec_json=json.dumps({
            'source_estimate': estimate.code,
            'machine_type': estimate.machine_type,
            'elev_type': estimate.elev_type,
            'floors': estimate.floors,
            'stops': estimate.stops,
            'capacity_kg': estimate.capacity_kg,
            'doors_count': estimate.doors_count,
            'speed': estimate.speed,
            'travel_m': estimate.travel_m,
            'city': estimate.city,
        }, ensure_ascii=False),
        labor=0,
        transport=0,
        other_costs=0,
        profit_pct=margin_pct,
        materials_total=materials,
        cost_total=materials,
        profit_amount=profit,
        before_tax=before,
        vat_amount=vat,
        grand_total=grand,
        pay_advance_pct=50,
        pay_supply_pct=40,
        pay_final_pct=10,
    )
    assign_organization(q)
    db.session.add(q)
    db.session.flush()

    for sort_i, ln in enumerate(estimate.lines or [], start=1):
        row = InstallQuotationLine(
            quotation_id=q.id,
            sort_order=sort_i,
            stage=(ln.category or 'تقدير')[:100],
            name=(ln.description or ln.category or 'بند')[:300],
            qty=float(ln.quantity or 1),
            unit=(ln.unit or 'وحدة')[:40],
            unit_price=money_round(ln.unit_price),
        )
        assign_organization(row)
        db.session.add(row)

    estimate.result_project_id = project.id
    estimate.result_quotation_id = q.id
    estimate.status = 'محوّل لعرض سعر'
    return {
        'project_id': project.id,
        'quotation_id': q.id,
        'created': True,
        'project_code': project.code,
        'quote_code': q.code,
    }
