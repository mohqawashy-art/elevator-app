"""لوحة إدارة منصة LiftCore — منفصلة عن تطبيق العملاء."""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta

from flask import current_app, g, has_app_context, has_request_context, request
from sqlalchemy import text

from models import OnboardingInvite, Organization, PlatformPayment, Settings, Technician, User, db
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


ONLINE_MINUTES = 15


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
    users_total = 0
    users_online = 0
    with _all_tenants():
        users_total = User.query.count()
        since = datetime.utcnow() - timedelta(minutes=ONLINE_MINUTES)
        users_online = User.query.filter(
            User.is_active.is_(True),
            User.last_login.isnot(None),
            User.last_login >= since,
        ).count()
    return {
        'total': sum(by_status.values()),
        'active': by_status.get('active', 0),
        'trial': by_status.get('trial', 0),
        'suspended': by_status.get('suspended', 0),
        'invites_open': invites_open,
        'leads_new': leads_new,
        'by_status': by_status,
        'users_total': users_total,
        'users_online': users_online,
    }


@contextmanager
def _all_tenants():
    """تجاوز عزل المستأجر لاستعلامات لوحة المنصة."""
    if not has_app_context():
        yield
        return
    prev = getattr(g, '_resolving_default_org', False)
    g._resolving_default_org = True
    try:
        yield
    finally:
        g._resolving_default_org = prev


def _fmt_mb(mb: int | None) -> str:
    if mb is None:
        return '—'
    if mb >= 1024:
        return f'{mb / 1024:.1f} GB'
    return f'{int(mb)} MB'


