"""تحصيل الإيرادات — عمليات غير محصّلة وكشف حساب العميل."""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy import or_

from models import Contract, Customer, Invoice, PartsBilling, Revenue, db

COLLECTED_REVENUE_STATUSES = ('محصّل', 'محصل')
UNPAID_INVOICE_STATUSES = ['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً']
PAID_INVOICE_STATUSES = ['مدفوعة', 'مدفوع', 'محصّل']
UNPAID_PARTS_STATUSES = ('غير محصل', 'معلقة', 'بانتظار موافقة العميل', 'بانتظار التوريد')
CONTRACT_REVENUE_KEYWORDS = ('عقد', 'صيانة', 'ضمان', 'تجديد')
_CN_CODE_RE = re.compile(r'(CN-\d+)', re.I)


def _round_money(v: float) -> float:
    return round(float(v or 0), 2)


def _extract_contract_code(*texts) -> str | None:
    for text in texts:
        if not text:
            continue
        match = _CN_CODE_RE.search(str(text))
        if match:
            return match.group(1).upper()
    return None


def _is_contract_revenue_type(revenue_type: str) -> bool:
    t = (revenue_type or '').strip()
    return any(keyword in t for keyword in CONTRACT_REVENUE_KEYWORDS)


def _invoice_paid_total(inv: Invoice) -> float:
    paid = _round_money(getattr(inv, 'paid_amount', 0) or 0)
    if paid <= 0.01 and (inv.status or '').strip() in PAID_INVOICE_STATUSES:
        paid = _round_money(inv.total or 0)
    return paid


def resolve_contract_id(
    customer_id: int | None,
    reference: str = '',
    notes: str = '',
    description: str = '',
    revenue_type: str = '',
    revenue_id: int | None = None,
) -> int | None:
    """ربط الإيراد/الفاتورة بالعقد من الكود أو السياق."""
    if not customer_id:
        return None

    code = _extract_contract_code(reference, notes, description)
    if code:
        contract = Contract.query.filter_by(code=code, customer_id=customer_id).first()
        if contract:
            return contract.id

    if revenue_id:
        rev = Revenue.query.get(revenue_id)
        if rev:
            if rev.contract_id:
                return rev.contract_id
            if rev.invoice_id:
                inv = Invoice.query.get(rev.invoice_id)
                if inv and inv.contract_id:
                    return inv.contract_id
                if inv:
                    inv_code = _extract_contract_code(inv.description, inv.notes)
                    if inv_code:
                        contract = Contract.query.filter_by(
                            code=inv_code, customer_id=customer_id
                        ).first()
                        if contract:
                            return contract.id

    if _is_contract_revenue_type(revenue_type):
        active = [
            c for c in Contract.query.filter_by(customer_id=customer_id)
            .order_by(Contract.start_date.desc())
            .all()
            if _contract_is_collectible(c)
        ]
        if len(active) == 1:
            return active[0].id

    return None


def repair_contract_payment_links(commit: bool = True) -> int:
    """إصلاح الربط الناقص بين الإيرادات/الفواتير والعقود."""
    changed = 0

    for rev in Revenue.query.filter(
        Revenue.contract_id.is_(None),
        Revenue.customer_id.isnot(None),
    ).all():
        cid = resolve_contract_id(
            rev.customer_id,
            rev.reference or '',
            rev.notes or '',
            '',
            rev.revenue_type or '',
            revenue_id=rev.id,
        )
        if cid:
            rev.contract_id = cid
            changed += 1

    for inv in Invoice.query.filter(
        Invoice.contract_id.is_(None),
        Invoice.customer_id.isnot(None),
    ).all():
        cid = resolve_contract_id(
            inv.customer_id,
            '',
            inv.notes or '',
            inv.description or '',
        )
        if not cid:
            rev = Revenue.query.filter_by(invoice_id=inv.id).first()
            if rev and rev.contract_id:
                cid = rev.contract_id
        if cid:
            inv.contract_id = cid
            changed += 1

    if changed and commit:
        db.session.commit()
    return changed


SOURCE_REVENUE_TYPES = {
    'contract': 'تجديد عقد',
    'invoice': 'عقد جديد',
    'parts_billing': 'قطع غيار',
}


