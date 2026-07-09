"""اشتراكات عملاء LiftCore — إدارة يدوية من لوحة المنصة (بدون بوابة دفع)."""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta

from models import Organization, PlatformPayment, db

# أسعار افتراضية ر.س / شهر — قابلة للتجاوز لكل مؤسسة
PLAN_MONTHLY_SAR = {
    'basic': 299.0,
    'pro': 599.0,
    'enterprise': 1499.0,
}

BILLING_STATUSES = ('ok', 'due', 'overdue', 'complimentary')
BILLING_CYCLES = ('monthly', 'yearly')
PAYMENT_METHODS = ('transfer', 'cash', 'card', 'complimentary', 'other')


def plan_price(plan: str | None, cycle: str = 'monthly') -> float:
    monthly = PLAN_MONTHLY_SAR.get((plan or 'basic').strip().lower(), PLAN_MONTHLY_SAR['basic'])
    if (cycle or 'monthly').strip().lower() == 'yearly':
        return round(monthly * 12 * 0.9, 2)  # خصم 10% سنوي
    return float(monthly)


def effective_amount(org: Organization) -> float:
    if org.billing_amount is not None and float(org.billing_amount) > 0:
        return float(org.billing_amount)
    return plan_price(org.plan, org.billing_cycle or 'monthly')


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


def refresh_billing_status(org: Organization, *, commit: bool = False) -> str:
    """حدّث billing_status حسب تاريخ انتهاء الفترة / التجربة."""
    if (org.billing_status or '') == 'complimentary':
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
    org.billing_status = 'ok'
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
        amount=amount,
        currency='SAR',
        method=method,
        reference=(reference or '').strip()[:100] or None,
        note=(note or '').strip() or None,
        period_start=start,
        period_end=end,
        plan=org.plan,
        recorded_by_user_id=recorded_by_user_id,
        paid_at=now,
    )
    db.session.add(payment)

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
    db.session.commit()
    return {'ok': True, 'payment': payment, 'org': org}


def list_payments(org_id: int, limit: int = 50) -> list[PlatformPayment]:
    return (
        PlatformPayment.query.filter_by(organization_id=org_id)
        .order_by(PlatformPayment.id.desc())
        .limit(limit)
        .all()
    )


def billing_overview(limit: int = 200) -> dict:
    """ملخص فوترة لكل المؤسسات (ما عدا default إن رغبت لاحقاً)."""
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
        })
    db.session.commit()  # حفظ حالات محدّثة
    # ترتيب: overdue ثم due ثم الباقي
    order = {'overdue': 0, 'due': 1, 'ok': 2, 'complimentary': 3}
    rows.sort(key=lambda r: (order.get(r['billing_status'], 9), r['days_left'] if r['days_left'] is not None else 9999))
    return {'rows': rows, 'stats': stats, 'plan_prices': PLAN_MONTHLY_SAR}
