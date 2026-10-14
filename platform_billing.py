"""اشتراكات عملاء LiftCore — إدارة يدوية من لوحة المنصة (حسابات مؤسسة نسق كور)."""
from __future__ import annotations

import re
from calendar import monthrange
from datetime import datetime, timedelta

from sqlalchemy import inspect, text

from models import Organization, PlatformExpense, PlatformInvoice, PlatformPayment, db
from plan_catalog import normalize_plan, plan_definition


BILLING_STATUSES = ('ok', 'due', 'overdue', 'complimentary')
BILLING_CYCLES = ('monthly', 'yearly')
PAYMENT_METHODS = ('transfer', 'cash', 'card', 'complimentary', 'other')
INVOICE_STATUSES = ('unpaid', 'paid', 'void')
VAT_PCT = 15.0
JAMA_SLUG = 'jama'
JAMA_FREE_MONTHS = 12
FREE_NOTE_TAG = '[NASQ-FREE]'
JAMA_FREE_NOTE = 'مجاني لمدة عام — مؤسسة نسق كور للحلول المتكاملة'
DEMO_FREE_NOTE = 'حساب تجريبي مجاني — مؤسسة نسق كور للحلول المتكاملة'

NASQ_CORE = {
    'legal_name': 'مؤسسة نسق كور للحلول المتكاملة',
    'brand': 'Nasaq Core',
    'product': 'LiftCore',
    'city': 'مكة المكرمة',
    'district': 'حي العوالي',
    'street': 'طريق الطائف',
    'address': 'مكة المكرمة، حي العوالي، طريق الطائف',
    'country': 'المملكة العربية السعودية',
    'phone': '0566299626',
    'email': 'info@liftcoreapp.com',
    'cr_number': '4031239017',
    'currency': 'ر.س',
    'logo': 'images/nasaq-core-logo.png',
}

EXPENSE_CATEGORIES = (
    ('hosting', 'استضافة وخوادم'),
    ('domain', 'نطاقات وشهادات'),
    ('ads', 'إعلانات وتسويق'),
    ('salaries', 'رواتب وأتعاب'),
    ('software', 'برمجيات واشتراكات'),
    ('other', 'أخرى'),
)

INVOICE_STATUS_AR = {
    'unpaid': 'غير مدفوعة',
    'paid': 'مدفوعة',
    'void': 'ملغاة',
}


def _plan_price_maps() -> tuple[dict[str, float], dict[str, float]]:
    from plan_catalog import PLAN_ORDER
    monthly: dict[str, float] = {}
    yearly: dict[str, float] = {}
    for key in PLAN_ORDER:
        spec = plan_definition(key)
        monthly[key] = float(spec.get('monthly_sar') or 0)
        yearly[key] = float(spec.get('yearly_sar') or 0)
    return monthly, yearly


# توافق خلفي — تُحدَّث عند الاستيراد؛ plan_price() يقرأ القيم الحية
PLAN_MONTHLY_SAR, PLAN_YEARLY_SAR = _plan_price_maps()


def plan_price(plan: str | None, cycle: str = 'monthly') -> float:
    key = normalize_plan(plan)
    spec = plan_definition(key)
    if (cycle or 'monthly').strip().lower() == 'yearly':
        return float(spec.get('yearly_sar') or 0)
    return float(spec.get('monthly_sar') or 0)


def _org_slug(org: Organization) -> str:
    return (org.slug or '').strip().lower()


def is_demo_tenant(org: Organization) -> bool:
    slug = _org_slug(org)
    if slug == 'demo' or slug.startswith('demo-'):
        return True
    try:
        from demo_provisioning import is_demo_org
        return bool(is_demo_org(org))
    except Exception:
        return '[DEMO]' in (org.notes or '')


def is_jama_tenant(org: Organization) -> bool:
    return _org_slug(org) == JAMA_SLUG