def invoice_remaining(inv: Invoice) -> float:
    total = _round_money(inv.total)
    paid = _round_money(getattr(inv, 'paid_amount', 0) or 0)
    return max(total - paid, 0)


def parts_remaining(pb: PartsBilling) -> float:
    total = _round_money(pb.sell_price)
    paid = _round_money(getattr(pb, 'paid_amount', 0) or 0)
    return max(total - paid, 0)


def contract_paid_amount(contract_id: int) -> float:
    """مجموع المحصّل على العقد — إيرادات + فواتير (مباشرة أو عبر كود العقد)."""
    if not contract_id:
        return 0.0

    contract = Contract.query.get(contract_id)
    if not contract:
        return 0.0

    rev_rows = Revenue.query.filter(
        Revenue.contract_id == contract_id,
        Revenue.status.in_(COLLECTED_REVENUE_STATUSES),
    ).all()
    rev_paid = _round_money(sum(_round_money(r.total or 0) for r in rev_rows))

    linked_by_invoice: dict[int, float] = {}
    for r in rev_rows:
        if not r.invoice_id:
            continue
        inv_id = int(r.invoice_id)
        linked_by_invoice[inv_id] = linked_by_invoice.get(inv_id, 0.0) + _round_money(r.total or 0)

    inv_extra = 0.0
    for inv in Invoice.query.filter_by(contract_id=contract_id).all():
        inv_paid = _invoice_paid_total(inv)
        linked = linked_by_invoice.get(inv.id, 0.0)
        inv_extra += max(0.0, inv_paid - linked)

    code = (contract.code or '').upper()
    customer_id = contract.customer_id

    orphan_revs = Revenue.query.filter(
        Revenue.customer_id == customer_id,
        Revenue.contract_id.is_(None),
        Revenue.status.in_(COLLECTED_REVENUE_STATUSES),
    ).all()
    for rev in orphan_revs:
        amount = _round_money(rev.total or 0)
        if amount <= 0.01:
            continue
        matched = resolve_contract_id(
            customer_id,
            rev.reference or '',
            rev.notes or '',
            '',
            rev.revenue_type or '',
            revenue_id=rev.id,
        )
        if matched == contract_id:
            rev_paid += amount
            continue
        if code and code in f'{rev.reference or ""} {rev.notes or ""}':
            rev_paid += amount

    orphan_invs = Invoice.query.filter(
        Invoice.customer_id == customer_id,
        Invoice.contract_id.is_(None),
    ).all()
    for inv in orphan_invs:
        inv_paid = _invoice_paid_total(inv)
        if inv_paid <= 0.01:
            continue
        matched = resolve_contract_id(
            customer_id,
            '',
            inv.notes or '',
            inv.description or '',
        )
        if matched == contract_id:
            inv_extra += inv_paid
            continue
        if code and code in f'{inv.description or ""} {inv.notes or ""}':
            inv_extra += inv_paid

    return _round_money(rev_paid + inv_extra)


def contract_remaining(contract: Contract) -> float:
    return max(_round_money(contract.total) - contract_paid_amount(contract.id), 0)


def _contract_is_collectible(contract: Contract, today: date | None = None) -> bool:
    today = today or date.today()
    if (contract.status or '').strip() in ('ملغي', 'ملغى'):
        return False
    if contract.end_date and contract.end_date < today:
        return False
    return True


def _invoice_exists_for_parts(parts_id: int) -> bool:
    return Invoice.query.filter_by(parts_billing_id=parts_id).first() is not None


def _invoice_exists_for_contract(contract_id: int) -> bool:
    return Invoice.query.filter_by(contract_id=contract_id).first() is not None


