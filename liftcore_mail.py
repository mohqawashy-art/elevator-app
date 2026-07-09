"""إرسال بريد المنصة — ترحيب التسجيل (Resend اختياري)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def _mail_from() -> str:
    return os.environ.get('MAIL_FROM', 'noreply@liftcoreapp.com').strip()


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
    api_key = os.environ.get('MAIL_API_KEY', '').strip()
    if not api_key:
        logger.info(
            'signup welcome (dry-run) to=%s slug=%s url=%s',
            to_email, slug, login_url,
        )
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
        logger.warning('Resend HTTP %s: %s', exc.code, exc.read()[:500])
        return False
    except OSError as exc:
        logger.warning('Resend send failed: %s', exc)
        return False
