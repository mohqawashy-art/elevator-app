"""إرسال عروض السعر للعميل عبر واتساب أو البريد."""
from __future__ import annotations

from urllib.parse import quote

from operations import whatsapp_url


def _company_name(settings) -> str:
    if not settings:
        return 'LiftCore'
    return (
        (getattr(settings, 'company_name_ar', None) or '').strip()
        or (getattr(settings, 'company_name', None) or '').strip()
        or 'LiftCore'
    )


def install_quote_message(*, company: str, customer_name: str, quote_code: str, total: float, print_url: str) -> str:
    total_txt = f'{float(total or 0):,.0f}'
    return (
        f'مرحباً {customer_name or "العميل"}،\n'
        f'إليكم عرض السعر {quote_code} من {company}.\n'
        f'الإجمالي شامل الضريبة: {total_txt} ر.س\n'
        f'للاطلاع والطباعة:\n{print_url}\n'
        f'يسعدنا تواصلكم بعد المراجعة.'
    )


def maintenance_quote_message(*, company: str, customer_name: str, quote_code: str, total: float, print_url: str) -> str:
    total_txt = f'{float(total or 0):,.2f}'
    return (
        f'مرحباً {customer_name or "العميل"}،\n'
        f'إليكم عرض سعر الصيانة {quote_code} من {company}.\n'
        f'الإجمالي شامل الضريبة: {total_txt} ر.س\n'
        f'للاطلاع والطباعة:\n{print_url}\n'
        f'يسعدنا تواصلكم بعد المراجعة.'
    )


def mailto_url(*, email: str, subject: str, body: str) -> str:
    email = (email or '').strip()
    if not email or '@' not in email:
        return ''
    return f'mailto:{email}?subject={quote(subject)}&body={quote(body)}'


def delivery_links_for_install_quote(quotation, *, print_url: str, settings=None) -> dict:
    company = _company_name(settings)
    customer = getattr(quotation, 'customer', None)
    name = (
        (getattr(quotation, 'client_name', None) or '').strip()
        or (customer.name if customer else '')
        or 'العميل'
    )
    phone = (
        (getattr(quotation, 'client_phone', None) or '').strip()
        or (getattr(customer, 'phone', None) if customer else '')
        or (getattr(customer, 'phone2', None) if customer else '')
        or ''
    )
    email = (getattr(customer, 'email', None) if customer else '') or ''
    code = quotation.code or ''
    total = getattr(quotation, 'grand_total', None) or 0
    msg = install_quote_message(
        company=company,
        customer_name=name,
        quote_code=code,
        total=total,
        print_url=print_url,
    )
    return {
        'whatsapp_url': whatsapp_url(phone, msg),
        'mailto_url': mailto_url(
            email=email,
            subject=f'عرض سعر {code} — {company}',
            body=msg,
        ),
        'message': msg,
        'has_phone': bool(phone),
        'has_email': bool(email and '@' in email),
    }


def delivery_links_for_maint_quote(quote, *, print_url: str, settings=None) -> dict:
    company = _company_name(settings)
    customer = getattr(quote, 'customer', None)
    name = (customer.name if customer else '') or 'العميل'
    phone = ''
    email = ''
    if customer:
        phone = (customer.phone or customer.phone2 or '').strip()
        email = (getattr(customer, 'email', None) or '').strip()
    code = quote.code or ''
    total = quote.total or 0
    msg = maintenance_quote_message(
        company=company,
        customer_name=name,
        quote_code=code,
        total=total,
        print_url=print_url,
    )
    return {
        'whatsapp_url': whatsapp_url(phone, msg),
        'mailto_url': mailto_url(
            email=email,
            subject=f'عرض سعر صيانة {code} — {company}',
            body=msg,
        ),
        'message': msg,
        'has_phone': bool(phone),
        'has_email': bool(email and '@' in email),
    }
