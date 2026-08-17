"""عزل المستأجر — فلتر SQLAlchemy التلقائي + helpers يدوية."""

from __future__ import annotations

from flask import abort, g, has_request_context, request
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

from models import TenantMixin, db

PLATFORM_HOSTS = frozenset({'liftcoreapp.com', 'www.liftcoreapp.com'})
MARKETING_SLUGS = frozenset({'www', 'app', 'api', 'admin', 'staging', 'mail'})
ADMIN_HOSTS = frozenset({'admin.liftcoreapp.com'})
TENANT_EXEMPT_PATHS = frozenset({
    '/api/health',
    '/api/version',
    '/signup',
    '/api/signup',
    '/coming-soon',
    '/auth/handoff',
    '/api/webhooks/moyasar',
    '/api/webhooks/whatsapp',
})
TENANT_EXEMPT_PREFIXES = ('/onboard/',)


def init_tenant_scope(database):
    """سجّل فلتر tenant على جلسة SQLAlchemy — يُستدعى مرة بعد db.init_app."""

    @event.listens_for(database.session, 'do_orm_execute')
    def _add_tenant_filter(execute_state):
        if not execute_state.is_select:
            return
        if execute_state.execution_options.get('skip_tenant'):
            return
        if getattr(g, '_resolving_default_org', False):
            return
        oid = getattr(g, 'organization_id', None)
        if not oid:
            oid = effective_organization_id()
        if not oid:
            return
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda cls: cls.organization_id == oid,  # noqa: ARG005
                include_aliases=True,
            )
        )

    @event.listens_for(database.session, 'before_flush')
    def _assign_org_on_new_tenant_rows(session, _flush_context, _instances):
        """يملأ organization_id الناقص من سياق الطلب (أو default في الاختبارات)."""
        from flask import current_app

        oid = getattr(g, 'organization_id', None)
        if not oid and current_app.config.get('TESTING'):
            from models import Organization

            org = Organization.query.filter_by(slug='default').first()
            if not org:
                org = Organization.query.filter_by(slug='alpha').first()
            oid = org.id if org else None
        if not oid:
            return
        for obj in session.new:
            if isinstance(obj, TenantMixin) and obj.organization_id is None:
                obj.organization_id = oid


def effective_organization_id():
    """معرّف المؤسسة النشطة — subdomain أو default لـ app/localhost."""
    oid = getattr(g, 'organization_id', None)
    if oid:
        return oid
    if has_request_context():
        host = (request.host or '').split(':')[0].lower()
        if host not in ('app.liftcoreapp.com', '127.0.0.1', 'localhost'):
            return None
    cached = getattr(g, '_default_org_id', None)
    if cached is not None:
        return cached or None
    from models import Organization

    g._resolving_default_org = True
    try:
        org = Organization.query.filter_by(slug='default').first()
        g._default_org_id = org.id if org else 0
    finally:
        g._resolving_default_org = False
    return g._default_org_id or None


def current_organization_id():
    oid = effective_organization_id()
    if oid is None:
        abort(404, description='المؤسسة غير معروفة')
    return oid


def tenant_query(model):
    oid = effective_organization_id()
    if oid:
        return model.query.filter_by(organization_id=oid)
    return model.query


def tenant_get_or_404(model, record_id):
    return tenant_query(model).filter_by(id=record_id).first_or_404()


def assign_organization(obj):
    oid = effective_organization_id()
    if oid is None:
        abort(404, description='المؤسسة غير معروفة')
    obj.organization_id = oid
    return obj


def _bind_app_host_default_org():
    host = (request.host or '').split(':')[0].lower()
    if host != 'app.liftcoreapp.com':
        return False
    from models import Organization

    g._resolving_default_org = True
    try:
        org = Organization.query.filter_by(slug='default').first()
    finally:
        g._resolving_default_org = False
    if not org:
        return False
    g.organization = org
    g.organization_id = org.id
    return True


def _tenant_slug_from_host(host: str) -> str | None:
    host = (host or '').split(':')[0].lower().rstrip('.')
    if not host or host in PLATFORM_HOSTS:
        return None
    # IP / localhost — ليس subdomain tenant (مهم لـ e2e والتطوير المحلي)
    if host in ('localhost', '127.0.0.1', '::1') or host.replace('.', '').isdigit():
        return None
    parts = host.split('.')
    if len(parts) < 3:
        return None
    slug = parts[0]
    if slug in MARKETING_SLUGS:
        return None
    return slug


def _bind_local_default_org() -> bool:
    """localhost / 127.0.0.1 → مؤسسة default (e2e + تطوير)."""
    host = (request.host or '').split(':')[0].lower()
    if host not in ('127.0.0.1', 'localhost', '::1'):
        return False
    from models import Organization

    g._resolving_default_org = True
    try:
        org = Organization.query.filter_by(slug='default').first()
    finally:
        g._resolving_default_org = False
    if not org:
        return False
    g.organization = org
    g.organization_id = org.id
    return True


def _bind_admin_host() -> bool:
    """admin.liftcoreapp.com — لوحة المنصة بدون tenant."""
    host = (request.host or '').split(':')[0].lower().rstrip('.')
    if host not in ADMIN_HOSTS and not host.startswith('admin.'):
        return False
    if host.startswith('admin.') and host not in ADMIN_HOSTS:
        # admin.localhost للاختبارات
        if host not in ('admin.localhost', 'admin.127.0.0.1') and not host.endswith('.liftcoreapp.com'):
            return False
    g.organization = None
    g.organization_id = None
    g.platform_admin_host = True
    return True


def resolve_tenant():
    """يُستدعى before_request — يحدّد g.organization من الـ subdomain."""
    path = request.path or ''
    g.platform_admin_host = False
    if path in TENANT_EXEMPT_PATHS or any(path.startswith(p) for p in TENANT_EXEMPT_PREFIXES):
        g.organization = None
        g.organization_id = None
        return None

    if _bind_admin_host():
        return None

    slug = _tenant_slug_from_host(request.host or '')
    if not slug:
        if _bind_app_host_default_org() or _bind_local_default_org():
            return None
        g.organization = None
        g.organization_id = None
        return None

    from models import Organization

    g._resolving_default_org = True
    try:
        org = Organization.query.filter_by(slug=slug).first()
    finally:
        g._resolving_default_org = False
    if not org or org.status == 'suspended':
        abort(404)
    from demo_provisioning import organization_access_allowed

    if not organization_access_allowed(org):
        abort(404)
    g.organization = org
    g.organization_id = org.id
    return None