def is_policy_free_org(org: Organization, *, now: datetime | None = None) -> bool:
    """جما (خلال عام المجانية) والديمو — لا إيرادات للمنصة."""
    if is_demo_tenant(org):
        return True
    if not is_jama_tenant(org):
        return False
    now = now or datetime.utcnow()
    end = org.current_period_end
    notes = org.billing_notes or ''
    if FREE_NOTE_TAG in notes and end:
        return end > now
    if FREE_NOTE_TAG not in notes:
        return True
    return bool(end and end > now)


def is_complimentary_org(org: Organization) -> bool:
    if is_policy_free_org(org):
        return True
    return (org.billing_status or '') == 'complimentary'


def effective_amount(org: Organization) -> float:
    if is_complimentary_org(org):
        return 0.0
    if org.billing_amount is not None:
        return float(org.billing_amount)
    return plan_price(org.plan, org.billing_cycle or 'monthly')


def split_vat_inclusive(total: float, tax_pct: float = VAT_PCT) -> tuple[float, float, float]:
    total = round(float(total or 0), 2)
    pct = float(tax_pct or 0)
    if pct <= 0 or total <= 0:
        return total, 0.0, total
    tax = round(total * pct / (100.0 + pct), 2)
    subtotal = round(total - tax, 2)
    return subtotal, tax, total


def _add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def period_end_from(start: datetime, cycle: str = 'monthly') -> datetime:
    if (cycle or 'monthly').strip().lower() == 'yearly':
        return _add_months(start, 12)
    return _add_months(start, 1)


def next_platform_code(model, prefix: str, field: str = 'code', digits: int = 4) -> str:
    pattern = re.compile(r'^' + re.escape(prefix) + r'(\d+)$')
    max_num = 0
    col = getattr(model, field)
    for (code,) in model.query.with_entities(col).all():
        if not code:
            continue
        m = pattern.match(str(code).strip())
        if m:
            max_num = max(max_num, int(m.group(1)))
    n = max_num + 1
    while True:
        candidate = f'{prefix}{str(n).zfill(digits)}'
        if not model.query.filter(col == candidate).first():
            return candidate
        n += 1


def ensure_platform_books_schema() -> None:
    """جداول/أعمدة حسابات نسق كور إن غابت (بدون انتظار Alembic وحده)."""
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    if 'platform_invoices' not in tables:
        PlatformInvoice.__table__.create(bind=db.engine, checkfirst=True)
        tables.add('platform_invoices')
    if 'platform_expenses' not in tables:
        PlatformExpense.__table__.create(bind=db.engine, checkfirst=True)
        tables.add('platform_expenses')
    if 'platform_payments' not in tables:
        return
    pay_cols = {c['name'] for c in insp.get_columns('platform_payments')}
    for col_name, column_type in (
        ('invoice_id', 'INTEGER'),
        ('receipt_code', 'VARCHAR(30)'),
        ('receipt_issued_at', 'TIMESTAMP'),
    ):
        if col_name in pay_cols:
            continue
        db.session.execute(text(
            f'ALTER TABLE platform_payments ADD COLUMN {col_name} {column_type}'
        ))
        db.session.commit()
        pay_cols.add(col_name)


def _zero_platform_payments(org: Organization) -> int:
    n = 0
    payments = PlatformPayment.query.filter_by(organization_id=org.id).all()
    for pay in payments:
        if float(pay.amount or 0) == 0 and (pay.method or '') == 'complimentary':
            continue
        pay.amount = 0.0
        pay.method = 'complimentary'
        extra = 'صُفّر — حساب مجاني لنسق كور'
        note = (pay.note or '').strip()
        if extra not in note:
            pay.note = f'{note} | {extra}'.strip(' |') if note else extra
        n += 1
    if (org.last_payment_amount or 0) != 0:
        org.last_payment_amount = 0.0
    return n


