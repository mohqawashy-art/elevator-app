"""مدفوعات اشتراك المنصة عبر Moyasar (فاتورة مستضافة)."""
from __future__ import annotations

import base64
import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest

from platform_billing import effective_amount, record_payment


def moyasar_enabled() -> bool:
    return bool((os.environ.get('MOYASAR_SECRET_KEY') or '').strip())


def moyasar_secret_key() -> str:
    return (os.environ.get('MOYASAR_SECRET_KEY') or '').strip()


def moyasar_publishable_key() -> str:
    return (os.environ.get('MOYASAR_PUBLISHABLE_KEY') or '').strip()


def _auth_header() -> str:
    token = base64.b64encode(f'{moyasar_secret_key()}:'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def _public_base() -> str:
    return (os.environ.get('LIFTCORE_PUBLIC_BASE') or 'https://liftcoreapp.com').rstrip('/')


# Cloudflare أمام api.moyasar.com يحجب User-Agent الافتراضي لـ urllib (Error 1010).
_MOYASAR_UA = 'LiftCore/1.0 (+https://liftcoreapp.com; subscription-billing)'


def _moyasar_headers(*, json_body: bool = True) -> dict:
    headers = {
        'Authorization': _auth_header(),
        'Accept': 'application/json',
        'User-Agent': _MOYASAR_UA,
    }
    if json_body:
        headers['Content-Type'] = 'application/json'
    return headers


def create_subscription_invoice(org, *, callback_base: str | None = None) -> dict:
    """ينشئ فاتورة Moyasar لتجديد اشتراك المؤسسة. يعيد {ok, url, id, errors}."""
    if not moyasar_enabled():
        return {'ok': False, 'errors': ['بوابة الدفع غير مفعّلة — عيّن MOYASAR_SECRET_KEY.']}

    amount_sar = float(effective_amount(org))
    if amount_sar <= 0:
        return {'ok': False, 'errors': ['مبلغ الاشتراك غير صالح.']}

    amount_halalas = int(round(amount_sar * 100))
    base = (callback_base or _public_base()).rstrip('/')
    # رجوع للـ subdomain الحالي إن وُجد في callback_base
    success_url = f'{base}/settings?tab=plan&paid=1'
    back_url = f'{base}/settings?tab=plan&paid=0'

    body = {
        'amount': amount_halalas,
        'currency': 'SAR',
        'description': f'LiftCore subscription — {org.slug} ({org.plan or "basic"})',
        'callback_url': f'{_public_base()}/api/webhooks/moyasar',
        'success_url': success_url,
        'back_url': back_url,
        'metadata': {
            'organization_id': str(org.id),
            'organization_slug': org.slug or '',
            'plan': org.plan or 'basic',
            'billing_cycle': org.billing_cycle or 'monthly',
            'purpose': 'subscription_renewal',
        },
    }
    data = json.dumps(body).encode('utf-8')
    req = urlrequest.Request(
        'https://api.moyasar.com/v1/invoices',
        data=data,
        headers=_moyasar_headers(json_body=True),
        method='POST',
    )
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace') if exc.fp else str(exc)
        return {'ok': False, 'errors': [f'Moyasar HTTP {exc.code}: {detail[:300]}']}
    except urlerror.URLError as exc:
        return {'ok': False, 'errors': [f'Moyasar connection error: {exc.reason or exc}']}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {'ok': False, 'errors': [f'Moyasar response error: {exc}']}

    url = (payload.get('url') or '').strip()
    inv_id = (payload.get('id') or '').strip()
    if not url or not inv_id:
        return {'ok': False, 'errors': ['استجابة Moyasar ناقصة (url/id).'], 'raw': payload}
    return {'ok': True, 'url': url, 'id': inv_id, 'amount': amount_sar, 'raw': payload}


def apply_moyasar_payment_event(payload: dict) -> dict:
    """يعالج حدث دفع ناجح من Moyasar — idempotent عبر reference."""
    from models import Organization, PlatformPayment, db

    if not isinstance(payload, dict):
        return {'ok': False, 'errors': ['payload غير صالح']}

    # شكل الفاتورة أو الدفعة
    data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
    status = (data.get('status') or payload.get('status') or '').strip().lower()
    if status not in ('paid', 'captured'):
        return {'ok': True, 'ignored': True, 'reason': f'status={status or "unknown"}'}

    payment_id = (data.get('id') or '').strip()
    if not payment_id:
        return {'ok': False, 'errors': ['معرف الدفع مفقود']}

    existing = PlatformPayment.query.filter_by(reference=payment_id).first()
    if existing:
        return {'ok': True, 'duplicate': True, 'payment_id': existing.id}

    meta = data.get('metadata') if isinstance(data.get('metadata'), dict) else {}
    org_id_raw = meta.get('organization_id') or data.get('organization_id')
    try:
        org_id = int(org_id_raw)
    except (TypeError, ValueError):
        return {'ok': False, 'errors': ['organization_id مفقود في metadata']}

    org = db.session.get(Organization, org_id)
    if not org:
        return {'ok': False, 'errors': [f'مؤسسة غير موجودة: {org_id}']}

    amount_halalas = data.get('amount')
    try:
        amount_sar = float(amount_halalas) / 100.0
    except (TypeError, ValueError):
        amount_sar = effective_amount(org)

    cycle = org.billing_cycle or 'monthly'
    months = 12 if cycle == 'yearly' else 1
    result = record_payment(
        org,
        amount=amount_sar,
        method='card',
        reference=payment_id,
        note='Moyasar auto-renewal',
        months=months,
    )
    if not result.get('ok'):
        return result
    return {
        'ok': True,
        'payment_id': result['payment'].id,
        'organization_id': org.id,
        'amount': amount_sar,
    }
