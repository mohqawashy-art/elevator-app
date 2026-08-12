"""طلبات التجربة وعروض السعر من صفحات التسويق — حفظ وعرض في المنصة."""
from __future__ import annotations

from datetime import datetime

from models import SalesLead, db


REQUEST_TYPES = {
    'demo': 'طلب تجربة',
    'quote': 'عرض سعر',
}

LEAD_STATUSES = {
    'new': 'جديد',
    'contacted': 'تم التواصل',
    'closed': 'مغلق',
}


def create_sales_lead(
    *,
    company_name: str,
    contact_name: str,
    contact_email: str,
    phone: str = '',
    city: str = '',
    elevators: str = '',
    notes: str = '',
    request_type: str = 'demo',
    source_path: str = '/',
) -> SalesLead:
    rtype = (request_type or 'demo').strip().lower()
    if rtype not in REQUEST_TYPES:
        rtype = 'demo'
    lead = SalesLead(
        request_type=rtype,
        status='new',
        company_name=(company_name or '').strip()[:200],
        contact_name=(contact_name or '').strip()[:100],
        contact_email=(contact_email or '').strip()[:120].lower(),
        phone=(phone or '').strip()[:40] or None,
        city=(city or '').strip()[:100] or None,
        elevators=(elevators or '').strip()[:40] or None,
        notes=(notes or '').strip()[:2000] or None,
        source_path=(source_path or '/')[:40],
        email_sent=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(lead)
    db.session.commit()
    return lead


def mark_lead_email_result(lead: SalesLead, result: dict) -> None:
    lead.email_sent = bool(result.get('ok'))
    if result.get('ok'):
        lead.email_error = None
    else:
        reason = (result.get('reason') or 'failed')[:80]
        detail = (result.get('detail') or '')[:200]
        lead.email_error = (f'{reason}: {detail}' if detail else reason)[:300]
    lead.updated_at = datetime.utcnow()
    db.session.commit()


def list_sales_leads(*, status: str = '', limit: int = 200) -> list[SalesLead]:
    q = SalesLead.query
    status = (status or '').strip().lower()
    if status in LEAD_STATUSES:
        q = q.filter(SalesLead.status == status)
    return q.order_by(SalesLead.id.desc()).limit(limit).all()


def sales_lead_stats() -> dict:
    rows = (
        db.session.query(SalesLead.status, db.func.count(SalesLead.id))
        .group_by(SalesLead.status)
        .all()
    )
    by_status = {s or 'unknown': n for s, n in rows}
    return {
        'total': sum(by_status.values()),
        'new': by_status.get('new', 0),
        'contacted': by_status.get('contacted', 0),
        'closed': by_status.get('closed', 0),
        'by_status': by_status,
    }


def set_sales_lead_status(lead_id: int, status: str) -> SalesLead | None:
    status = (status or '').strip().lower()
    if status not in LEAD_STATUSES:
        return None
    lead = db.session.get(SalesLead, int(lead_id))
    if not lead:
        return None
    lead.status = status
    lead.updated_at = datetime.utcnow()
    db.session.commit()
    return lead


def request_type_label(key: str) -> str:
    return REQUEST_TYPES.get((key or '').lower(), key or '—')


def status_label(key: str) -> str:
    return LEAD_STATUSES.get((key or '').lower(), key or '—')
