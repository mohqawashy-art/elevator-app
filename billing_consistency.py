"""G7 — اتساق كاش العقود / الفواتير / القطع مع الإيرادات."""

from __future__ import annotations

from datetime import date

from models import Contract, Invoice, PartsBilling, Revenue, db
from customer_billing import (
    COLLECTED_REVENUE_STATUSES,
    PAID_INVOICE_STATUSES,
    UNPAID_INVOICE_STATUSES,
    _round_money,
    contract_paid_amount,
    repair_contract_payment_links,
)


def revenue_paid_for_invoice(invoice_id: int) -> float:
    rows = Revenue.query.filter(
        Revenue.invoice_id == invoice_id,
        Revenue.status.in_(COLLECTED_REVENUE_STATUSES),
    ).all()
    return _round_money(sum(_round_money(r.total or 0) for r in rows))


def revenue_paid_for_parts(parts_id: int) -> float:
    rows = Revenue.query.filter(
        Revenue.parts_billing_id == parts_id,
        Revenue.status.in_(COLLECTED_REVENUE_STATUSES),
    ).all()
    return _round_money(sum(_round_money(r.total or 0) for r in rows))


def _contract_invoice_status(contract: Contract, paid: float, today: date | None = None) -> str:
    today = today or date.today()
    total = _round_money(contract.total or 0)
    paid = _round_money(paid)
    remaining = max(total - paid, 0)
    if total <= 0:
        return 'غير مدفوع'
    if remaining <= 0.01:
        return 'مدفوع'
    status = 'مدفوع جزئياً' if paid > 0 else 'غير مدفوع'
    overdue = Invoice.query.filter(
        Invoice.contract_id == contract.id,
        Invoice.due_date.isnot(None),
        Invoice.due_date < today,
        Invoice.status.in_(UNPAID_INVOICE_STATUSES),
    ).first()
    if overdue and remaining > 0.01:
        return 'متأخر'
    return status


def refresh_contract_cache(contract: Contract) -> bool:
    computed = contract_paid_amount(contract.id)
    stored = _round_money(contract.paid_amount or 0)
    status = _contract_invoice_status(contract, computed)
    changed = abs(stored - computed) > 0.01 or (contract.invoice_status or '') != status
    contract.paid_amount = computed
    contract.invoice_status = status
    return changed


def refresh_invoice_cache(inv: Invoice) -> bool:
    if 'سند' in (inv.invoice_type or ''):
        return False
    from_revenues = revenue_paid_for_invoice(inv.id)
    stored = _round_money(inv.paid_amount or 0)
    canonical = from_revenues
    if canonical <= 0.01 and (inv.status or '').strip() in PAID_INVOICE_STATUSES:
        canonical = _round_money(inv.total or 0)
    total = _round_money(inv.total or 0)
    if total <= 0:
        status = inv.status or 'غير مدفوعة'
    elif canonical >= total - 0.01:
        status = 'مدفوعة'
    elif canonical > 0.01:
        status = 'مدفوع جزئياً'
    else:
        status = 'غير مدفوعة'
    changed = abs(stored - canonical) > 0.01 or (inv.status or '') != status
    inv.paid_amount = canonical
    inv.status = status
    return changed


def refresh_parts_cache(pb: PartsBilling) -> bool:
    from_revenues = revenue_paid_for_parts(pb.id)
    stored = _round_money(pb.paid_amount or 0)
    canonical = from_revenues if from_revenues > 0.01 else stored
    total = _round_money(pb.sell_price or 0)
    if canonical >= total - 0.01 and total > 0:
        status = 'محصل'
    elif canonical > 0.01:
        status = 'غير محصل'
    else:
        status = pb.status or 'غير محصل'
    changed = abs(stored - canonical) > 0.01 or (pb.status or '') != status
    pb.paid_amount = canonical
    pb.status = status
    return changed


