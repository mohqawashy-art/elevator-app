"""طلبات التجربة وعروض السعر من صفحات التسويق — حفظ وعرض في المنصة."""
from __future__ import annotations

import re
from datetime import datetime

from models import SalesLead, db

_SPAM_COMPANIES = frozenset({
    'roberthob',
    'hiltonconge',
})
_ARABIC_RE = re.compile(r'[\u0600-\u06FF]')
_REPEAT_CHAR_RE = re.compile(r'(.)\1{6,}')


def is_spam_sales_lead(
    *,
    company_name: str,
    contact_name: str,
    contact_email: str,
    phone: str = '',
    city: str = '',
    notes: str = '',
) -> bool:
    """يصد طلبات البوت المتكررة دون منع عميل سعودي حقيقي."""
    company = (company_name or '').strip().lower()
    name = (contact_name or '').strip().lower()
    email = (contact_email or '').strip().lower()
    note = (notes or '').strip()
    if company in _SPAM_COMPANIES or name in _SPAM_COMPANIES:
        return True
    blob = f'{company} {name} {note} {email}'
    if _REPEAT_CHAR_RE.search(blob):
        return True
    tokens = re.findall(r'\S+', note)
    if len(note) >= 40 and tokens:
        short = sum(1 for t in tokens if len(t) <= 2)
        if short / len(tokens) >= 0.45:
            return True
    combined = f'{company_name or ""}{contact_name or ""}{city or ""}'
    has_ar = bool(_ARABIC_RE.search(combined))
    phone_digits = re.sub(r'\D', '', phone or '')
    if (
        not has_ar
        and company
        and company == name
        and phone_digits.startswith('8')
        and len(phone_digits) >= 10
    ):
        return True
    return False


REQUEST_TYPES = {
    'demo': 'طلب تجربة',
    'quote': 'عرض سعر',
}

LEAD_STATUSES = {
    'new': 'جديد',
    'contacted': 'تم التواصل',
    'fulfilled': 'تم الإرسال',
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
    utm_source: str = '',
    utm_medium: str = '',
    utm_campaign: str = '',
    gclid: str = '',
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
        utm_source=(utm_source or '').strip()[:80] or None,
        utm_medium=(utm_medium or '').strip()[:80] or None,
        utm_campaign=(utm_campaign or '').strip()[:120] or None,
        gclid=(gclid or '').strip()[:120] or None,
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
        'fulfilled': by_status.get('fulfilled', 0),
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


def get_sales_lead(lead_id: int) -> SalesLead | None:
    return db.session.get(SalesLead, int(lead_id))


def _plans_quote_text() -> str:
    from plan_catalog import PLAN_ORDER, plan_definition

    lines = []
    for key in PLAN_ORDER:
        p = plan_definition(key)
        label = p.get('label') or key
        yearly = p.get('yearly_sar')
        elev = (p.get('limits') or {}).get('elevators')
        if yearly is None:
            lines.append(f'{label}: عرض مخصص للمؤسسات')
        else:
            elev_txt = f' — حتى {elev} مصعد' if elev else ''
            lines.append(f'{label}: {yearly:,.0f} ر.س / سنة{elev_txt}')
    return '\n'.join(lines) + '\n'


def fulfill_demo_lead(lead_id: int, *, password_hasher) -> dict:
    """موافقة على تجربة: إنشاء حساب ديمو + إرسال بيانات الدخول للعميل."""
    from demo_provisioning import create_demo_account
    from liftcore_mail import send_demo_access_email

    lead = get_sales_lead(lead_id)
    if not lead:
        return {'ok': False, 'error': 'الطلب غير موجود.'}
    if (lead.request_type or '') != 'demo':
        return {'ok': False, 'error': 'هذا الطلب ليس طلب تجربة.'}
    if lead.status == 'fulfilled' and lead.result_org_id:
        return {'ok': False, 'error': 'تم إرسال تجربة لهذا الطلب مسبقاً.'}

    result = create_demo_account(
        company_name=lead.company_name,
        contact_name=lead.contact_name,
        contact_email=lead.contact_email,
        days=2,
        password_hasher=password_hasher,
    )
    if not result.get('ok'):
        return {
            'ok': False,
            'error': ' — '.join(result.get('errors') or ['فشل إنشاء الحساب التجريبي.']),
        }

    ends = result.get('trial_ends_at')
    ends_txt = ends.strftime('%Y-%m-%d %H:%M') if ends else ''
    mail = send_demo_access_email(
        to_email=lead.contact_email,
        contact_name=lead.contact_name,
        company_name=result.get('company_name') or lead.company_name,
        username=result['username'],
        password=result['password'],
        login_url=result['login_url'],
        days=int(result.get('days') or 2),
        trial_ends_at=ends_txt,
    )

    lead.status = 'fulfilled'
    lead.fulfilled_at = datetime.utcnow()
    lead.result_org_id = result.get('organization_id')
    lead.customer_mail_sent = bool(mail.get('ok'))
    lead.action_note = (
        f"تجربة: {result.get('slug')} · يوزر {result.get('username')} · "
        f"{result.get('login_url')}"
    )[:500]
    if not mail.get('ok'):
        lead.email_error = (mail.get('detail') or mail.get('reason') or 'mail_failed')[:300]
    else:
        lead.email_error = None
    lead.updated_at = datetime.utcnow()
    db.session.commit()

    return {
        'ok': True,
        'lead': lead,
        'demo': result,
        'mail': mail,
        'password': result['password'],
    }


def fulfill_quote_lead(lead_id: int) -> dict:
    """إرسال عرض أسعار بالبريد للعميل."""
    from liftcore_mail import send_pricing_quote_email

    lead = get_sales_lead(lead_id)
    if not lead:
        return {'ok': False, 'error': 'الطلب غير موجود.'}
    if (lead.request_type or '') != 'quote':
        return {'ok': False, 'error': 'هذا الطلب ليس عرض سعر.'}
    if lead.status == 'fulfilled' and lead.customer_mail_sent:
        return {'ok': False, 'error': 'تم إرسال عرض السعر مسبقاً.'}

    mail = send_pricing_quote_email(
        to_email=lead.contact_email,
        contact_name=lead.contact_name,
        company_name=lead.company_name,
        elevators_hint=lead.elevators or '',
        plans_text=_plans_quote_text(),
        pricing_url='https://liftcoreapp.com/pricing',
    )
    if not mail.get('ok'):
        lead.email_error = (mail.get('detail') or mail.get('reason') or 'mail_failed')[:300]
        lead.updated_at = datetime.utcnow()
        db.session.commit()
        return {
            'ok': False,
            'error': f"تعذّر إرسال البريد ({mail.get('reason') or 'failed'}).",
            'mail': mail,
        }

    lead.status = 'fulfilled'
    lead.fulfilled_at = datetime.utcnow()
    lead.customer_mail_sent = True
    lead.email_error = None
    lead.action_note = f'عُرض سعر أُرسل إلى {lead.contact_email}'[:500]
    lead.updated_at = datetime.utcnow()
    db.session.commit()
    return {'ok': True, 'lead': lead, 'mail': mail}


def clear_all_sales_leads() -> int:
    """يحذف كل طلبات المبيعات. يرجع العدد المحذوف."""
    n = SalesLead.query.delete()
    db.session.commit()
    return int(n or 0)


def request_type_label(key: str) -> str:
    return REQUEST_TYPES.get((key or '').lower(), key or '—')


def status_label(key: str) -> str:
    return LEAD_STATUSES.get((key or '').lower(), key or '—')