def apply_free_tenant_policy(org: Organization, *, now: datetime | None = None) -> bool:
    """جما مجاناً لعام، والديمو مجاناً — مبلغ صفر ولا تدخل الإيرادات."""
    now = now or datetime.utcnow()
    notes = org.billing_notes or ''
    changed = False

    if is_demo_tenant(org):
        if org.billing_status != 'complimentary':
            org.billing_status = 'complimentary'
            changed = True
        if float(org.billing_amount or 0) != 0 or org.billing_amount is None:
            org.billing_amount = 0.0
            changed = True
        if FREE_NOTE_TAG not in notes:
            org.billing_notes = f'{FREE_NOTE_TAG} {DEMO_FREE_NOTE}'
            changed = True
        if _zero_platform_payments(org):
            changed = True
        return changed

    if not is_jama_tenant(org):
        return False

    already = FREE_NOTE_TAG in notes
    if not already:
        org.billing_status = 'complimentary'
        org.billing_amount = 0.0
        org.current_period_start = now
        org.current_period_end = _add_months(now, JAMA_FREE_MONTHS)
        org.billing_notes = f'{FREE_NOTE_TAG} {JAMA_FREE_NOTE}'
        _zero_platform_payments(org)
        return True

    end = org.current_period_end
    if end and end > now:
        if org.billing_status != 'complimentary':
            org.billing_status = 'complimentary'
            changed = True
        if float(org.billing_amount or 0) != 0:
            org.billing_amount = 0.0
            changed = True
        if _zero_platform_payments(org):
            changed = True
        return changed

    # انتهى عام المجانية — يعود للاشتراك العادي
    if org.billing_status == 'complimentary':
        org.billing_status = 'due'
        changed = True
    if org.billing_amount == 0:
        org.billing_amount = None
        changed = True
    return changed


def apply_all_free_tenant_policies(*, commit: bool = True) -> int:
    n = 0
    orgs = Organization.query.all()
    for org in orgs:
        if apply_free_tenant_policy(org):
            n += 1
    if commit and n:
        db.session.commit()
    return n


def refresh_billing_status(org: Organization, *, commit: bool = False) -> str:
    """حدّث billing_status حسب تاريخ انتهاء الفترة / التجربة."""
    apply_free_tenant_policy(org)
    if is_complimentary_org(org):
        org.billing_status = 'complimentary'
        if commit:
            db.session.commit()
        return 'complimentary'
    if (org.status or '') == 'suspended':
        if commit:
            db.session.commit()
        return org.billing_status or 'overdue'

    now = datetime.utcnow()
    end = org.current_period_end or org.trial_ends_at
    if not end:
        status = 'ok' if (org.status or '') == 'active' else 'due'
    elif end < now - timedelta(days=7):
        status = 'overdue'
    elif end < now:
        status = 'due'
    elif end <= now + timedelta(days=7):
        status = 'due'
    else:
        status = 'ok'
    org.billing_status = status
    if commit:
        db.session.commit()
    return status


def ensure_subscription_defaults(org: Organization, *, days_trial: int = 14) -> None:
    """عند التفعيل الأول: فترة اشتراك أو تجربة."""
    now = datetime.utcnow()
    if not org.billing_cycle:
        org.billing_cycle = 'monthly'
    if not org.billing_status:
        org.billing_status = 'ok'
    if org.status == 'trial' and not org.trial_ends_at:
        org.trial_ends_at = now + timedelta(days=days_trial)
    if org.status == 'active' and not org.current_period_end:
        org.current_period_start = now
        org.current_period_end = period_end_from(now, org.billing_cycle or 'monthly')
    apply_free_tenant_policy(org)
    refresh_billing_status(org)


