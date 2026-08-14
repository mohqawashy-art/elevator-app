"""تحصيل الإيرادات — عمليات غير محصّلة وكشف حساب العميل."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import or_

from models import Contract, Customer, Invoice, PartsBilling, Revenue, db
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query

COLLECTED_REVENUE_STATUSES = ('محصّل', 'محصل', 'مدفوع', 'مدفوعة')
UNPAID_INVOICE_STATUSES = ['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً']
PAID_INVOICE_STATUSES = ['مدفوعة', 'مدفوع', 'محصّل', 'محصل']
UNPAID_PARTS_STATUSES = ('غير محصل', 'معلقة', 'بانتظار موافقة العميل', 'بانتظار التوريد')
CONTRACT_REVENUE_KEYWORDS = ('عقد', 'صيانة', 'ضمان', 'تجديد')
_CONTRACT_CODE_RE = re.compile(r'(CN|CI)-?\s*(\d+)', re.I)


def _normalize_contract_code(code: str | None) -> str | None:
    raw = (code or '').strip().upper()
    if not raw:
        return None
    m = _CONTRACT_CODE_RE.search(raw)
    if m:
        return f'{m.group(1).upper()}-{int(m.group(2)):05d}'
    m2 = re.fullmatch(r'(\d+)', raw)
    if m2:
        return f'CN-{int(m2.group(1)):05d}'
    return raw


def _extract_contract_code(*texts) -> str | None:
    for text in texts:
        if not text:
            continue
        match = _CONTRACT_CODE_RE.search(str(text))
        if match:
            return f'{match.group(1).upper()}-{int(match.group(2)):05d}'
    return None


def _round_money(v: float) -> float:
    return round(float(v or 0), 2)


def _money_decimal(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def split_vat_amounts(
    *,
    amount_ex_vat=None,
    total_incl_vat=None,
    tax_pct: float = 15,
) -> tuple[float, float, float]:
    """تقسيم المبلغ / الضريبة / الإجمالي دون انحراف 1599.99 عند الإدخال الشامل."""
    pct = 15.0 if tax_pct is None else float(tax_pct)
    rate = Decimal(str(pct / 100))
    has_total = total_incl_vat not in (None, '')

    if has_total:
        total_d = _money_decimal(total_incl_vat)
        if amount_ex_vat not in (None, ''):
            amount_d = _money_decimal(amount_ex_vat)
        else:
            amount_d = (total_d / (Decimal('1') + rate)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        tax_d = total_d - amount_d
        total_d = amount_d + tax_d
        return float(amount_d), float(tax_d), float(total_d)

    amount_d = _money_decimal(amount_ex_vat)
    tax_d = (amount_d * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_d = amount_d + tax_d
    return float(amount_d), float(tax_d), float(total_d)


def _before_tax_from_inclusive(total_incl, tax_pct: float = 15) -> float:
    """قبل الضريبة من إجمالي شامل دون إعادة بناء تُنتج 1299.99 / 3000.01."""
    amount, _tax, _total = split_vat_amounts(total_incl_vat=total_incl, tax_pct=tax_pct)
    return amount


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
        contract = tenant_query(Contract).filter_by(code=code, customer_id=customer_id).first()
        if contract:
            return contract.id

    if revenue_id:
        rev = tenant_query(Revenue).filter_by(id=revenue_id).first()
        if rev:
            if rev.contract_id:
                return rev.contract_id
            if rev.invoice_id:
                inv = tenant_query(Invoice).filter_by(id=rev.invoice_id).first()
                if inv and inv.contract_id:
                    return inv.contract_id
                if inv:
                    inv_code = _extract_contract_code(inv.description, inv.notes)
                    if inv_code:
                        contract = tenant_query(Contract).filter_by(
                            code=inv_code, customer_id=customer_id
                        ).first()
                        if contract:
                            return contract.id

    if _is_contract_revenue_type(revenue_type):
        active = [
            c for c in tenant_query(Contract).filter_by(customer_id=customer_id)
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

    for rev in tenant_query(Revenue).filter(
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

    for inv in tenant_query(Invoice).filter(
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
            rev = tenant_query(Revenue).filter_by(invoice_id=inv.id).first()
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

    contract = tenant_query(Contract).filter_by(id=contract_id).first()
    if not contract:
        return 0.0

    rev_rows = tenant_query(Revenue).filter(
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
    for inv in tenant_query(Invoice).filter_by(contract_id=contract_id).all():
        # سند القبض = نفس مبلغ الإيراد — لا يُحسب مرتين
        if is_receipt_voucher(inv.invoice_type) or getattr(inv, 'revenue_id', None):
            continue
        inv_paid = _invoice_paid_total(inv)
        linked = linked_by_invoice.get(inv.id, 0.0)
        inv_extra += max(0.0, inv_paid - linked)

    code = (contract.code or '').upper()
    customer_id = contract.customer_id

    orphan_revs = tenant_query(Revenue).filter(
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

    orphan_invs = tenant_query(Invoice).filter(
        Invoice.customer_id == customer_id,
        Invoice.contract_id.is_(None),
    ).all()
    for inv in orphan_invs:
        if is_receipt_voucher(inv.invoice_type) or getattr(inv, 'revenue_id', None):
            continue
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


def _tax_invoice_q():
    return tenant_query(Invoice).filter(
        or_(
            Invoice.invoice_type.is_(None),
            Invoice.invoice_type == '',
            ~Invoice.invoice_type.contains('سند'),
        )
    )


def _invoice_exists_for_parts(parts_id: int) -> bool:
    return _tax_invoice_q().filter_by(parts_billing_id=parts_id).first() is not None


def _invoice_exists_for_contract(contract_id: int) -> bool:
    return _tax_invoice_q().filter_by(contract_id=contract_id).first() is not None


def customer_billable_ops(customer_id: int) -> list[dict]:
    """عمليات جاهزة لإصدار فاتورة عليها (لم تُفوتر بعد)."""
    rows: list[dict] = []
    today = date.today()

    for pb in (
        tenant_query(PartsBilling).filter_by(customer_id=customer_id)
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
            'amount_before_tax': _before_tax_from_inclusive(total),
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

    for c in tenant_query(Contract).filter_by(customer_id=customer_id).order_by(Contract.start_date.desc()).all():
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

        rows.append({
            'source_type': 'contract',
            'source_id': c.id,
            'code': c.code,
            'date': str(c.start_date or ''),
            'title': c.contract_type or 'عقد',
            'description': f'فاتورة عقد {c.code} — {c.contract_type or "صيانة"} (المبلغ الكامل)',
            'amount_before_tax': _before_tax_from_inclusive(total),
            'total': total,
            'paid': paid,
            'remaining': max(remaining, 0),
            'contract_id': c.id,
            'contract_code': c.code,
            'fault_code': '',
            'visit_code': '',
            'status': c.invoice_status or 'غير مدفوع',
            'collected': collected,
            'hint': (
                'تم التحصيل — إصدار فاتورة للتوثيق'
                if collected
                else f'فاتورة بالمبلغ الكامل ({total:,.2f}) — الدفعات بسندات قبض'
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
        tenant_query(Revenue).filter_by(customer_id=customer_id)
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


def tenant_outstanding_collectible(*, today: date | None = None) -> dict:
    """المبالغ المستحقة التحصيل على مستوى المستأجر.

    يعتمد أساساً على المتبقي من العقود (قيمة العقد − المدفوع)،
    ويضيف فواتير بلا عقد + قطع غيار غير محصّلة — دون تكرار سندات القبض.
    """
    today = today or date.today()
    contracts_total = 0.0
    contracts_count = 0
    invoices_total = 0.0
    invoices_count = 0
    parts_total = 0.0
    parts_count = 0
    detail_rows: list[dict] = []

    for c in tenant_query(Contract).order_by(Contract.end_date.asc()).all():
        if not _contract_is_collectible(c, today):
            continue
        rem = max(
            _round_money(c.total) - _round_money(getattr(c, 'paid_amount', 0) or 0),
            0,
        )
        if rem <= 0.01:
            continue
        contracts_total += rem
        contracts_count += 1
        detail_rows.append({
            'kind': 'عقد',
            'code': c.code,
            'customer': c.customer.name if c.customer else '—',
            'customer_id': c.customer_id,
            'total': _round_money(c.total),
            'paid': _round_money(getattr(c, 'paid_amount', 0) or 0),
            'remaining': rem,
            'due_date': str(getattr(c, 'due_date', None) or ''),
            'status': c.invoice_status or 'غير مدفوع',
            'link': f'/contracts?highlight={c.id}',
        })

    for inv in tenant_query(Invoice).filter(Invoice.contract_id.is_(None)).all():
        if is_receipt_voucher(inv.invoice_type) or getattr(inv, 'revenue_id', None):
            continue
        rem = invoice_remaining(inv)
        if rem <= 0.01:
            continue
        invoices_total += rem
        invoices_count += 1
        detail_rows.append({
            'kind': 'فاتورة',
            'code': inv.code,
            'customer': inv.customer.name if inv.customer else '—',
            'customer_id': inv.customer_id,
            'total': _round_money(inv.total),
            'paid': _round_money(getattr(inv, 'paid_amount', 0) or 0),
            'remaining': rem,
            'due_date': str(inv.due_date or ''),
            'status': inv.status or 'غير مدفوعة',
            'link': f'/invoices/{inv.id}/print',
        })

    for pb in tenant_query(PartsBilling).all():
        rem = parts_remaining(pb)
        if rem <= 0.01:
            continue
        parts_total += rem
        parts_count += 1
        detail_rows.append({
            'kind': 'قطع غيار',
            'code': pb.code,
            'customer': pb.customer.name if pb.customer else '—',
            'customer_id': pb.customer_id,
            'total': _round_money(pb.sell_price),
            'paid': _round_money(getattr(pb, 'paid_amount', 0) or 0),
            'remaining': rem,
            'due_date': '',
            'status': pb.status or 'غير محصل',
            'link': f'/parts-billing?highlight={pb.id}',
        })

    detail_rows.sort(key=lambda r: r['remaining'], reverse=True)
    total = _round_money(contracts_total + invoices_total + parts_total)
    return {
        'total': total,
        'contracts_total': _round_money(contracts_total),
        'contracts_count': contracts_count,
        'invoices_total': _round_money(invoices_total),
        'invoices_count': invoices_count,
        'parts_total': _round_money(parts_total),
        'parts_count': parts_count,
        'items_count': contracts_count + invoices_count + parts_count,
        'rows': detail_rows,
    }


def tenant_uncollected_ops(*, customer_id: int | None = None) -> list[dict]:
    """المستحقات غير المحصّلة للمستأجر — اختيارياً لعميل واحد."""
    from sqlalchemy.orm import joinedload

    rows: list[dict] = []
    today = date.today()

    cq = tenant_query(Contract).options(joinedload(Contract.customer))
    if customer_id:
        cq = cq.filter_by(customer_id=customer_id)
    for c in cq.order_by(Contract.start_date.desc()).all():
        remaining = contract_remaining(c)
        if remaining <= 0.01 or not _contract_is_collectible(c, today):
            continue
        paid = contract_paid_amount(c.id)
        cust = c.customer
        rows.append({
            'source_type': 'contract',
            'source_id': c.id,
            'code': c.code,
            'date': str(c.start_date or ''),
            'due_date': str(getattr(c, 'due_date', None) or ''),
            'title': c.contract_type or 'عقد',
            'description': f'عقد {c.code} — المتبقي على قيمة العقد',
            'total': _round_money(c.total),
            'paid': paid,
            'remaining': remaining,
            'amount_before_tax': _before_tax_from_inclusive(remaining),
            'contract_id': c.id,
            'customer_id': c.customer_id,
            'customer': cust.name if cust else '—',
            'customer_code': cust.code if cust else '',
            'status': c.invoice_status or 'غير مدفوع',
            'collected': False,
            'hint': f'غير محصّل — المتبقي {_round_money(remaining)}',
        })

    iq = tenant_query(Invoice).options(joinedload(Invoice.customer))
    if customer_id:
        iq = iq.filter_by(customer_id=customer_id)
    for inv in iq.order_by(Invoice.invoice_date.desc()).all():
        remaining = invoice_remaining(inv)
        if remaining <= 0.01:
            continue
        if inv.status in PAID_INVOICE_STATUSES and remaining <= 0.01:
            continue
        cust = inv.customer
        rows.append({
            'source_type': 'invoice',
            'source_id': inv.id,
            'code': inv.code,
            'date': str(inv.invoice_date or ''),
            'due_date': str(inv.due_date or ''),
            'title': inv.invoice_type or 'فاتورة',
            'description': inv.description or inv.invoice_type or 'فاتورة',
            'total': _round_money(inv.total),
            'paid': _round_money(getattr(inv, 'paid_amount', 0) or 0),
            'remaining': remaining,
            'amount_before_tax': _before_tax_from_inclusive(remaining),
            'contract_id': inv.contract_id,
            'customer_id': inv.customer_id,
            'customer': cust.name if cust else '—',
            'customer_code': cust.code if cust else '',
            'status': inv.status or 'غير مدفوعة',
            'collected': False,
            'hint': f'غير محصّل — المتبقي {_round_money(remaining)}',
        })

    pq = tenant_query(PartsBilling).options(
        joinedload(PartsBilling.customer),
        joinedload(PartsBilling.fault),
        joinedload(PartsBilling.visit),
    )
    if customer_id:
        pq = pq.filter_by(customer_id=customer_id)
    for pb in pq.order_by(PartsBilling.billing_date.desc()).all():
        if (pb.status or '') not in UNPAID_PARTS_STATUSES and parts_remaining(pb) <= 0.01:
            continue
        remaining = parts_remaining(pb)
        if remaining <= 0.01:
            continue
        cust = pb.customer
        rows.append({
            'source_type': 'parts_billing',
            'source_id': pb.id,
            'code': pb.code,
            'date': str(pb.billing_date or ''),
            'due_date': '',
            'title': 'تركيب قطع غيار',
            'description': (pb.description or 'قطع غيار')[:120],
            'total': _round_money(pb.sell_price),
            'paid': _round_money(getattr(pb, 'paid_amount', 0) or 0),
            'remaining': remaining,
            'amount_before_tax': _before_tax_from_inclusive(remaining),
            'contract_id': pb.contract_id,
            'customer_id': pb.customer_id,
            'customer': cust.name if cust else '—',
            'customer_code': cust.code if cust else '',
            'status': pb.status or 'غير محصل',
            'fault_code': pb.fault.code if pb.fault else '',
            'visit_code': pb.visit.code if pb.visit else '',
            'collected': False,
            'hint': f'غير محصّل — المتبقي {_round_money(remaining)}',
        })

    rows.sort(key=lambda x: (x['remaining'], x['date'], x['code'] or ''), reverse=True)
    return rows


def customer_uncollected_ops(customer_id: int) -> list[dict]:
    """عمليات العميل غير المحصّلة بالكامل."""
    return tenant_uncollected_ops(customer_id=customer_id)


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
        c = tenant_get_or_404(Contract, int(source_id))
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
        inv = tenant_get_or_404(Invoice, int(source_id))
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
        pb = tenant_get_or_404(PartsBilling, int(source_id))
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


def is_receipt_voucher(invoice_type: str | None) -> bool:
    return 'سند' in (invoice_type or '')


def validate_tax_invoice_full_amount(
    invoice_type: str | None,
    total_incl_vat: float,
    source_type: str | None,
    source_id: int | None,
) -> str | None:
    """يرفض فاتورة ضريبية بمبلغ جزئي — مطابق للمعايير السعودية."""
    from zatca_qr import is_tax_invoice

    if not is_tax_invoice(invoice_type):
        return None
    st = (source_type or '').strip()
    if st == 'revenue':
        return (
            'محاسبياً: لا تُصدر فاتورة ضريبية من الإيراد — '
            'أصدر الفاتورة بالمبلغ الكامل من العقد أو العملية، ثم سجّل التحصيل كإيراد.'
        )
    expected = expected_source_total(st, source_id)
    if expected is None:
        return None
    total = _round_money(total_incl_vat)
    if abs(total - expected) > 0.02:
        return (
            f'الفاتورة الضريبية يجب أن تكون بالمبلغ الكامل ({expected:,.2f} ر.س شامل الضريبة) — '
            'الدفعات الجزئية تُسجّل بسندات قبض.'
        )
    return None


def expected_source_total(source_type: str | None, source_id: int | None) -> float | None:
    st = (source_type or '').strip()
    if not st or not source_id:
        return None
    sid = int(source_id)
    if st == 'contract':
        c = tenant_query(Contract).filter_by(id=sid).first()
        return _round_money(c.total) if c else None
    if st == 'parts_billing':
        pb = tenant_query(PartsBilling).filter_by(id=sid).first()
        return _round_money(pb.sell_price) if pb else None
    return None


def receipt_for_revenue(revenue_id: int) -> Invoice | None:
    return tenant_query(Invoice).filter_by(revenue_id=revenue_id).first()


def create_receipt_voucher_for_revenue(revenue: Revenue) -> Invoice | None:
    """إنشاء سند قبض تلقائي عند تسجيل إيراد محصّل."""
    if (revenue.status or '') not in COLLECTED_REVENUE_STATUSES:
        return None
    existing = receipt_for_revenue(revenue.id)
    if existing:
        return existing

    from operations import next_code

    payment_total = _round_money(revenue.total)
    if payment_total <= 0.01:
        return None

    parent_inv = tenant_query(Invoice).filter_by(id=revenue.invoice_id).first() if revenue.invoice_id else None
    description = (revenue.revenue_type or 'تحصيل').strip()
    notes_parts = [f'إيراد {revenue.code}']
    if parent_inv:
        notes_parts.append(f'مقابل فاتورة {parent_inv.code}')
        description = f'سند قبض — {parent_inv.description or parent_inv.invoice_type or "فاتورة"}'[:300]
    elif revenue.contract_id:
        c = tenant_query(Contract).filter_by(id=revenue.contract_id).first()
        if c:
            notes_parts.append(f'عقد {c.code}')
            description = f'سند قبض — عقد {c.code}'[:300]
    elif revenue.parts_billing_id:
        pb = tenant_query(PartsBilling).filter_by(id=revenue.parts_billing_id).first()
        if pb:
            notes_parts.append(f'قطع {pb.code}')
            description = f'سند قبض — {pb.description or pb.code}'[:300]

    receipt = Invoice(
        code=next_code(Invoice, 'RCP-', digits=4),
        invoice_type='سند قبض',
        customer_id=revenue.customer_id,
        contract_id=revenue.contract_id,
        parts_billing_id=revenue.parts_billing_id,
        parent_invoice_id=parent_inv.id if parent_inv else None,
        revenue_id=revenue.id,
        invoice_date=revenue.revenue_date or date.today(),
        due_date=None,
        description=description,
        amount=payment_total,
        tax_amount=0.0,
        total=payment_total,
        paid_amount=payment_total,
        payment_method=revenue.payment_method or '',
        status='مدفوعة',
        notes=' — '.join(notes_parts),
    )
    assign_organization(receipt)
    db.session.add(receipt)
    return receipt


def customer_financial_totals(revenues, parts, invoices) -> dict:
    """مجاميع المدفوعات دون احتساب العملية مرتين (إيراد + قطع غيار + سند قبض)."""
    revenue_linked_parts = {
        int(r.parts_billing_id) for r in revenues if r.parts_billing_id
    }
    rev_keys = {(r.revenue_date, _round_money(r.total)) for r in revenues}
    revenue_ids = {int(r.id) for r in revenues if r.id}

    invoice_extra = []
    for inv in invoices:
        # سند القبض مرآة للإيراد — لا يُضاف للمجموع
        if is_receipt_voucher(inv.invoice_type):
            continue
        if getattr(inv, 'revenue_id', None) and int(inv.revenue_id) in revenue_ids:
            continue
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
    """كشف حساب: مدين (عقود/فواتير) + دائن (إيرادات/سندات) + رصيد جاري."""
    customer = tenant_get_or_404(Customer, customer_id)

    tax_invoices = (
        tenant_query(Invoice).filter_by(customer_id=customer_id)
        .order_by(Invoice.invoice_date.asc(), Invoice.id.asc())
        .all()
    )

    debits: list[dict] = []
    invoiced_contract_ids: set[int] = set()
    for inv in tax_invoices:
        if is_receipt_voucher(inv.invoice_type) or getattr(inv, 'revenue_id', None):
            continue
        remaining = invoice_remaining(inv)
        if inv.contract_id:
            invoiced_contract_ids.add(int(inv.contract_id))
        debits.append({
            'date': str(inv.invoice_date or ''),
            'code': inv.code,
            'type': inv.invoice_type or 'فاتورة',
            'description': (inv.description or '')[:200],
            'debit': _round_money(inv.total),
            'credit': 0,
            'paid': _round_money(getattr(inv, 'paid_amount', 0) or 0),
            'remaining': remaining,
            'status': inv.status or '',
            'source_type': 'invoice',
            'source_id': inv.id,
        })

    # عقود بلا فاتورة ضريبية — تُحسب كمدين (شائع في جما عند التحصيل على العقد مباشرة)
    for c in (
        tenant_query(Contract).filter_by(customer_id=customer_id)
        .order_by(Contract.start_date.asc(), Contract.id.asc())
        .all()
    ):
        if c.id in invoiced_contract_ids:
            continue
        total = _round_money(c.total)
        if total <= 0.01:
            continue
        paid = contract_paid_amount(c.id)
        remaining = max(total - paid, 0)
        debits.append({
            'date': str(c.start_date or ''),
            'code': c.code,
            'type': 'عقد',
            'description': f'{c.contract_type or "عقد"} — قيمة العقد',
            'debit': total,
            'credit': 0,
            'paid': paid,
            'remaining': remaining,
            'status': c.invoice_status or 'غير مدفوع',
            'source_type': 'contract',
            'source_id': c.id,
        })

    revenues = (
        tenant_query(Revenue).filter_by(customer_id=customer_id)
        .filter(Revenue.status.in_(COLLECTED_REVENUE_STATUSES))
        .order_by(Revenue.revenue_date.asc(), Revenue.id.asc())
        .all()
    )

    credits: list[dict] = []
    for r in revenues:
        receipt = receipt_for_revenue(r.id)
        parent_ref = ''
        if r.invoice_id:
            inv = tenant_query(Invoice).filter_by(id=r.invoice_id).first()
            if inv and not is_receipt_voucher(inv.invoice_type):
                parent_ref = f'فاتورة {inv.code}'
        elif r.contract_id:
            c = tenant_query(Contract).filter_by(id=r.contract_id).first()
            parent_ref = f'عقد {c.code}' if c else ''
        elif r.parts_billing_id:
            pb = tenant_query(PartsBilling).filter_by(id=r.parts_billing_id).first()
            parent_ref = f'قطع {pb.code}' if pb else ''

        credits.append({
            'date': str(r.revenue_date or ''),
            'code': r.code,
            'receipt_code': receipt.code if receipt else '',
            'type': r.revenue_type or 'إيراد',
            'description': parent_ref or (r.notes or '')[:200],
            'debit': 0,
            'credit': _round_money(r.total),
            'status': r.status or '',
            'source_type': 'revenue',
            'source_id': r.id,
            'receipt_id': receipt.id if receipt else None,
            'invoice_id': r.invoice_id,
        })

    # دفتر حركة موحّد مع رصيد جاري
    raw_lines: list[dict] = []
    for d in debits:
        raw_lines.append({
            'date': d['date'],
            'code': d['code'],
            'type': d['type'],
            'description': d['description'],
            'debit': d['debit'],
            'credit': 0.0,
            'source_type': d['source_type'],
            'source_id': d['source_id'],
        })
    for c in credits:
        desc = c['description']
        if c.get('receipt_code'):
            desc = f"{desc} — سند {c['receipt_code']}".strip(' —')
        raw_lines.append({
            'date': c['date'],
            'code': c['code'],
            'type': c['type'],
            'description': desc,
            'debit': 0.0,
            'credit': c['credit'],
            'source_type': c['source_type'],
            'source_id': c['source_id'],
        })

    raw_lines.sort(key=lambda x: (x['date'] or '', x['source_type'], x['source_id'] or 0))
    balance = 0.0
    lines: list[dict] = []
    for row in raw_lines:
        balance = _round_money(balance + row['debit'] - row['credit'])
        lines.append({**row, 'balance': balance})

    total_invoiced = _round_money(sum(d['debit'] for d in debits))
    total_paid = _round_money(sum(c['credit'] for c in credits))
    balance_due = max(_round_money(total_invoiced - total_paid), 0)
    # إن وُجد رصيد دائن (دفع زائد) يظهر سالباً في running balance
    running = lines[-1]['balance'] if lines else 0.0

    uncollected = customer_uncollected_ops(customer_id)
    uncollected_total = _round_money(sum(_round_money(o.get('remaining') or 0) for o in uncollected))

    return {
        'customer_id': customer_id,
        'customer_code': customer.code,
        'customer_name': customer.name,
        'customer_phone': customer.phone or '',
        'customer_city': customer.city or '',
        'customer_address': customer.address or '',
        'total_invoiced': total_invoiced,
        'total_debit': total_invoiced,
        'total_outstanding': balance_due,
        'total_paid': total_paid,
        'total_credit': total_paid,
        'balance_due': balance_due,
        'running_balance': running,
        'uncollected_total': uncollected_total,
        'debits': debits,
        'credits': credits,
        'lines': lines,
        'uncollected_ops': uncollected,
        'generated_at': date.today().isoformat(),
    }