def customer_billable_ops(customer_id: int) -> list[dict]:
    """عمليات جاهزة لإصدار فاتورة عليها (لم تُفوتر بعد)."""
    rows: list[dict] = []
    today = date.today()

    for pb in (
        PartsBilling.query.filter_by(customer_id=customer_id)
        .order_by(PartsBilling.billing_date.desc())
        .all()
    ):
        if _invoice_exists_for_parts(pb.id):
            continue
        total = _round_money(pb.sell_price)
        if total <= 0.01:
            continue
        paid = _round_money(getattr(pb, 'paid_amount', 0) or 0)
        collected = paid >= total - 0.01 or (pb.status or '') in ('محصل', 'محصّل', 'مكتملة')
        rows.append({
            'source_type': 'parts_billing',
            'source_id': pb.id,
            'code': pb.code,
            'date': str(pb.billing_date or ''),
            'title': 'تركيب قطع غيار',
            'description': (pb.description or 'قطع غيار')[:200],
            'amount_before_tax': round(total / 1.15, 2),
            'total': total,
            'paid': paid,
            'remaining': max(total - paid, 0),
            'contract_id': pb.contract_id,
            'contract_code': pb.contract.code if pb.contract else '',
            'fault_code': pb.fault.code if pb.fault else '',
            'visit_code': pb.visit.code if pb.visit else '',
            'status': pb.status or 'غير محصل',
            'collected': collected,
            'hint': 'تم التحصيل — إصدار فاتورة للتوثيق' if collected else 'غير محصّل — فاتورة ثم تحصيل',
        })

    for c in Contract.query.filter_by(customer_id=customer_id).order_by(Contract.start_date.desc()).all():
        if not _contract_is_collectible(c, today):
            continue
        if _invoice_exists_for_contract(c.id):
            continue

        total = _round_money(c.total)
        if total <= 0.01:
            continue

        paid = contract_paid_amount(c.id)
        remaining = contract_remaining(c)
        collected = remaining <= 0.01 and paid >= total - 0.01

        if Invoice.query.filter(
            Invoice.contract_id == c.id,
            Invoice.status.in_(UNPAID_INVOICE_STATUSES),
        ).first():
            continue

        if not collected and remaining <= 0.01:
            continue

        bill_total = total if collected else remaining
        rows.append({
            'source_type': 'contract',
            'source_id': c.id,
            'code': c.code,
            'date': str(c.start_date or ''),
            'title': c.contract_type or 'عقد',
            'description': f'فاتورة عقد {c.code} — {c.contract_type or "صيانة"}',
            'amount_before_tax': round(bill_total / 1.15, 2),
            'total': bill_total,
            'paid': paid,
            'remaining': max(remaining, 0),
            'contract_id': c.id,
            'contract_code': c.code,
            'fault_code': '',
            'visit_code': '',
            'status': c.invoice_status or 'غير مدفوع',
            'collected': collected,
            'hint': (
                'تم تحصيل العقد — إصدار فاتورة للتوثيق'
                if collected
                else 'غير محصّل بالكامل — فاتورة ثم تحصيل'
            ),
        })

    rows.sort(key=lambda x: (x['date'], x['code']), reverse=True)
    return rows


def _fmt_date_dmy(d) -> str:
    if not d:
        return '—'
    return d.strftime('%d/%m/%Y')


def _is_renewal_revenue(revenue: Revenue) -> bool:
    rev_type = (revenue.revenue_type or '').strip()
    if 'تجديد' in rev_type:
        return True
    if rev_type in ('تجديد عقد', 'عقد صيانة', 'صيانة', 'عقد ضمان') and revenue.contract_id:
        return True
    return False


def invoice_description_for_revenue(revenue: Revenue) -> str:
    """بيان الحساب للفاتورة عند الربط بإيراد محصّل."""
    rev_type = (revenue.revenue_type or '').strip()
    contract = revenue.contract

    if contract and _is_renewal_revenue(revenue):
        return (
            'تجديد عقد صيانة مصاعد عن الفترة '
            f'من {_fmt_date_dmy(contract.start_date)} إلى {_fmt_date_dmy(contract.end_date)}'
        )

    if revenue.parts_billing_id and revenue.parts_billing:
        pb = revenue.parts_billing
        desc = (pb.description or '').strip()
        if desc:
            return desc
        return f'تركيب قطع غيار — {pb.code}'

    if rev_type == 'قطع غيار':
        notes = (revenue.notes or '').strip()
        if notes:
            return notes
        return f'قطع غيار — {revenue.code}'

    if rev_type == 'عقد جديد' and contract:
        return (
            'عقد جديد صيانة مصاعد عن الفترة '
            f'من {_fmt_date_dmy(contract.start_date)} إلى {_fmt_date_dmy(contract.end_date)}'
        )

    if contract:
        return (
            f'{rev_type or "خدمة"} — عقد {contract.code} '
            f'من {_fmt_date_dmy(contract.start_date)} إلى {_fmt_date_dmy(contract.end_date)}'
        )

    notes = (revenue.notes or '').strip()
    if notes:
        return notes
    ref = (revenue.reference or '').strip()
    if ref:
        return ref
    return rev_type or f'إيراد {revenue.code}'


