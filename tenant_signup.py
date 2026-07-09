"""تسجيل مؤسسة جديدة — أسبوع 7 (نطاق المنصة فقط)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta

from flask import abort, has_request_context, request

from models import Organization, Settings, User, db
from tenant_scope import MARKETING_SLUGS, PLATFORM_HOSTS

SLUG_RE = re.compile(r'^[a-z][a-z0-9-]{1,61}[a-z0-9]$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

RESERVED_SLUGS = frozenset({
    'default', 'jama', 'demo', 'test', 'liftcore', 'platform', 'signup', 'register',
}) | MARKETING_SLUGS

SIGNUP_HOSTS = frozenset({'liftcoreapp.com', 'www.liftcoreapp.com', 'localhost', '127.0.0.1'})


def signup_enabled() -> bool:
    return os.environ.get('LIFTCORE_SIGNUP_ENABLED', '').strip().lower() in (
        '1', 'true', 'yes', 'on',
    )


def is_signup_host(host: str | None = None) -> bool:
    if host is None:
        if not has_request_context():
            return False
        host = request.host or ''
    host = (host or '').split(':')[0].lower().rstrip('.')
    return host in SIGNUP_HOSTS


def require_signup_host():
    if not is_signup_host():
        abort(404)


def normalize_slug(raw: str) -> str:
    slug = (raw or '').strip().lower()
    slug = re.sub(r'[^a-z0-9-]+', '-', slug)
    slug = re.sub(r'-{2,}', '-', slug).strip('-')
    return slug


def validate_slug(slug: str) -> str | None:
    slug = normalize_slug(slug)
    if len(slug) < 3:
        return 'معرّف المؤسسة قصير جداً (3 أحرف على الأقل).'
    if len(slug) > 63:
        return 'معرّف المؤسسة طويل جداً.'
    if slug in RESERVED_SLUGS:
        return 'هذا المعرّف محجوز — اختر اسماً آخر.'
    if not SLUG_RE.match(slug):
        return 'المعرّف: حروف إنجليزية صغيرة وأرقام وشرطة فقط.'
    if Organization.query.filter_by(slug=slug).first():
        return 'هذا المعرّف مستخدم مسبقاً.'
    return None


def validate_email(email: str) -> str | None:
    email = (email or '').strip()
    if not email:
        return 'البريد الإلكتروني مطلوب.'
    if len(email) > 100:
        return 'البريد الإلكتروني طويل جداً.'
    if not EMAIL_RE.match(email):
        return 'صيغة البريد الإلكتروني غير صحيحة.'
    return None


def validate_company_name(name: str) -> str | None:
    name = (name or '').strip()
    if len(name) < 2:
        return 'اسم الشركة مطلوب.'
    if len(name) > 200:
        return 'اسم الشركة طويل جداً.'
    return None


def validate_admin_name(name: str) -> str | None:
    name = (name or '').strip()
    if len(name) < 2:
        return 'اسم المسؤول مطلوب.'
    if len(name) > 100:
        return 'اسم المسؤول طويل جداً.'
    return None


def _username_for_signup(slug: str, email: str) -> str:
    local = (email.split('@', 1)[0] or '').strip().lower()
    local = re.sub(r'[^a-z0-9_]+', '_', local)[:40]
    if local:
        return local
    return f'{slug}_admin'[:50]


def create_tenant_signup(
    *,
    company_name: str,
    slug: str,
    admin_email: str,
    admin_name: str,
    password_hash: str,
    username: str | None = None,
) -> dict:
    """ينشئ organization + admin + settings — بدون nginx/systemd."""
    slug = normalize_slug(slug)
    company_name = company_name.strip()
    admin_email = admin_email.strip()
    admin_name = admin_name.strip()

    errors: list[str] = []
    for err in (
        validate_company_name(company_name),
        validate_slug(slug),
        validate_email(admin_email),
        validate_admin_name(admin_name),
    ):
        if err:
            errors.append(err)
    if errors:
        return {'ok': False, 'errors': errors}

    uname = (username or _username_for_signup(slug, admin_email)).strip().lower()[:50]
    if not uname:
        return {'ok': False, 'errors': ['اسم المستخدم غير صالح.']}

    trial_days = int(os.environ.get('LIFTCORE_TRIAL_DAYS', '14') or 14)
    trial_ends = datetime.utcnow() + timedelta(days=max(1, trial_days))

    org = Organization(
        slug=slug,
        name=company_name,
        status='trial',
        plan='basic',
        admin_email=admin_email,
        trial_ends_at=trial_ends,
    )
    db.session.add(org)
    db.session.flush()

    settings = Settings(
        organization_id=org.id,
        company_name=company_name,
        email=admin_email,
        tax_pct=15,
        currency='SAR',
        language='ar',
    )
    db.session.add(settings)

    user = User(
        organization_id=org.id,
        username=uname,
        password_hash=password_hash,
        full_name=admin_name,
        email=admin_email,
        role='admin',
        is_active=True,
        language='ar',
    )
    db.session.add(user)
    db.session.commit()

    login_url = f'https://{slug}.liftcoreapp.com/login'
    return {
        'ok': True,
        'organization_id': org.id,
        'slug': slug,
        'username': uname,
        'login_url': login_url,
        'admin_user_id': user.id,
    }
