"""إرسال بريد المنصة — ترحيب التسجيل ودعوات الانضمام (Resend اختياري)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def _mail_from() -> str:
    raw = os.environ.get('MAIL_FROM', 'noreply@liftcoreapp.com').strip()
    if not raw:
        raw = 'noreply@liftcoreapp.com'
    # Resend يقبل "Name <email@domain>" — أفضل للتسليم
    if '<' not in raw and '@' in raw:
        return f'LiftCore <{raw}>'
    return raw


def _ensure_mail_env() -> None:
    """أعد قراءة MAIL_* من platform.env قبل الإرسال (يتجاوز بيئة قديمة في Gunicorn)."""
    path = '/etc/liftcore/platform.env'
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding='utf-8') as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, val = line.partition('=')
                key = key.strip().lstrip('\ufeff')
                if key not in ('MAIL_API_KEY', 'MAIL_FROM'):
                    continue
                os.environ[key] = val.strip().strip('"').strip("'")
    except OSError as exc:
        logger.warning('could not refresh mail env from %s: %s', path, exc)


def mail_configured() -> bool:
    _ensure_mail_env()
    return bool(os.environ.get('MAIL_API_KEY', '').strip())


def _parse_resend_error(body: bytes | str) -> str:
    text = body.decode('utf-8', errors='replace') if isinstance(body, (bytes, bytearray)) else str(body or '')
    text = text.strip()
    if not text:
        return ''
    try:
        data = json.loads(text)
    except Exception:
        return text[:180]
    if isinstance(data, dict):
        msg = data.get('message') or data.get('error') or data.get('name') or ''
        if isinstance(msg, dict):
            msg = msg.get('message') or str(msg)
        return str(msg)[:180]
    return text[:180]


def _send_email(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    log_tag: str,
    reply_to: str | None = None,
) -> dict:
    """يرجع {ok, reason, detail?} — ok=True فقط عند إرسال فعلي ناجح."""
    _ensure_mail_env()
    to_email = (to_email or '').strip()
    if not to_email:
        logger.warning('%s skipped — empty recipient', log_tag)
        return {'ok': False, 'reason': 'empty_recipient'}

    api_key = os.environ.get('MAIL_API_KEY', '').strip()
    if not api_key:
        logger.warning(
            '%s not sent — MAIL_API_KEY missing (to=%s subject=%s)',
            log_tag, to_email, subject,
        )
        return {'ok': False, 'reason': 'mail_not_configured'}

    payload = {
        'from': _mail_from(),
        'to': [to_email],
        'subject': subject,
        'text': body_text,
    }
    reply = (reply_to or '').strip()
    if reply and '@' in reply:
        payload['reply_to'] = reply
    req = urllib.request.Request(
        'https://api.resend.com/emails',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            # Resend/Cloudflare يرفض الطلبات بدون User-Agent (error 1010)
            'User-Agent': 'LiftCore/1.0 (+https://liftcoreapp.com)',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if 200 <= resp.status < 300:
                return {'ok': True, 'reason': 'sent'}
            detail = _parse_resend_error(resp.read()[:500])
            return {'ok': False, 'reason': f'http_{resp.status}', 'detail': detail}
    except urllib.error.HTTPError as exc:
        raw = exc.read()[:500]
        detail = _parse_resend_error(raw)
        logger.warning('Resend HTTP %s (%s): %s', exc.code, log_tag, raw)
        return {'ok': False, 'reason': f'http_{exc.code}', 'detail': detail}
    except OSError as exc:
        logger.warning('Resend send failed (%s): %s', log_tag, exc)
        return {'ok': False, 'reason': 'network_error', 'detail': str(exc)[:120]}


def _as_bool(result: dict | bool) -> bool:
    if isinstance(result, dict):
        return bool(result.get('ok'))
    return bool(result)


def send_welcome_email(
    *,
    to_email: str,
    company_name: str,
    slug: str,
    admin_name: str,
    login_url: str,
) -> bool:
    """يرسل بريد ترحيب. يرجع False إن لم يُضبط MAIL_API_KEY أو فشل الإرسال."""
    subject = f'مرحباً بك في LiftCore — {company_name}'
    body_text = (
        f'مرحباً {admin_name},\n\n'
        f'تم إنشاء حساب «{company_name}» بنجاح.\n'
        f'رابط الدخول: {login_url}\n\n'
        f'معرّف المؤسسة: {slug}\n'
        '— فريق LiftCore'
    )
    return _as_bool(_send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        log_tag='signup welcome',
    ))


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


def send_demo_request_email(
    *,
    sales_email: str,
    company_name: str,
    contact_name: str,
    contact_email: str,
    phone: str = '',
    city: str = '',
    elevators: str = '',
    notes: str = '',
    request_type: str = 'demo',
) -> dict:
    """يرسل طلب تجربة أو عرض سعر إلى بريد المبيعات مع Reply-To لبريد العميل."""
    company = (company_name or '').strip() or '—'
    name = (contact_name or '').strip() or '—'
    email = (contact_email or '').strip()
    kind = 'عرض سعر' if (request_type or '').lower() == 'quote' else 'عرض تجريبي'
    subject = f'طلب {kind} — {company}'
    body_text = (
        f'طلب {kind} من صفحة التعريف\n'
        '================================\n\n'
        f'الشركة: {company}\n'
        f'المسؤول: {name}\n'
        f'البريد: {email or "—"}\n'
        f'الجوال: {(phone or "").strip() or "—"}\n'
        f'المدينة: {(city or "").strip() or "—"}\n'
        f'عدد المصاعد تقريباً: {(elevators or "").strip() or "—"}\n'
        f'ملاحظات:\n{(notes or "").strip() or "—"}\n'
    )
    return _send_email(
        to_email=sales_email,
        subject=subject,
        body_text=body_text,
        log_tag='demo request',
        reply_to=email,
    )


def mail_result_message(result: dict | bool, *, to_email: str) -> tuple[str, str]:
    """(notice, notice_type) لواجهة المشغّل."""
    if isinstance(result, bool):
        result = {'ok': result, 'reason': 'sent' if result else 'failed'}
    if result.get('ok'):
        return f'تم إرسال البريد إلى {to_email}.', 'ok'
    reason = result.get('reason') or 'failed'
    if reason == 'mail_not_configured':
        return (
            'لم يُرسل البريد: MAIL_API_KEY غير مضبوط على السيرفر. '
            'أضفه في /etc/liftcore/platform.env ثم أعد تشغيل الخدمة. '
            f'انسخ الرابط يدوياً للعميل.',
            'warn',
        )
    if reason == 'empty_recipient':
        return 'لم يُرسل البريد: لا يوجد عنوان مستلم.', 'warn'
    detail = (result.get('detail') or '').strip()
    if detail:
        return f'تعذّر إرسال البريد إلى {to_email} ({reason}): {detail}', 'warn'
    return f'تعذّر إرسال البريد إلى {to_email} ({reason}). انسخ الرابط يدوياً.', 'warn'