def customer_invoicable_revenues(customer_id: int) -> list[dict]:
    """إيرادات محصّلة لم تُربط بفاتورة بعد — لإصدار فاتورة ضريبية."""
    rows: list[dict] = []
    revs = (
        Revenue.query.filter_by(customer_id=customer_id)
        .filter(Revenue.status.in_(COLLECTED_REVENUE_STATUSES))
        .filter(Revenue.invoice_id.is_(None))
        .order_by(Revenue.revenue_date.desc())
        .all()
    )
    for r in revs:
        invoice_desc = invoice_description_for_revenue(r)
        contract = r.contract
        rows.append({
            'source_type': 'revenue',
            'source_id': r.id,
            'code': r.code,
            'date': str(r.revenue_date or ''),
            'title': r.revenue_type or 'إيراد',
            'description': invoice_desc,
            'invoice_description': invoice_desc,
            'revenue_type': r.revenue_type or '',
            'amount_before_tax': _round_money(r.amount),
            'total': _round_money(r.total),
            'paid': _round_money(r.total),
            'remaining': 0,
            'contract_id': r.contract_id,
            'contract_code': contract.code if contract else '',
            'contract_start': str(contract.start_date or '') if contract else '',
            'contract_end': str(contract.end_date or '') if contract else '',
            'is_renewal': _is_renewal_revenue(r),
            'parts_billing_id': r.parts_billing_id,
            'collected': True,
            'hint': 'تم التحصيل — إصدار فاتورة للتوثيق',
            'payment_method': r.payment_method or '',
            'reference': r.reference or '',
        })

    rows.sort(key=lambda x: (x['date'], x['code']), reverse=True)
    return rows


def customer_uncollected_ops(customer_id: int) -> list[dict]:
    """عمليات العميل غير المحصّلة بالكامل."""
    rows: list[dict] = []
    today = date.today()

    contracts = (
        Contract.query.filter_by(customer_id=customer_id)
        .order_by(Contract.start_date.desc())
        .all()
    )
    for c in contracts:
        remaining = contract_remaining(c)
        if remaining <= 0.01 or not _contract_is_collectible(c, today):
            continue
        paid = contract_paid_amount(c.id)
        rows.append({
            'source_type': 'contract',
            'source_id': c.id,
            'code': c.code,
            'date': str(c.start_date or ''),
            'title': c.contract_type or 'عقد',
            'description': f'عقد {c.code} — المتبقي على قيمة العقد',
            'total': _round_money(c.total),
            'paid': paid,
            'remaining': remaining,
            'amount_before_tax': round(remaining / 1.15, 2),
            'contract_id': c.id,
            'status': c.invoice_status or 'غير مدفوع',
            'collected': False,
            'hint': f'غير محصّل — المتبقي {_round_money(remaining)}',
        })

    invoices = (
        Invoice.query.filter_by(customer_id=customer_id)
        .order_by(Invoice.invoice_date.desc())
        .all()
    )
    for inv in invoices:
        remaining = invoice_remaining(inv)
        if remaining <= 0.01:
            continue
        if inv.status in PAID_INVOICE_STATUSES and remaining <= 0.01:
            continue
        rows.append({
            'source_type': 'invoice',
            'source_id': inv.id,
            'code': inv.code,
            'date': str(inv.invoice_date or ''),
            'title': inv.invoice_type or 'فاتورة',
            'description': inv.description or inv.invoice_type or 'فاتورة',
            'total': _round_money(inv.total),
            'paid': _round_money(getattr(inv, 'paid_amount', 0) or 0),
            'remaining': remaining,
            'amount_before_tax': round(remaining / 1.15, 2),
            'contract_id': inv.contract_id,
            'status': inv.status or 'غير مدفوعة',
            'collected': False,
            'hint': f'غير محصّل — المتبقي {_round_money(remaining)}',
        })

    parts = (
        PartsBilling.query.filter_by(customer_id=customer_id)
        .order_by(PartsBilling.billing_date.desc())
        .all()
    )
    for pb in parts:
        if (pb.status or '') not in UNPAID_PARTS_STATUSES and parts_remaining(pb) <= 0.01:
            continue
        remaining = parts_remaining(pb)
        if remaining <= 0.01:
            continue
        rows.append({
            'source_type': 'parts_billing',
            'source_id': pb.id,
            'code': pb.code,
            'date': str(pb.billing_date or ''),
            'title': 'تركيب قطع غيار',
            'description': (pb.description or 'قطع غيار')[:120],
            'total': _round_money(pb.sell_price),
            'paid': _round_money(getattr(pb, 'paid_amount', 0) or 0),
            'remaining': remaining,
            'amount_before_tax': round(remaining / 1.15, 2),
            'contract_id': pb.contract_id,
            'status': pb.status or 'غير محصل',
            'fault_code': pb.fault.code if pb.fault else '',
            'visit_code': pb.visit.code if pb.visit else '',
            'collected': False,
            'hint': f'غير محصّل — المتبقي {_round_money(remaining)}',
        })

    rows.sort(key=lambda x: (x['date'], x['code']), reverse=True)
    return rows


