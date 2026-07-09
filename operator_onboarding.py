"""دعوات انضمام العملاء — إنشاء / استلام فورم / تفعيل من لوحة المشغّل."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta

from flask import g

from models import OnboardingInvite, Organization, Settings, ZatcaCredentials, db
from tenant_signup import (
    normalize_slug,
    validate_admin_name,
    validate_company_name,
    validate_email,
    validate_slug,
)


PLANS = ('basic', 'pro', 'enterprise')
INVITE_TTL_DAYS = int(os.environ.get('LIFTCORE_INVITE_DAYS', '14') or 14)


def operator_org_slugs() -> set[str]:
    raw = os.environ.get('LIFTCORE_OPERATOR_ORGS', 'default')
    return {s.strip().lower() for s in raw.split(',') if s.strip()} or {'default'}


def is_platform_operator(user) -> bool:
    """مشغّل المنصة = admin على مؤسسة default (أو قائمة LIFTCORE_OPERATOR_ORGS)."""
    if not user or getattr(user, 'role', None) != 'admin':
        return False
    org = getattr(g, 'organization', None)
    slug = getattr(org, 'slug', None) if org else None
    if not slug:
        return False
    return slug.lower() in operator_org_slugs()


def _new_token() -> str:
    return secrets.token_urlsafe(32)[:64]


def create_invite(
    *,
    plan: str = 'basic',
    suggested_slug: str = '',
    contact_email: str = '',
    contact_name: str = '',
    notes: str = '',
    created_by_user_id: int | None = None,
    days: int | None = None,
) -> dict:
    plan = (plan or 'basic').strip().lower()
    if plan not in PLANS:
        return {'ok': False, 'errors': ['باقة غير معروفة.']}
    slug = normalize_slug(suggested_slug) if suggested_slug else ''
    if slug:
        err = validate_slug(slug)
        if err:
            return {'ok': False, 'errors': [err]}
    email = (contact_email or '').strip()
    err = validate_email(email)
    if err:
        return {'ok': False, 'errors': [err or 'بريد العميل مطلوب لإرسال رابط الدعوة.']}

    ttl = max(1, int(days if days is not None else INVITE_TTL_DAYS))
    inv = OnboardingInvite(
        token=_new_token(),
        status='pending',
        plan=plan,
        suggested_slug=slug or None,
        contact_email=email,
        contact_name=(contact_name or '').strip() or None,
        notes=(notes or '').strip() or None,
        expires_at=datetime.utcnow() + timedelta(days=ttl),
        created_by_user_id=created_by_user_id,
    )
    db.session.add(inv)
    db.session.commit()
    url = invite_public_url(inv.token)
    return {
        'ok': True,
        'invite': inv,
        'url': url,
        'ttl_days': ttl,
    }


def invite_public_url(token: str) -> str:
    base = os.environ.get('LIFTCORE_PUBLIC_BASE', 'https://liftcoreapp.com').rstrip('/')
    return f'{base}/onboard/{token}'


def get_invite(token: str) -> OnboardingInvite | None:
    token = (token or '').strip()
    if not token:
        return None
    return OnboardingInvite.query.filter_by(token=token).first()


def invite_is_open(inv: OnboardingInvite) -> tuple[bool, str | None]:
    if not inv:
        return False, 'الدعوة غير موجودة.'
    if inv.status in ('activated', 'cancelled'):
        return False, 'هذه الدعوة لم تعد متاحة.'
    if inv.status == 'submitted':
        return False, 'تم إرسال البيانات مسبقاً — بانتظار التفعيل.'
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        if inv.status == 'pending':
            inv.status = 'expired'
            db.session.commit()
        return False, 'انتهت صلاحية رابط الدعوة.'
    if inv.status != 'pending':
        return False, 'الدعوة غير متاحة للتعبئة.'
    return True, None


def submit_invite_form(inv: OnboardingInvite, data: dict) -> dict:
    ok, err = invite_is_open(inv)
    if not ok:
        return {'ok': False, 'errors': [err]}

    company_name = (data.get('company_name') or '').strip()
    admin_name = (data.get('admin_name') or '').strip()
    admin_email = (data.get('admin_email') or '').strip()
    preferred = normalize_slug(data.get('preferred_slug') or inv.suggested_slug or '')

    errors = []
    for e in (
        validate_company_name(company_name),
        validate_admin_name(admin_name),
        validate_email(admin_email),
    ):
        if e:
            errors.append(e)
    if preferred:
        e = validate_slug(preferred)
        if e:
            errors.append(e)
    if errors:
        return {'ok': False, 'errors': errors}

    inv.company_name = company_name
    inv.company_name_en = (data.get('company_name_en') or '').strip() or None
    inv.cr_number = (data.get('cr_number') or '').strip() or None
    inv.vat_number = (data.get('vat_number') or '').strip() or None
    inv.phone = (data.get('phone') or '').strip() or None
    inv.email = (data.get('email') or admin_email).strip() or None
    inv.city = (data.get('city') or '').strip() or None
    inv.address = (data.get('address') or '').strip() or None
    inv.admin_name = admin_name
    inv.admin_email = admin_email
    inv.admin_phone = (data.get('admin_phone') or '').strip() or None
    inv.preferred_slug = preferred or None
    inv.status = 'submitted'
    inv.submitted_at = datetime.utcnow()
    db.session.commit()
    return {'ok': True, 'invite': inv}


def activate_invite(
    inv: OnboardingInvite,
    *,
    slug: str | None = None,
    plan: str | None = None,
    password: str,
    password_hash: str,
) -> dict:
    """تفعيل الدعوة → إنشاء organization + settings + admin."""
    from sqlalchemy.exc import IntegrityError
    from tenant_signup import create_tenant_signup

    if inv.status == 'activated':
        return {'ok': False, 'errors': ['تم تفعيل هذه الدعوة مسبقاً.']}
    if inv.status not in ('submitted', 'pending'):
        return {'ok': False, 'errors': ['لا يمكن تفعيل هذه الدعوة.']}
    if inv.expires_at and inv.expires_at < datetime.utcnow() and inv.status != 'submitted':
        return {'ok': False, 'errors': ['انتهت صلاحية الدعوة.']}

    company = (inv.company_name or '').strip()
    admin_name = (inv.admin_name or inv.contact_name or '').strip()
    admin_email = (inv.admin_email or inv.contact_email or '').strip()
    use_slug = normalize_slug(slug or inv.preferred_slug or inv.suggested_slug or '')
    use_plan = (plan or inv.plan or 'basic').strip().lower()
    if use_plan not in PLANS:
        use_plan = 'basic'

    if not company or not admin_name or not admin_email or not use_slug:
        return {'ok': False, 'errors': ['بيانات الدعوة غير مكتملة للتفعيل.']}
    if not password_hash:
        return {'ok': False, 'errors': ['كلمة المرور مطلوبة.']}

    result = create_tenant_signup(
        company_name=company,
        slug=use_slug,
        admin_email=admin_email,
        admin_name=admin_name,
        password_hash=password_hash,
        username=use_slug,
    )
    if not result.get('ok'):
        return result

    oid = result['organization_id']
    org = db.session.get(Organization, oid)
    if org:
        org.status = 'active'
        org.plan = use_plan
        org.trial_ends_at = None

    # تخطّي فلتر المستأجر (المشغّل على default / أو بدون request)
    prev_resolving = getattr(g, '_resolving_default_org', False)
    g._resolving_default_org = True
    try:
        settings = Settings.query.filter_by(organization_id=oid).first()
        if settings:
            settings.company_name_en = inv.company_name_en
            settings.cr_number = inv.cr_number
            settings.vat_number = inv.vat_number
            phone = (inv.phone or inv.admin_phone or '')[:20]
            settings.phone = phone or None
            settings.email = inv.email or admin_email
            settings.city = inv.city
            settings.address = inv.address

        vat = (inv.vat_number or '').strip()
        has_zatca = ZatcaCredentials.query.filter_by(organization_id=oid).first()
        if vat and not has_zatca:
            db.session.add(ZatcaCredentials(
                organization_id=oid,
                vat_number=vat[:15],
                cr_number=(inv.cr_number or '')[:20] or None,
                status='pending',
                environment='sandbox',
            ))
    finally:
        g._resolving_default_org = prev_resolving

    inv.status = 'activated'
    inv.activated_at = datetime.utcnow()
    inv.organization_id = oid
    inv.plan = use_plan
    inv.preferred_slug = use_slug
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {'ok': False, 'errors': ['تعذّر حفظ بيانات التفعيل.']}

    return {
        'ok': True,
        'organization_id': oid,
        'slug': use_slug,
        'username': result['username'],
        'login_url': result['login_url'],
        'plan': use_plan,
        'password': password,
    }


def list_invites(limit: int = 50) -> list[OnboardingInvite]:
    return (
        OnboardingInvite.query
        .order_by(OnboardingInvite.id.desc())
        .limit(limit)
        .all()
    )