def set_subscription(
    org: Organization,
    *,
    plan: str | None = None,
    cycle: str | None = None,
    amount: float | None = None,
    period_end: datetime | None = None,
    billing_status: str | None = None,
    billing_notes: str | None = None,
    clear_amount: bool = False,
) -> dict:
    if plan is not None:
        plan = plan.strip().lower()
        from platform_admin import PLANS
        if plan not in PLANS:
            return {'ok': False, 'errors': ['باقة غير معروفة.']}
        org.plan = plan
        # عند مغادرة باقة التخصيص أزل الميزات اليدوية حتى تُستخدم الباقة القياسية
        if plan != 'custom':
            org.features_override_json = None
    if cycle is not None:
        cycle = cycle.strip().lower()
        if cycle not in BILLING_CYCLES:
            return {'ok': False, 'errors': ['دورة فوترة غير معروفة.']}
        org.billing_cycle = cycle
    if clear_amount:
        org.billing_amount = None
    elif amount is not None:
        if amount < 0:
            return {'ok': False, 'errors': ['المبلغ غير صالح.']}
        org.billing_amount = float(amount)
    if period_end is not None:
        org.current_period_end = period_end
        if not org.current_period_start:
            org.current_period_start = datetime.utcnow()
    if billing_status is not None:
        billing_status = billing_status.strip().lower()
        if billing_status not in BILLING_STATUSES:
            return {'ok': False, 'errors': ['حالة فوترة غير معروفة.']}
        org.billing_status = billing_status
    if billing_notes is not None:
        org.billing_notes = billing_notes.strip() or None
    apply_free_tenant_policy(org)
    if org.billing_status != 'complimentary':
        refresh_billing_status(org)
    db.session.commit()
    return {'ok': True, 'org': org}


def extend_trial(org: Organization, *, days: int = 14) -> dict:
    days = max(1, min(int(days or 14), 90))
    now = datetime.utcnow()
    base = org.trial_ends_at if org.trial_ends_at and org.trial_ends_at > now else now
    org.trial_ends_at = base + timedelta(days=days)
    org.status = 'trial'
    org.suspended_at = None
    if not is_policy_free_org(org):
        org.billing_status = 'ok'
    apply_free_tenant_policy(org)
    db.session.commit()
    return {'ok': True, 'org': org, 'trial_ends_at': org.trial_ends_at}


def record_payment(
    org: Organization,
    *,
    amount: float,
    method: str = 'transfer',
    reference: str = '',
    note: str = '',
    months: int | None = None,
    recorded_by_user_id: int | None = None,
    paid_at: datetime | None = None,
    invoice_id: int | None = None,
) -> dict:
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {'ok': False, 'errors': ['المبلغ مطلوب.']}
    if amount < 0:
        return {'ok': False, 'errors': ['المبلغ غير صالح.']}

    method = (method or 'transfer').strip().lower()
    if method not in PAYMENT_METHODS:
        method = 'other'

    if is_policy_free_org(org):
        amount = 0.0
        method = 'complimentary'

    ref = (reference or '').strip()[:100] or None
    if ref:
        existing = PlatformPayment.query.filter_by(reference=ref).first()
        if existing:
            return {'ok': True, 'payment': existing, 'org': org, 'duplicate': True}

    invoice = None
    if invoice_id:
        invoice = db.session.get(PlatformInvoice, int(invoice_id))
        if not invoice or invoice.organization_id != org.id:
            return {'ok': False, 'errors': ['الفاتورة غير تابعة لهذه المؤسسة.']}
        if invoice.status == 'void':
            return {'ok': False, 'errors': ['لا يمكن سداد فاتورة ملغاة.']}

    cycle = org.billing_cycle or 'monthly'
    if months is None:
        months = 12 if cycle == 'yearly' else 1
    months = max(1, min(int(months), 36))

    now = paid_at or datetime.utcnow()
    if org.current_period_end and org.current_period_end > now:
        start = org.current_period_end
    else:
        start = now
    end = _add_months(start, months)

    payment = PlatformPayment(
        organization_id=org.id,
        invoice_id=invoice.id if invoice else None,
        amount=amount,
        currency='SAR',
        method=method,
        reference=ref,
        note=(note or '').strip() or None,
        period_start=start,
        period_end=end,
        plan=org.plan,
        recorded_by_user_id=recorded_by_user_id,
        paid_at=now,
    )
    if amount > 0:
        payment.receipt_code = next_platform_code(PlatformPayment, 'NSQ-RCP-', field='receipt_code')
        payment.receipt_issued_at = now
    db.session.add(payment)
    db.session.flush()

    if invoice and amount > 0:
        invoice.status = 'paid'
        invoice.paid_at = now
        payment.invoice_id = invoice.id
    elif amount > 0:
        open_inv = (
            PlatformInvoice.query.filter_by(organization_id=org.id, status='unpaid')
            .order_by(PlatformInvoice.id.asc())
            .first()
        )
        if open_inv:
            payment.invoice_id = open_inv.id
            open_inv.status = 'paid'
            open_inv.paid_at = now

    org.current_period_start = start
    org.current_period_end = end
    org.last_payment_at = now
    org.last_payment_amount = amount
    org.last_payment_ref = payment.reference
    org.status = 'active'
    org.suspended_at = None
    org.trial_ends_at = None
    if method == 'complimentary' or amount == 0:
        org.billing_status = 'complimentary'
    else:
        org.billing_status = 'ok'
    apply_free_tenant_policy(org)
    db.session.commit()
    return {'ok': True, 'payment': payment, 'org': org}