def audit_billing_consistency() -> dict:
    issues: list[dict] = []

    for c in Contract.query.all():
        computed = contract_paid_amount(c.id)
        stored = _round_money(c.paid_amount or 0)
        if abs(stored - computed) > 0.01:
            issues.append({
                'entity': 'contract',
                'id': c.id,
                'code': c.code,
                'stored': stored,
                'computed': computed,
                'delta': _round_money(computed - stored),
            })

    for inv in Invoice.query.all():
        if 'سند' in (inv.invoice_type or ''):
            continue
        from_rev = revenue_paid_for_invoice(inv.id)
        stored = _round_money(inv.paid_amount or 0)
        expected = from_rev
        if expected <= 0.01 and (inv.status or '').strip() in PAID_INVOICE_STATUSES:
            expected = _round_money(inv.total or 0)
        if abs(stored - expected) > 0.01 and abs(from_rev - stored) > 0.01:
            issues.append({
                'entity': 'invoice',
                'id': inv.id,
                'code': inv.code,
                'stored': stored,
                'computed': expected,
                'from_revenues': from_rev,
                'delta': _round_money(expected - stored),
            })

    for pb in PartsBilling.query.all():
        from_rev = revenue_paid_for_parts(pb.id)
        stored = _round_money(pb.paid_amount or 0)
        if from_rev > 0.01 and abs(stored - from_rev) > 0.01:
            issues.append({
                'entity': 'parts_billing',
                'id': pb.id,
                'code': pb.code,
                'stored': stored,
                'computed': from_rev,
                'delta': _round_money(from_rev - stored),
            })

    by_entity: dict[str, int] = {}
    for row in issues:
        by_entity[row['entity']] = by_entity.get(row['entity'], 0) + 1

    return {
        'ok': len(issues) == 0,
        'issue_count': len(issues),
        'by_entity': by_entity,
        'issues': issues[:200],
    }


def repair_billing_consistency(*, commit: bool = True) -> dict:
    links_fixed = repair_contract_payment_links(commit=False)

    contracts_changed = 0
    invoices_changed = 0
    parts_changed = 0

    for c in Contract.query.all():
        if refresh_contract_cache(c):
            contracts_changed += 1

    for inv in Invoice.query.all():
        if refresh_invoice_cache(inv):
            invoices_changed += 1

    for pb in PartsBilling.query.all():
        if refresh_parts_cache(pb):
            parts_changed += 1

    if commit:
        db.session.commit()

    audit = audit_billing_consistency()
    return {
        'links_fixed': links_fixed,
        'contracts_updated': contracts_changed,
        'invoices_updated': invoices_changed,
        'parts_updated': parts_changed,
        'remaining_issues': audit['issue_count'],
        'ok': audit['ok'],
    }


_ENTITY_LABELS = {
    'contract': 'عقد',
    'invoice': 'فاتورة',
    'parts_billing': 'قطع غيار',
}


def billing_discrepancies_report() -> dict:
    """تقرير H3 — فروقات كاش الفوترة مع سياق للواجهة."""
    audit = audit_billing_consistency()
    rows: list[dict] = []
    total_delta = 0.0

    for issue in audit.get('issues', []):
        entity = issue.get('entity', '')
        row_id = issue.get('id')
        customer_name = ''
        detail = ''

        if entity == 'contract':
            c = Contract.query.get(row_id)
            if c:
                customer_name = (c.customer.name if c.customer else '') or ''
                detail = c.contract_type or ''
        elif entity == 'invoice':
            inv = Invoice.query.get(row_id)
            if inv:
                customer_name = (inv.customer.name if inv.customer else '') or ''
                detail = (inv.invoice_type or inv.description or '')[:80]
        elif entity == 'parts_billing':
            pb = PartsBilling.query.get(row_id)
            if pb:
                customer_name = (pb.customer.name if pb.customer else '') or ''
                detail = (pb.description or '')[:80]

        delta = float(issue.get('delta') or 0)
        total_delta += abs(delta)
        rows.append({
            'entity': entity,
            'entity_label': _ENTITY_LABELS.get(entity, entity),
            'id': row_id,
            'code': issue.get('code') or '',
            'customer': customer_name,
            'detail': detail,
            'stored': issue.get('stored', 0),
            'computed': issue.get('computed', 0),
            'from_revenues': issue.get('from_revenues'),
            'delta': delta,
            'link': _entity_link(entity, row_id),
        })

    by_entity = audit.get('by_entity') or {}
    return {
        'ok': audit.get('ok', True),
        'issue_count': audit.get('issue_count', 0),
        'total_abs_delta': _round_money(total_delta),
        'contracts': by_entity.get('contract', 0),
        'invoices': by_entity.get('invoice', 0),
        'parts': by_entity.get('parts_billing', 0),
        'rows': rows,
        'generated_at': date.today().isoformat(),
    }


def _entity_link(entity: str, row_id: int | None) -> str:
    if not row_id:
        return ''
    if entity == 'contract':
        return f'/contracts?highlight={row_id}'
    if entity == 'invoice':
        return f'/invoices/{row_id}/print'
    if entity == 'parts_billing':
        return f'/parts-billing?highlight={row_id}'
    return ''