def apply_payment_to_source(
    source_type: str,
    source_id: int,
    payment_total: float,
) -> dict:
    """تسجيل دفعة على عملية — payment_total = إجمالي التحصيل (شامل الضريبة)."""
    payment_total = _round_money(payment_total)
    if payment_total <= 0:
        raise ValueError('مبلغ التحصيل يجب أن يكون أكبر من صفر')

    if source_type == 'contract':
        c = Contract.query.get_or_404(int(source_id))
        remaining = contract_remaining(c)
        if payment_total > remaining + 0.01:
            raise ValueError(f'المبلغ أكبر من المتبقي على العقد ({remaining:.2f})')
        return {
            'customer_id': c.customer_id,
            'contract_id': c.id,
            'invoice_id': None,
            'parts_billing_id': None,
            'revenue_type': SOURCE_REVENUE_TYPES['contract'],
            'reference_note': f'تحصيل عقد {c.code}',
        }

    if source_type == 'invoice':
        inv = Invoice.query.get_or_404(int(source_id))
        remaining = invoice_remaining(inv)
        if payment_total > remaining + 0.01:
            raise ValueError(f'المبلغ أكبر من المتبقي على الفاتورة ({remaining:.2f})')
        inv.paid_amount = _round_money((getattr(inv, 'paid_amount', 0) or 0) + payment_total)
        if inv.paid_amount >= _round_money(inv.total) - 0.01:
            inv.status = 'مدفوعة'
        else:
            inv.status = 'مدفوع جزئياً'
        contract_id = inv.contract_id or resolve_contract_id(
            inv.customer_id,
            '',
            inv.notes or '',
            inv.description or '',
        )
        if contract_id and not inv.contract_id:
            inv.contract_id = contract_id
        return {
            'customer_id': inv.customer_id,
            'contract_id': contract_id,
            'invoice_id': inv.id,
            'parts_billing_id': None,
            'revenue_type': SOURCE_REVENUE_TYPES['invoice'],
            'reference_note': f'تحصيل فاتورة {inv.code}',
        }

    if source_type == 'parts_billing':
        pb = PartsBilling.query.get_or_404(int(source_id))
        remaining = parts_remaining(pb)
        if payment_total > remaining + 0.01:
            raise ValueError(f'المبلغ أكبر من المتبقي على بيان القطع ({remaining:.2f})')
        pb.paid_amount = _round_money((getattr(pb, 'paid_amount', 0) or 0) + payment_total)
        if pb.paid_amount >= _round_money(pb.sell_price) - 0.01:
            pb.status = 'محصل'
        else:
            pb.status = 'غير محصل'
        return {
            'customer_id': pb.customer_id,
            'contract_id': pb.contract_id,
            'invoice_id': None,
            'parts_billing_id': pb.id,
            'revenue_type': SOURCE_REVENUE_TYPES['parts_billing'],
            'reference_note': f'تحصيل قطع {pb.code}',
        }

    raise ValueError('نوع العملية غير معروف')