def issue_invoice(
    org: Organization,
    *,
    amount: float | None = None,
    description: str = '',
    notes: str = '',
    created_by_user_id: int | None = None,
    tax_pct: float = VAT_PCT,
) -> dict:
    apply_free_tenant_policy(org)
    if is_complimentary_org(org):
        return {'ok': False, 'errors': ['لا تُصدر فاتورة لحساب مجاني (جما/ديمو أو هدية).']}
    if amount is None:
        amount = effective_amount(org)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {'ok': False, 'errors': ['المبلغ غير صالح.']}
    if amount <= 0:
        return {'ok': False, 'errors': ['مبلغ الفاتورة يجب أن يكون أكبر من صفر.']}

    now = datetime.utcnow()
    cycle = org.billing_cycle or 'yearly'
    start = org.current_period_end if org.current_period_end and org.current_period_end > now else now
    end = period_end_from(start, cycle)
    subtotal, tax, total = split_vat_inclusive(amount, tax_pct)
    desc = (description or '').strip() or (
        f'اشتراك LiftCore — {org.plan or "liftcore"} — {"سنوي" if cycle == "yearly" else "شهري"}'
    )
    inv = PlatformInvoice(
        code=next_platform_code(PlatformInvoice, 'NSQ-INV-'),
        organization_id=org.id,
        description=desc[:300],
        period_start=start,
        period_end=end,
        subtotal=subtotal,
        tax_pct=float(tax_pct),
        tax_amount=tax,
        total=total,
        currency='SAR',
        status='unpaid',
        issue_date=now,
        due_date=now + timedelta(days=14),
        notes=(notes or '').strip() or None,
        created_by_user_id=created_by_user_id,
    )
    db.session.add(inv)
    db.session.commit()
    return {'ok': True, 'invoice': inv}


def void_invoice(invoice: PlatformInvoice) -> dict:
    if invoice.status == 'paid':
        return {'ok': False, 'errors': ['لا يمكن إلغاء فاتورة مدفوعة.']}
    invoice.status = 'void'
    db.session.commit()
    return {'ok': True, 'invoice': invoice}


