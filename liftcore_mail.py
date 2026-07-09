"""إرسال بريد المنصة — ترحيب التسجيل ودعوات الانضمام (Resend اختياري)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def _mail_from() -> str:
    return os.environ.get('MAIL_FROM', 'noreply@liftcoreapp.com').strip()


def _send_email(*, to_email: str, subject: str, body_text: str, log_tag: str) -> bool:
    to_email = (to_email or '').strip()
    if not to_email:
        logger.warning('%s skipped — empty recipient', log_tag)
        return False

    api_key = os.environ.get('MAIL_API_KEY', '').strip()
    if not api_key:
        logger.info('%s (dry-run) to=%s subject=%s', log_tag, to_email, subject)
        return True

    payload = {
        'from': _mail_from(),
        'to': [to_email],
        'subject': subject,
        'text': body_text,
    }
    req = urllib.request.Request(
        'https://api.resend.com/emails',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as exc:
        logger.warning('Resend HTTP %s (%s): %s', exc.code, log_tag, exc.read()[:500])
        return False
    except OSError as exc:
        logger.warning('Resend send failed (%s): %s', log_tag, exc)
        return False


def send_welcome_email(
    *,
    to_email: str,
    company_name: str,
    slug: str,
    admin_name: str,
    login_url: str,
) -> bool:
    """يرسل بريد ترحيب — أو يسجّل فقط إن لم يُضبط MAIL_API_KEY."""
    subject = f'مرحباً بك في LiftCore — {company_name}'
    body_text = (
        f'مرحباً {admin_name},\n\n'
        f'تم إنشاء حساب «{company_name}» بنجاح.\n'
        f'رابط الدخول: {login_url}\n\n'
        f'معرّف المؤسسة: {slug}\n'
        '— فريق LiftCore'
    )
    return _send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        log_tag='signup welcome',
    )


def send_onboarding_invite_email(
    *,
    to_email: str,
    contact_name: str,
    invite_url: str,
    plan: str = 'basic',
    days: int | None = None,
) -> bool:
    """يرسل رابط تعبئة بيانات الشركة للعميل بعد الاتفاق التجاري."""
    name = (contact_name or '').strip() or 'عميلنا الكريم'
    plan_label = (plan or 'basic').strip()
    ttl = f'\nصلاحية الرابط: {days} يوماً.\n' if days else '\n'
    subject = 'دعوة إكمال بيانات شركتك في LiftCore'
    body_text = (
        f'مرحباً {name},\n\n'
        'شكراً لاختيارك LiftCore.\n'
        'يرجى إكمال بيانات شركتك عبر الرابط التالي حتى نجهّز حسابك:\n\n'
        f'{invite_url}\n'
        f'{ttl}'
        f'الباقة المتفق عليها: {plan_label}\n\n'
        'بعد استلام البيانات سنراجعها ونفعّل الحساب ونرسل لك بيانات الدخول.\n\n'
        '— فريق LiftCore'
    )
    return _send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        log_tag='onboarding invite',
    )


def send_onboarding_activated_email(
    *,
    to_email: str,
    company_name: str,
    admin_name: str,
    slug: str,
    username: str,
    password: str,
    login_url: str,
    plan: str = 'basic',
) -> bool:
    """يرسل بيانات الدخول بعد تفعيل الدعوة."""
    name = (admin_name or '').strip() or 'عميلنا الكريم'
    subject = f'تم تفعيل حسابك في LiftCore — {company_name}'
    body_text = (
        f'مرحباً {name},\n\n'
        f'تم تفعيل حساب «{company_name}» بنجاح.\n\n'
        f'رابط الدخول: {login_url}\n'
        f'اسم المستخدم: {username}\n'
        f'كلمة المرور: {password}\n'
        f'معرّف المؤسسة: {slug}\n'
        f'الباقة: {plan}\n\n'
        'ننصح بتغيير كلمة المرور بعد أول دخول.\n\n'
        '— فريق LiftCore'
    )
    return _send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        log_tag='onboarding activated',
    )