def _read_meminfo() -> dict:
    path = '/proc/meminfo'
    total = avail = None
    if os.path.isfile(path):
        data = {}
        with open(path, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2:
                    data[parts[0].rstrip(':')] = int(parts[1])
        if 'MemTotal' in data:
            total = data['MemTotal'] // 1024
        if 'MemAvailable' in data:
            avail = data['MemAvailable'] // 1024
    return {'total_mb': total, 'available_mb': avail}


def _loadavg() -> tuple[float, float, float] | None:
    try:
        return os.getloadavg()
    except (OSError, AttributeError):
        return None


def _uptime_seconds() -> float | None:
    path = '/proc/uptime'
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            return float(fh.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _fmt_uptime(seconds: float | None) -> str:
    if not seconds:
        return '—'
    sec = int(seconds)
    days, rem = divmod(sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f'{days}ي {hours}س'
    if hours:
        return f'{hours}س {minutes}د'
    return f'{minutes}د'


def _systemd_is_active(name: str) -> str | None:
    try:
        proc = subprocess.run(
            ['systemctl', 'is-active', name],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        val = (proc.stdout or '').strip()
        return val or None
    except (OSError, subprocess.SubprocessError):
        return None


def server_status() -> dict:
    """حالة جهاز جوجل الذي يشغّل المنصة الآن."""
    from liftcore_database import database_backend, database_info

    mem = _read_meminfo()
    total_mb = mem.get('total_mb')
    avail_mb = mem.get('available_mb')
    used_pct = None
    if total_mb and avail_mb is not None and total_mb > 0:
        used_pct = round(100 * (total_mb - avail_mb) / total_mb)

    disk = {'total_mb': None, 'free_mb': None, 'used_pct': None}
    try:
        root = os.path.expanduser('~') or '/'
        if has_app_context():
            root = current_app.root_path or root
        usage = shutil.disk_usage(root)
        disk['total_mb'] = round(usage.total / (1024 * 1024))
        disk['free_mb'] = round(usage.free / (1024 * 1024))
        if usage.total:
            disk['used_pct'] = round(100 * (1 - usage.free / usage.total))
    except OSError:
        pass

    cpu = os.cpu_count() or 0
    load = _loadavg()
    load1 = load[0] if load else None

    db_ok = False
    db_backend = 'unknown'
    db_name = ''
    try:
        db.session.execute(text('SELECT 1'))
        db_ok = True
    except Exception:
        db_ok = False
        try:
            db.session.rollback()
        except Exception:
            pass
    if has_app_context():
        db_backend = database_backend(current_app.config.get('SQLALCHEMY_DATABASE_URI'))
        info = database_info(current_app)
        db_name = info.get('database') or os.path.basename(info.get('path') or '') or ''

    warn = []
    if not db_ok:
        warn.append('قاعدة البيانات لا ترد')
    if avail_mb is not None and avail_mb < 400:
        warn.append('الذاكرة منخفضة')
    if disk.get('free_mb') is not None and disk['free_mb'] < 1024:
        warn.append('مساحة القرص منخفضة')
    if load1 is not None and cpu and load1 > cpu * 1.2:
        warn.append('حمل المعالج مرتفع')

    ok = db_ok and not warn
    liftcore_svc = _systemd_is_active('liftcore')
    jama_svc = _systemd_is_active('liftcore-jama')

    return {
        'ok': ok,
        'level': 'ok' if ok else ('bad' if not db_ok else 'warn'),
        'label': 'يعمل' if ok else ('متوقف' if not db_ok else 'تحذير'),
        'hostname': socket.gethostname(),
        'cpu_count': cpu,
        'load1': round(load1, 2) if load1 is not None else None,
        'memory_total': _fmt_mb(total_mb),
        'memory_available': _fmt_mb(avail_mb),
        'memory_used_pct': used_pct,
        'disk_total': _fmt_mb(disk.get('total_mb')),
        'disk_free': _fmt_mb(disk.get('free_mb')),
        'disk_used_pct': disk.get('used_pct'),
        'uptime': _fmt_uptime(_uptime_seconds()),
        'db_ok': db_ok,
        'db_backend': db_backend,
        'db_name': db_name,
        'version': os.environ.get('LIFTCORE_VERSION') or (
            current_app.config.get('LIFTCORE_VERSION') if has_app_context() else ''
        ) or '—',
        'service_liftcore': liftcore_svc,
        'service_jama': jama_svc,
        'warnings': warn,
        'checked_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
    }


def _empty_ops(org: Organization) -> dict:
    suspended = (org.status or '') == 'suspended'
    return {
        'users_total': 0,
        'users_active': 0,
        'users_online': 0,
        'technicians': 0,
        'last_login': None,
        'last_login_label': '—',
        'runtime_key': 'stopped' if suspended else 'running',
        'runtime_label': 'موقوف' if suspended else 'يعمل',
    }


def tenant_ops_by_id(orgs: list[Organization]) -> dict[str, dict]:
    """تشغيل كل مستأجر + المستخدمون على هذا السيرفر."""
    out = {str(o.id): _empty_ops(o) for o in orgs}
    if not orgs:
        return out
    ids = [o.id for o in orgs]
    since = datetime.utcnow() - timedelta(minutes=ONLINE_MINUTES)
    with _all_tenants():
        user_rows = (
            db.session.query(
                User.organization_id,
                db.func.count(User.id),
                db.func.sum(db.case((User.is_active.is_(True), 1), else_=0)),
                db.func.sum(db.case(
                    (
                        db.and_(
                            User.is_active.is_(True),
                            User.last_login.isnot(None),
                            User.last_login >= since,
                        ),
                        1,
                    ),
                    else_=0,
                )),
                db.func.max(User.last_login),
            )
            .filter(User.organization_id.in_(ids))
            .group_by(User.organization_id)
            .all()
        )
        tech_rows = (
            db.session.query(Technician.organization_id, db.func.count(Technician.id))
            .filter(Technician.organization_id.in_(ids))
            .group_by(Technician.organization_id)
            .all()
        )
    for oid, total, active, online, last_login in user_rows:
        key = str(oid)
        if key not in out:
            continue
        out[key]['users_total'] = int(total or 0)
        out[key]['users_active'] = int(active or 0)
        out[key]['users_online'] = int(online or 0)
        if last_login:
            out[key]['last_login'] = last_login
            out[key]['last_login_label'] = last_login.strftime('%Y-%m-%d %H:%M')
    for oid, n in tech_rows:
        key = str(oid)
        if key in out:
            out[key]['technicians'] = int(n or 0)
    return out


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
    from entitlements import addon_catalog_for_ui, feature_catalog_for_ui, list_org_addons, resolve_entitlements
    from plan_catalog import plan_definition

    refresh_billing_status(org)
    entitlements = resolve_entitlements(org=org)
    plan_options = []
    for key in PLANS:
        spec = plan_definition(key)
        plan_options.append({
            'key': key,
            'label': spec.get('label_ar') or spec.get('label') or key,
        })
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
        'plan_options': plan_options,
        'entitlements': entitlements,
        'org_addons': list_org_addons(org.id),
        'addon_catalog': addon_catalog_for_ui(),
        'feature_catalog': feature_catalog_for_ui(),
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