def add_expense(
    *,
    amount: float,
    description: str,
    category: str = 'other',
    vendor: str = '',
    method: str = 'transfer',
    reference: str = '',
    notes: str = '',
    spent_at: datetime | None = None,
    created_by_user_id: int | None = None,
) -> dict:
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {'ok': False, 'errors': ['المبلغ غير صالح.']}
    if amount <= 0:
        return {'ok': False, 'errors': ['مبلغ المصروف يجب أن يكون أكبر من صفر.']}
    desc = (description or '').strip()
    if not desc:
        return {'ok': False, 'errors': ['وصف المصروف مطلوب.']}
    cats = {c[0] for c in EXPENSE_CATEGORIES}
    category = (category or 'other').strip().lower()
    if category not in cats:
        category = 'other'
    method = (method or 'transfer').strip().lower()
    if method not in PAYMENT_METHODS:
        method = 'other'
    exp = PlatformExpense(
        code=next_platform_code(PlatformExpense, 'NSQ-EXP-'),
        spent_at=spent_at or datetime.utcnow(),
        category=category,
        vendor=(vendor or '').strip()[:200] or None,
        description=desc[:400],
        amount=amount,
        currency='SAR',
        method=method,
        reference=(reference or '').strip()[:100] or None,
        notes=(notes or '').strip() or None,
        created_by_user_id=created_by_user_id,
    )
    db.session.add(exp)
    db.session.commit()
    return {'ok': True, 'expense': exp}


def counts_as_platform_revenue(payment: PlatformPayment, org: Organization | None = None) -> bool:
    if float(payment.amount or 0) <= 0:
        return False
    if (payment.method or '') == 'complimentary':
        return False
    org = org or db.session.get(Organization, payment.organization_id)
    if not org:
        return False
    if is_demo_tenant(org) or is_jama_tenant(org):
        return False
    if is_complimentary_org(org) and (payment.method or '') == 'complimentary':
        return False
    return True


def account_statement(org: Organization) -> dict:
    invoices = (
        PlatformInvoice.query.filter_by(organization_id=org.id)
        .order_by(PlatformInvoice.issue_date.asc(), PlatformInvoice.id.asc())
        .all()
    )
    payments = (
        PlatformPayment.query.filter_by(organization_id=org.id)
        .order_by(PlatformPayment.paid_at.asc(), PlatformPayment.id.asc())
        .all()
    )
    lines = []
    debit = 0.0
    credit = 0.0
    for inv in invoices:
        if inv.status == 'void':
            continue
        amt = float(inv.total or 0)
        debit += amt
        lines.append({
            'at': inv.issue_date,
            'kind': 'invoice',
            'code': inv.code,
            'label': inv.description or 'فاتورة اشتراك',
            'debit': amt,
            'credit': 0.0,
            'id': inv.id,
        })
    for pay in payments:
        amt = float(pay.amount or 0)
        if amt <= 0:
            continue
        credit += amt
        lines.append({
            'at': pay.paid_at or pay.created_at,
            'kind': 'receipt',
            'code': pay.receipt_code or f'P-{pay.id}',
            'label': 'سند قبض',
            'debit': 0.0,
            'credit': amt,
            'id': pay.id,
        })
    lines.sort(key=lambda r: (r['at'] or datetime.utcnow(), r['kind'] == 'receipt', r['id']))
    running = 0.0
    for line in lines:
        running += float(line['debit']) - float(line['credit'])
        line['balance'] = round(running, 2)
    return {
        'org': org,
        'company': NASQ_CORE,
        'lines': lines,
        'debit': round(debit, 2),
        'credit': round(credit, 2),
        'balance': round(debit - credit, 2),
        'invoices': invoices,
        'payments': payments,
    }