def customer_financial_totals(revenues, parts, invoices) -> dict:
    """مجاميع المدفوعات دون احتساب العملية مرتين (إيراد + قطع غيار)."""
    revenue_linked_parts = {
        int(r.parts_billing_id) for r in revenues if r.parts_billing_id
    }
    rev_keys = {(r.revenue_date, _round_money(r.total)) for r in revenues}

    invoice_extra = []
    for inv in invoices:
        if inv.parts_billing_id and int(inv.parts_billing_id) in revenue_linked_parts:
            continue
        if (inv.invoice_date, _round_money(inv.total)) in rev_keys:
            continue
        invoice_extra.append(inv)

    contract_rev_types = (
        'عقد صيانة', 'عقد ضمان', 'عقد تركيب', 'تجديد عقد', 'عقد جديد', 'صيانة',
    )
    contract_payments = sum(
        r.total or 0 for r in revenues
        if (r.revenue_type or 'عقد صيانة') in contract_rev_types
    )
    contract_payments += sum(i.total or 0 for i in invoice_extra if i.contract_id)

    parts_from_rev = sum(
        r.total or 0 for r in revenues if (r.revenue_type or '') == 'قطع غيار'
    )
    parts_legacy = sum(
        p.sell_price or 0 for p in parts
        if p.id not in revenue_linked_parts
    )
    parts_payments = parts_from_rev + parts_legacy

    other_payments = sum(
        r.total or 0 for r in revenues if (r.revenue_type or '') == 'أعمال إضافية'
    )

    total_paid = sum(r.total or 0 for r in revenues) + sum(i.total or 0 for i in invoice_extra)

    return {
        'contract_payments': _round_money(contract_payments),
        'parts_payments': _round_money(parts_payments),
        'other_payments': _round_money(other_payments),
        'total_paid': _round_money(total_paid),
        'invoice_extra': invoice_extra,
    }


def build_customer_statement(customer_id: int) -> dict:
    """كشف حساب: مستحقات + دفعات + رصيد."""
    customer = Customer.query.get_or_404(customer_id)
    debits: list[dict] = []
    for op in customer_uncollected_ops(customer_id):
        debits.append({
            'date': op['date'],
            'code': op['code'],
            'type': op['title'],
            'description': op['description'],
            'debit': op['remaining'],
            'credit': 0,
            'status': op['status'],
            'source_type': op['source_type'],
            'source_id': op['source_id'],
        })

    credits: list[dict] = []
    revenues = (
        Revenue.query.filter_by(customer_id=customer_id)
        .filter(Revenue.status.in_(COLLECTED_REVENUE_STATUSES))
        .order_by(Revenue.revenue_date.desc())
        .all()
    )
    for r in revenues:
        ref = ''
        if r.invoice_id:
            inv = Invoice.query.get(r.invoice_id)
            ref = f'فاتورة {inv.code}' if inv else ''
        elif r.parts_billing_id:
            pb = PartsBilling.query.get(r.parts_billing_id)
            ref = f'قطع {pb.code}' if pb else ''
        elif r.contract_id:
            c = Contract.query.get(r.contract_id)
            ref = f'عقد {c.code}' if c else ''
        credits.append({
            'date': str(r.revenue_date or ''),
            'code': r.code,
            'type': r.revenue_type or 'إيراد',
            'description': ref or (r.notes or ''),
            'debit': 0,
            'credit': _round_money(r.total),
            'status': r.status or '',
            'source_type': 'revenue',
            'source_id': r.id,
        })

    total_debit = _round_money(sum(d['debit'] for d in debits))
    total_credit = _round_money(sum(c['credit'] for c in credits))
    balance = _round_money(total_debit)

    return {
        'customer_id': customer_id,
        'customer_name': customer.name,
        'total_outstanding': total_debit,
        'total_paid': total_credit,
        'balance_due': balance,
        'debits': debits,
        'credits': credits,
        'uncollected_ops': customer_uncollected_ops(customer_id),
    }
