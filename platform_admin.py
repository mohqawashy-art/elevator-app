"""لوحة إدارة منصة LiftCore — منفصلة عن تطبيق العملاء."""
from __future__ import annotations

import os
from datetime import datetime

from flask import g, has_request_context, request

from models import OnboardingInvite, Organization, PlatformPayment, Settings, User, db
from plan_catalog import known_plan_keys


PLANS = known_plan_keys()

ADMIN_HOSTS = frozenset({
    'admin.liftcoreapp.com',
    'admin.localhost',
    'admin.127.0.0.1',
})


def operator_org_slugs() -> set[str]:
    raw = os.environ.get('LIFTCORE_OPERATOR_ORGS', 'default')
    return {s.strip().lower() for s in raw.split(',') if s.strip()} or {'default'}


def is_admin_host(host: str | None = None) -> bool:
    if host is None:
        if not has_request_context():
            return False
        host = request.host or ''
    host = (host or '').split(':')[0].lower().rstrip('.')
    if host in ADMIN_HOSTS:
        return True
    if host.startswith('admin.') and host.endswith('.liftcoreapp.com'):
        return True
    return False


def is_platform_operator(user) -> bool:
    """مشغّل المنصة = admin على مؤسسة default (أو LIFTCORE_OPERATOR_ORGS)."""
    if not user or getattr(user, 'role', None) != 'admin':
        return False
    allowed = operator_org_slugs()

    org = getattr(g, 'organization', None)
    if org and (getattr(org, 'slug', '') or '').lower() in allowed:
        return True

    oid = getattr(user, 'organization_id', None)
    if not oid:
        return False
    prev = getattr(g, '_resolving_default_org', False)
    g._resolving_default_org = True
    try:
        user_org = db.session.get(Organization, oid)
    finally:
        g._resolving_default_org = prev
    return bool(user_org and (user_org.slug or '').lower() in allowed)


def tenant_login_url(slug: str) -> str:
    slug = (slug or '').strip().lower()
    if slug in ('', 'default', 'app', 'liftcore'):
        return 'https://app.liftcoreapp.com/login'
    return f'https://{slug}.liftcoreapp.com/login'


def list_organizations(*, q: str = '', status: str = '', limit: int = 200) -> list[Organization]:
    query = Organization.query
    q = (q or '').strip()
    status = (status or '').strip().lower()
    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(
                Organization.slug.ilike(like),
                Organization.name.ilike(like),
                Organization.admin_email.ilike(like),
            )
        )
    if status:
        query = query.filter(Organization.status == status)
    return query.order_by(Organization.id.desc()).limit(limit).all()


def org_stats() -> dict:
    rows = (
        db.session.query(Organization.status, db.func.count(Organization.id))
        .group_by(Organization.status)
        .all()
    )
    by_status = {s or 'unknown': n for s, n in rows}
    invites_open = OnboardingInvite.query.filter(
        OnboardingInvite.status.in_(('pending', 'submitted'))
    ).count()
    leads_new = 0
    try:
        from models import SalesLead
        leads_new = SalesLead.query.filter_by(status='new').count()
    except Exception:
        leads_new = 0
    return {
        'total': sum(by_status.values()),
        'active': by_status.get('active', 0),
        'trial': by_status.get('trial', 0),
        'suspended': by_status.get('suspended', 0),
        'invites_open': invites_open,
        'leads_new': leads_new,
        'by_status': by_status,
    }


def get_org_detail(org_id: int) -> dict | None:
    org = db.session.get(Organization, org_id)
    if not org:
        return None
    prev = getattr(g, '_resolving_default_org', False)
    g._resolving_default_org = True
    try:
        settings = Settings.query.filter_by(organization_id=org.id).first()
        users = (
            User.query.filter_by(organization_id=org.id)
            .order_by(User.id.asc())
            .limit(50)
            .all()
        )
        invites = (
            OnboardingInvite.query.filter_by(organization_id=org.id)
            .order_by(OnboardingInvite.id.desc())
            .limit(20)
            .all()
        )
    finally:
        g._resolving_default_org = prev
    admin = next((u for u in users if u.role == 'admin'), users[0] if users else None)
    payments = (
        PlatformPayment.query.filter_by(organization_id=org.id)
        .order_by(PlatformPayment.id.desc())
        .limit(30)
        .all()
    )
    from platform_billing import effective_amount, refresh_billing_status
    from entitlements import addon_catalog_for_ui, list_org_addons, resolve_entitlements

    refresh_billing_status(org)
    entitlements = resolve_entitlements(org=org)
    return {
        'org': org,
        'settings': settings,
        'users': users,
        'admin': admin,
        'invites': invites,
        'payments': payments,
        'billing_amount': effective_amount(org),
        'login_url': tenant_login_url(org.slug),
        'plans': PLANS,
        'entitlements': entitlements,
        'org_addons': list_org_addons(org.id),
        'addon_catalog': addon_catalog_for_ui(),
    }


def update_org(
    org: Organization,
    *,
    plan: str | None = None,
    status: str | None = None,
    notes: str | None = None,
    name: str | None = None,
    admin_email: str | None = None,
) -> dict:
    if plan is not None:
        plan = plan.strip().lower()
        if plan not in PLANS:
            return {'ok': False, 'errors': ['باقة غير معروفة.']}
        org.plan = plan
    if status is not None:
        status = status.strip().lower()
        if status not in ('trial', 'active', 'suspended'):
            return {'ok': False, 'errors': ['حالة غير معروفة.']}
        org.status = status
        if status == 'suspended':
            org.suspended_at = datetime.utcnow()
        elif status in ('active', 'trial'):
            org.suspended_at = None
            if status == 'active':
                org.trial_ends_at = None
    if notes is not None:
        org.notes = notes.strip() or None
    if name is not None and name.strip():
        org.name = name.strip()[:200]
    if admin_email is not None:
        org.admin_email = admin_email.strip()[:100] or None
    db.session.commit()
    return {'ok': True, 'org': org}


def find_operator_user(login_id: str) -> User | None:
    """بحث مستخدم مشغّل بالاسم/البريد داخل مؤسسات المنصة فقط."""
    login_id = (login_id or '').strip()
    if not login_id:
        return None
    allowed = operator_org_slugs()
    orgs = Organization.query.filter(Organization.slug.in_(list(allowed))).all()
    if not orgs:
        return None
    org_ids = [o.id for o in orgs]
    return (
        User.query.filter(
            User.organization_id.in_(org_ids),
            User.is_active.is_(True),
            User.role == 'admin',
            db.or_(
                User.username == login_id,
                db.func.lower(User.email) == login_id.lower(),
            ),
        ).first()
    )


def recent_invites(limit: int = 30) -> list[OnboardingInvite]:
    return (
        OnboardingInvite.query
        .order_by(OnboardingInvite.id.desc())
        .limit(limit)
        .all()
    )


def invite_link(token: str) -> str:
    from operator_onboarding import invite_public_url

    return invite_public_url(token)