def books_snapshot(*, year: int | None = None) -> dict:
    now = datetime.utcnow()
    year = int(year or now.year)
    start = datetime(year, 1, 1)
    end = datetime(year, 12, 31, 23, 59, 59)
    payments = (
        PlatformPayment.query.filter(
            PlatformPayment.paid_at >= start,
            PlatformPayment.paid_at <= end,
        )
        .order_by(PlatformPayment.paid_at.desc())
        .all()
    )
    org_ids = {p.organization_id for p in payments}
    orgs = {o.id: o for o in Organization.query.filter(Organization.id.in_(org_ids)).all()} if org_ids else {}
    revenue_rows = []
    revenue = 0.0
    waived = 0.0
    for pay in payments:
        org = orgs.get(pay.organization_id)
        if counts_as_platform_revenue(pay, org):
            revenue += float(pay.amount or 0)
            revenue_rows.append(pay)
        else:
            waived += float(pay.amount or 0)

    expenses = (
        PlatformExpense.query.filter(
            PlatformExpense.spent_at >= start,
            PlatformExpense.spent_at <= end,
        )
        .order_by(PlatformExpense.spent_at.desc())
        .all()
    )
    expense_total = sum(float(e.amount or 0) for e in expenses)
    by_cat = {key: 0.0 for key, _ in EXPENSE_CATEGORIES}
    for exp in expenses:
        key = exp.category if exp.category in by_cat else 'other'
        by_cat[key] += float(exp.amount or 0)

    invoices = (
        PlatformInvoice.query.filter(
            PlatformInvoice.issue_date >= start,
            PlatformInvoice.issue_date <= end,
        )
        .order_by(PlatformInvoice.id.desc())
        .all()
    )
    invoiced = sum(float(i.total or 0) for i in invoices if i.status != 'void')
    unpaid = sum(float(i.total or 0) for i in invoices if i.status == 'unpaid')
    return {
        'year': year,
        'company': NASQ_CORE,
        'revenue': round(revenue, 2),
        'waived': round(waived, 2),
        'expenses': round(expense_total, 2),
        'net': round(revenue - expense_total, 2),
        'invoiced': round(invoiced, 2),
        'unpaid': round(unpaid, 2),
        'expense_by_category': by_cat,
        'expense_rows': expenses,
        'revenue_rows': revenue_rows,
        'invoices': invoices,
        'payments': payments,
        'expense_categories': EXPENSE_CATEGORIES,
    }


def list_payments(org_id: int, limit: int = 50) -> list[PlatformPayment]:
    return (
        PlatformPayment.query.filter_by(organization_id=org_id)
        .order_by(PlatformPayment.id.desc())
        .limit(limit)
        .all()
    )


def list_invoices(org_id: int, limit: int = 50) -> list[PlatformInvoice]:
    return (
        PlatformInvoice.query.filter_by(organization_id=org_id)
        .order_by(PlatformInvoice.id.desc())
        .limit(limit)
        .all()
    )


def billing_overview(limit: int = 200, *, year: int | None = None) -> dict:
    """ملخص فوترة لكل المؤسسات + بيان أرباح نسق كور."""
    ensure_platform_books_schema()
    apply_all_free_tenant_policies(commit=True)
    orgs = Organization.query.order_by(Organization.id.desc()).limit(limit).all()
    now = datetime.utcnow()
    rows = []
    stats = {'ok': 0, 'due': 0, 'overdue': 0, 'complimentary': 0, 'trial': 0}
    for org in orgs:
        status = refresh_billing_status(org)
        if (org.status or '') == 'trial':
            stats['trial'] = stats.get('trial', 0) + 1
        stats[status] = stats.get(status, 0) + 1
        end = org.current_period_end or org.trial_ends_at
        days_left = (end - now).days if end else None
        rows.append({
            'org': org,
            'billing_status': status,
            'amount': effective_amount(org),
            'period_end': end,
            'days_left': days_left,
            'free': is_policy_free_org(org),
        })
    db.session.commit()  # حفظ حالات محدّثة
    # ترتيب: overdue ثم due ثم الباقي
    order = {'overdue': 0, 'due': 1, 'ok': 2, 'complimentary': 3}
    rows.sort(key=lambda r: (order.get(r['billing_status'], 9), r['days_left'] if r['days_left'] is not None else 9999))
    monthly, yearly = _plan_price_maps()
    books = books_snapshot(year=year)
    return {
        'rows': rows,
        'stats': stats,
        'plan_prices': monthly,
        'plan_prices_yearly': yearly,
        'books': books,
        'company': NASQ_CORE,
        'expense_categories': EXPENSE_CATEGORIES,
    }
