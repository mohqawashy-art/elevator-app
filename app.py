"""
LiftCore — Flask Application
app.py
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, g, send_from_directory, abort, make_response, has_app_context
from models import db, Customer, Elevator, Contract, ContractElevator, Technician, TechnicianDocument
from models import MaintenanceVisit, Fault, Revenue, Expense, Invoice, Account
from models import JournalEntry, JournalLine
from models import MaintenanceTeam
from models import VisitTechnician, FaultTechnician, WhatsAppInbox
from models import InventoryItem, StockMovement, PartsBilling, Settings, User, Signatory
from models import PurchaseOrder, PurchaseOrderLine
from models import ElevatorEstimate, ElevatorEstimateLine
from elevator_estimate_calc import (
    calculate_lines, summarize_lines, MACHINE_TYPES, ELEV_TYPES,
    ESTIMATE_STATUSES, DEFAULT_VAT_PCT, DEFAULT_MARGIN_PCT,
)
from calendar import monthrange
from datetime import datetime, date, timedelta
from sqlalchemy import or_, and_, text, inspect
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
import time
import uuid
import shutil
import secrets
import string


def _load_env_file():
    """تحميل إعدادات المنصة — مرة واحدة لكل العملاء (LiftCore + جما + أي subdomain)."""
    configured_path = (os.environ.get('LIFTCORE_ENV_FILE') or '').strip()
    if configured_path:
        # بيئات staging تستخدم ملفاً واحداً معزولاً ولا تقرأ أسرار الإنتاج.
        paths = [configured_path]
    else:
        paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
            '/home/info/liftcore/.env',
            '/etc/liftcore/platform.env',
        ]
    for path in paths:
        if not os.path.isfile(path):
            continue
        # platform.env دائماً يغلب (أسرار الإنتاج)
        override = bool(configured_path) or path.rstrip('/').endswith('platform.env')
        try:
            with open(path, encoding='utf-8') as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, val = line.partition('=')
                    key = key.strip().lstrip('\ufeff')
                    val = val.strip().strip('"').strip("'")
                    if not key:
                        continue
                    if override or key not in os.environ:
                        os.environ[key] = val
        except OSError as exc:
            print(f'Warning: could not read {path}: {exc}')


_load_env_file()


def resolve_google_maps_api_key(settings=None):
    """مفتاح Google Maps على مستوى المنصة — من متغير البيئة فقط."""
    key = os.environ.get('GOOGLE_MAPS_API_KEY', '').strip()
    if key:
        return key
    if settings and (getattr(settings, 'google_maps_api_key', None) or '').strip():
        return settings.google_maps_api_key.strip()
    return ''


def google_maps_key_source(settings=None):
    """مصدر المفتاح (للتشخيص — بدون كشف القيمة)."""
    if os.environ.get('GOOGLE_MAPS_API_KEY', '').strip():
        return 'platform'
    if settings and (getattr(settings, 'google_maps_api_key', None) or '').strip():
        return 'settings'
    return 'none'


app = Flask(__name__)


def _resolve_database_uri():
    """استخدم liftcore.db — إن وُجد أكثر من نسخة، اختر الأكبر (البيانات الفعلية)."""
    os.makedirs(app.instance_path, exist_ok=True)
    instance_db = os.path.join(app.instance_path, 'liftcore.db')
    root_db = os.path.join(app.root_path, 'liftcore.db')
    candidates = []
    for path in (instance_db, root_db):
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            candidates.append(path)
    if not candidates:
        return 'sqlite:///' + instance_db.replace('\\', '/')
    best = max(candidates, key=os.path.getsize)
    return 'sqlite:///' + best.replace('\\', '/')


# =============================================
# الإعدادات
# =============================================
def _resolve_secret_key() -> str:
    """إنتاج (LIFTCORE_HTTPS): SECRET_KEY إلزامي بلا fallback. تطوير: مفتاح محلي فقط."""
    key = (os.environ.get('SECRET_KEY') or '').strip()
    if key:
        return key
    https_on = os.environ.get('LIFTCORE_HTTPS', '').strip().lower() in ('1', 'true', 'yes')
    if https_on:
        raise RuntimeError(
            'LiftCore: SECRET_KEY مطلوب في الإنتاج (LIFTCORE_HTTPS=1). '
            'عيّن متغير البيئة قبل التشغيل — لا يوجد fallback.'
        )
    return 'liftcore-secret-2025'


app.config['SECRET_KEY'] = _resolve_secret_key()
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or _resolve_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
if os.environ.get('LIFTCORE_HTTPS', '').strip().lower() in ('1', 'true', 'yes'):
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['PREFERRED_URL_SCHEME'] = 'https'

from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

from liftcore_security import validate_production_config  # noqa: E402
from liftcore_database import apply_database_config, database_backend, database_info, is_sqlite  # noqa: E402

apply_database_config(app)
validate_production_config(app)

from liftcore_monitoring import init_error_monitoring, monitoring_status  # noqa: E402

init_error_monitoring(app)


@app.after_request
def _security_headers(response):
    if os.environ.get('LIFTCORE_HTTPS', '').strip().lower() not in ('1', 'true', 'yes'):
        return response
    proto = (request.headers.get('X-Forwarded-Proto') or request.scheme or '').lower()
    if proto == 'https' or request.is_secure:
        response.headers.setdefault(
            'Strict-Transport-Security', 'max-age=63072000; includeSubDomains'
        )
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    return response


@app.after_request
def _strip_obsolete_contract_value_guard(response):
    """يشيل تحقق «قيمة العقد > 0» القديم من HTML حتى لو بقيت نسخة قديمة في الكاش/القرص."""
    try:
        if request.endpoint not in ('contracts',):
            return response
        ctype = (response.headers.get('Content-Type') or '').lower()
        if 'html' not in ctype:
            return response
        raw = response.get_data(as_text=True)
        marker = 'قيمة العقد يجب أن تكون أكبر من صفر'
        if marker not in raw:
            return response
        import re
        cleaned, n = re.subn(
            r"var\s+contractVal\s*=\s*parseFloat\([^;]*;\s*"
            r"if\s*\(\s*!contractVal\s*\|\|\s*contractVal\s*<=\s*0\s*\)\s*\{\s*"
            r"alert\(\s*['\"]قيمة العقد يجب أن تكون أكبر من صفر['\"]\s*\)\s*;\s*"
            r"return\s*;\s*\}\s*",
            "\n",
            raw,
            flags=re.M,
        )
        if n:
            response.set_data(cleaned)
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['X-LC-Contract-Zero'] = f'stripped:{n}'
    except Exception:
        app.logger.exception('strip obsolete contract value guard failed')
    return response

db.init_app(app)

from tenant_scope import (  # noqa: E402
    assign_organization,
    init_tenant_scope,
    resolve_tenant,
    tenant_get_or_404,
    tenant_query,
)

init_tenant_scope(db)

# موديول تركيب المصاعد (جداول منفصلة)
import installation.models  # noqa: F401, E402
from installation.config import install_module_enabled

from flask_migrate import Migrate  # noqa: E402

migrate = Migrate(app, db)

PUBLIC_ENDPOINTS = frozenset({
    'login', 'logout', 'static', 'index', 'api_version', 'api_health',
    'api_debug_contract_zero',
    'signup', 'api_signup', 'onboard_form', 'auth_handoff',
    'coming_soon', 'pricing', 'product_landing', 'demo_request',
    'robots_txt', 'sitemap_xml', 'google_site_verification',
    'ads_landing', 'ads_thanks', 'seo_elevator_management',
    'field_login', 'field_logout', 'field_manifest', 'field_service_worker',
    'web_manifest', 'admin_service_worker',
    'moyasar_webhook',
    'whatsapp_webhook',
})
PUBLIC_PATH_PREFIXES = ('/static',)
STATIC_UPLOADS_PREFIX = '/static/uploads'


def _is_public_static_path(path: str) -> bool:
    """أصول ثابتة عامة — uploads مستثناة (تُحمى في serve_upload_file)."""
    for prefix in PUBLIC_PATH_PREFIXES:
        if path.startswith(prefix):
            if path.startswith(STATIC_UPLOADS_PREFIX):
                return False
            return True
    return False


def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    try:
        user = db.session.get(User, uid)
    except Exception:
        db.session.rollback()
        return None
    if not user or not user.is_active:
        return None
    # سياسة الترخيص: جلسة مكتب واحدة لكل مستخدم — دخول جديد يُنهي الجلسات القديمة
    cookie_ver = session.get('session_version')
    db_ver = int(getattr(user, 'session_version', None) or 0)
    try:
        cookie_ver_i = int(cookie_ver) if cookie_ver is not None else None
    except (TypeError, ValueError):
        cookie_ver_i = None
    if cookie_ver_i is None or cookie_ver_i != db_ver:
        session.clear()
        session['login_notice'] = (
            'تم إنهاء جلستك لأن الحساب سُجّل دخوله من جهاز أو متصفح آخر. '
            'كل مستخدم مسموح له بجلسة واحدة فقط حسب سياسة الترخيص.'
        )
        return None
    # انتهاء تجربة / إيقاف المؤسسة — يُنهي الجلسة فوراً
    if user.organization_id and not getattr(g, 'platform_admin_host', False):
        try:
            from demo_provisioning import organization_access_allowed
            from models import Organization as _Org

            org = db.session.get(_Org, user.organization_id)
            if org and not organization_access_allowed(org):
                session.clear()
                session['login_notice'] = 'انتهت صلاحية الحساب التجريبي أو أُوقفت المؤسسة.'
                return None
        except Exception:
            db.session.rollback()
    return user


def stamp_created_by(row) -> None:
    """يثبّت من أنشأ السجل مرة واحدة (لا يُستبدل عند التعديل)."""
    if getattr(row, 'created_by_user_id', None) or getattr(row, 'created_by_name', None):
        return
    user = current_user()
    if not user:
        return
    if hasattr(row, 'created_by_user_id'):
        row.created_by_user_id = user.id
    if hasattr(row, 'created_by_name'):
        name = (getattr(user, 'full_name', None) or getattr(user, 'username', None) or '').strip()
        row.created_by_name = (name or f'#{user.id}')[:100]


def created_by_display(row) -> str:
    name = (getattr(row, 'created_by_name', None) or '').strip()
    if name:
        return name
    uid = getattr(row, 'created_by_user_id', None)
    if not uid:
        return ''
    try:
        user = db.session.get(User, uid)
    except Exception:
        return ''
    if not user:
        return ''
    return (user.full_name or user.username or f'#{uid}').strip()

def bump_user_session_version(user, *, bind_current_session: bool = False) -> int:
    """يزيد رقم جلسة المستخدم (يُبطل الكوكيز القديمة)."""
    ver = int(getattr(user, 'session_version', None) or 0) + 1
    user.session_version = ver
    if bind_current_session and session.get('user_id') == user.id:
        session['session_version'] = ver
    return ver


def require_login():
    return current_user()


def require_admin():
    user = current_user()
    if not user or user.role != 'admin':
        return None
    return user


ADMIN_DELETE_PASSWORD_FIELD = 'admin_password'


def _admin_delete_password_from_request():
    data = request.get_json(silent=True) if request.is_json else None
    if not isinstance(data, dict):
        data = {}
    return (
        (request.form.get(ADMIN_DELETE_PASSWORD_FIELD) or '')
        or (data.get(ADMIN_DELETE_PASSWORD_FIELD) or '')
    ).strip()


def _admin_delete_wants_json(*, json_response=False):
    if json_response:
        return True
    if request.is_json:
        return True
    if request.headers.get('X-LC-Admin-Delete') == '1':
        return True
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    return False


def enforce_admin_password(
    *,
    json_response=False,
    action='admin_action_confirmed',
    admin_only_ar='هذا الإجراء متاح للمسؤول فقط.',
    admin_only_en='This action is admin-only.',
    bad_password_ar='كلمة المرور غير صحيحة — لم يتم التنفيذ.',
    bad_password_en='Incorrect password — action cancelled.',
    details=None,
):
    """يتطلب دور admin + كلمة مرور المستخدم الحالي لتأكيد إجراء حسّاس."""
    as_json = _admin_delete_wants_json(json_response=json_response)
    user = current_user()
    if not user:
        if as_json:
            from liftcore_api_i18n import api_json_error
            return api_json_error('login_required', 401)
        return redirect(url_for('login'))
    if user.role != 'admin':
        if as_json:
            from liftcore_api_i18n import api_json_error
            return api_json_error(
                'admin_required', 403,
                message_ar=admin_only_ar, message_en=admin_only_en,
            )
        flash(admin_only_ar, 'error')
        abort(403)
    pwd = _admin_delete_password_from_request()
    if not pwd or not verify_password(user.password_hash, pwd):
        if as_json:
            from liftcore_api_i18n import api_json_error
            return api_json_error(
                'invalid_password', 403,
                message_ar=bad_password_ar, message_en=bad_password_en,
            )
        flash(bad_password_ar, 'error')
        return redirect(request.referrer or url_for('dashboard'))
    from audit_log import log_audit
    log_audit(
        action,
        user=user,
        details={'path': request.path, 'endpoint': request.endpoint, **(details or {})},
    )
    return None


def enforce_admin_delete(*, json_response=False):
    """يتطلب دور admin + كلمة مرور المستخدم الحالي لتأكيد الحذف."""
    return enforce_admin_password(
        json_response=json_response,
        action='admin_delete_confirmed',
        admin_only_ar='الحذف متاح للمسؤول فقط.',
        admin_only_en='Delete is admin-only.',
        bad_password_ar='كلمة المرور غير صحيحة — لم يتم الحذف.',
        bad_password_en='Incorrect password — delete cancelled.',
    )


def session_is_locked():
    return bool(session.get('session_locked'))


def set_session_locked(locked=True):
    if locked:
        session['session_locked'] = True
    else:
        session.pop('session_locked', None)
    session.modified = True


def _must_change_password_response(user):
    """إجبار تغيير كلمة المرور قبل أي عمل آخر."""
    if not getattr(user, 'must_change_password', False):
        return None
    from liftcore_rbac import PASSWORD_CHANGE_ALLOWED_ENDPOINTS

    ep = request.endpoint or ''
    if ep in PASSWORD_CHANGE_ALLOWED_ENDPOINTS:
        return None
    path = request.path or ''
    if path.startswith('/static/'):
        return None
    if path.startswith('/api/'):
        from liftcore_api_i18n import api_json_error
        return api_json_error('password_change_required', 403)
    session['settings_notice'] = 'يجب تغيير كلمة المرور قبل متابعة العمل.'
    return redirect(url_for('settings', tab='account', force_password=1))


def _session_lock_response():
    """منع الوصول للواجهات البرمجية أثناء قفل الجلسة (ما عدا فتح/قفل الجلسة)."""
    if not session_is_locked():
        return None
    if not current_user():
        return None
    path = request.path or ''
    if path.startswith('/static/'):
        return None
    if request.endpoint in ('api_session_lock', 'api_session_unlock', 'api_verify_signature'):
        return None
    if path.startswith('/api/'):
        from liftcore_api_i18n import api_json_error
        return api_json_error('session_locked', 423)
    return None


def _resolve_field_technician_id():
    """جلسة الفني أو معاينة المشرف (?tech_id=)."""
    from field_auth import field_session_technician_id

    tid = field_session_technician_id()
    if tid:
        return tid
    user = current_user()
    if user and user.role in ('admin', 'manager'):
        preview = request.args.get('tech_id', type=int)
        if preview:
            return preview
    return None


def _field_tech_api_allowed(path: str, method: str) -> bool:
    """واجهات يستخدمها محضر الفني من الجوال (خارج /field و /api/field)."""
    if method != 'POST':
        return False
    if path == '/api/signatures/verify':
        return True
    if path.endswith('/report'):
        if path.startswith('/api/maintenance-visits/'):
            return True
        if path.startswith('/api/faults/'):
            return True
    return False


def _field_portal_context(tech_id: int) -> dict:
    from field_auth import technician_portal_kind, technician_portal_label
    from operations import FAULT_OPEN
    from technician_assignments import faults_for_technician_filter

    tech = tenant_get_or_404(Technician, tech_id)
    kind = technician_portal_kind(tech)
    has_faults = (
        tenant_query(Fault).filter(
            faults_for_technician_filter(tech_id),
            Fault.status.in_(FAULT_OPEN),
        ).count()
        > 0
    )
    show_faults = kind in ('faults', 'both') or has_faults
    show_visits = kind in ('maintenance', 'both')
    if show_faults and not show_visits:
        portal_label = technician_portal_label('faults')
    elif show_visits and not show_faults:
        portal_label = technician_portal_label('maintenance')
    else:
        portal_label = technician_portal_label(kind)
    return {
        'field_tech': tech,
        'tech_id': tech.id,
        'portal_kind': kind,
        'portal_label': portal_label,
        'show_visits_nav': show_visits,
        'show_faults_nav': show_faults,
        'has_assigned_faults': has_faults,
    }


_permissions_schema_bootstrapped = False


def _bootstrap_permissions_schema_once():
    global _permissions_schema_bootstrapped
    if _permissions_schema_bootstrapped:
        return
    try:
        from liftcore_permissions import ensure_permissions_schema
        ensure_permissions_schema(db.session, db.engine)
        _permissions_schema_bootstrapped = True
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('permissions schema bootstrap: %s', exc)


@app.before_request
def _resolve_tenant_before_auth():
    return resolve_tenant()


@app.before_request
def enforce_auth():
    _bootstrap_permissions_schema_once()
    from field_auth import field_session_technician_id

    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    path = request.path or ''
    if _is_public_static_path(path):
        return None
    if path.startswith(STATIC_UPLOADS_PREFIX):
        return None

    field_tid = field_session_technician_id()

    if path.startswith('/field') or path.startswith('/api/field'):
        tech_id = _resolve_field_technician_id()
        if tech_id:
            g.field_tech_id = tech_id
            from field_auth import bind_field_technician_tenant
            bind_field_technician_tenant(tech_id)
            return None
        if path.startswith('/api/field'):
            return jsonify({'error': 'يجب تسجيل دخول الفني'}), 401
        return redirect(url_for('field_login', next=request.path))

    if field_tid and _field_tech_api_allowed(path, request.method):
        g.field_tech_id = field_tid
        from field_auth import bind_field_technician_tenant
        bind_field_technician_tenant(field_tid)
        return None

    user = current_user()
    if user:
        g.user = user
        oid = getattr(g, 'organization_id', None)
        user_oid = getattr(user, 'organization_id', None)
        # لوحة المنصة (admin.*) بدون tenant — لا تفرض تطابق organization_id
        if oid and user_oid is not None and user_oid != oid and not getattr(g, 'platform_admin_host', False):
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'غير مصرح لهذا الحساب'}), 403
            abort(403)
        lock_resp = _session_lock_response()
        if lock_resp:
            return lock_resp
        pwd_resp = _must_change_password_response(user)
        if pwd_resp:
            return pwd_resp
        # مسارات لوحة المنصة — تخطّي RBAC الخاص بتطبيق العميل
        if getattr(g, 'platform_admin_host', False) and (path.startswith('/platform') or path.startswith('/operator')):
            from liftcore_security import validate_csrf
            if not app.config.get('TESTING'):
                validate_csrf(
                    method=request.method,
                    endpoint=request.endpoint,
                    path=request.path or '',
                )
            return None
        from liftcore_rbac import check_rbac
        lang = resolve_user_language(user)
        s = None
        try:
            s = tenant_query(Settings).first()
        except Exception:
            db.session.rollback()
        rbac_resp = check_rbac(
            user,
            method=request.method,
            endpoint=request.endpoint,
            path=request.path or '',
            lang=lang,
            settings=s,
        )
        if rbac_resp:
            return rbac_resp
        from liftcore_security import validate_csrf
        if not app.config.get('TESTING'):
            validate_csrf(
                method=request.method,
                endpoint=request.endpoint,
                path=request.path or '',
            )
        return None

    if field_tid:
        if path.startswith('/api/'):
            return jsonify({'error': 'غير مصرح لهذا الحساب'}), 403
        return redirect(url_for('field_login', next=request.path))

    session.clear()
    if request.path.startswith('/api/'):
        return jsonify({'error': 'يجب تسجيل الدخول'}), 401
    return redirect(url_for('login', next=request.path))

APP_VERSION = os.environ.get('LIFTCORE_VERSION', '4a0a9d8-auth')


def western_digits(value):
    if value is None:
        return ''
    text = str(value)
    for i, ar in enumerate('٠١٢٣٤٥٦٧٨٩'):
        text = text.replace(ar, str(i))
    for i, fa in enumerate('۰۱۲۳۴۵۶۷۸۹'):
        text = text.replace(fa, str(i))
    return text


@app.template_filter('en_num')
def en_num_filter(value):
    if value is None or value == '':
        return ''
    try:
        n = float(value)
        if n == int(n):
            return f'{int(n):,}'
        return f'{n:,.2f}'
    except (TypeError, ValueError):
        return western_digits(value)


@app.template_filter('en_date')
def en_date_filter(value):
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    text = western_digits(str(value))
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return f'{m.group(3)}/{m.group(2)}/{m.group(1)}'
    return text


@app.template_filter('en_datetime')
def en_datetime_filter(value):
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y %H:%M')
    text = western_digits(str(value))
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})', text)
    if m:
        return f'{m.group(3)}/{m.group(2)}/{m.group(1)} {m.group(4)}:{m.group(5)}'
    return en_date_filter(text)


def get_app_settings():
    try:
        s = tenant_query(Settings).first()
    except Exception:
        db.session.rollback()
        s = None
    if not s:
        from tenant_scope import effective_organization_id

        if not effective_organization_id():
            return None
        s = Settings()
        assign_organization(s)
        db.session.add(s)
        db.session.commit()
    return s


def idle_screensaver_enabled(settings=None):
    s = settings if settings is not None else get_app_settings()
    val = getattr(s, 'idle_screensaver_enabled', None)
    if val is None:
        return True
    return bool(val)


def idle_screensaver_seconds(settings=None):
    s = settings if settings is not None else get_app_settings()
    try:
        sec = int(getattr(s, 'idle_screensaver_seconds', None) or 60)
    except (TypeError, ValueError):
        sec = 60
    return max(15, min(sec, 3600))


def azkar_ticker_enabled(settings=None):
    s = settings if settings is not None else get_app_settings()
    val = getattr(s, 'azkar_ticker_enabled', None)
    if val is None:
        return True
    return bool(val)


def brand_logo_url(settings=None):
    """شعار شركة العميل (ليس شعار منتج LiftCore)."""
    s = settings or get_app_settings()
    if s and s.logo_path:
        rel = s.logo_path.replace('\\', '/').lstrip('/')
        full = os.path.join(app.static_folder, rel.replace('/', os.sep))
        # دائماً نعيد مسار شعار العميل — لا نستبدله بشعار LiftCore
        url = url_for('static', filename=rel)
        if os.path.isfile(full):
            url += '?v=' + str(int(os.path.getmtime(full)))
        else:
            url += '?v=missing'
        return url
    # بدون شعار مرفوع: ملف افتراضي عام فقط
    if os.path.isfile(os.path.join(app.static_folder, 'logo.png')):
        return url_for('static', filename='logo.png')
    return url_for('static', filename='images/liftcore-brand-logo.png')


def liftcore_header_logo_url(settings=None):
    """شعار LiftCore في الهيدر — مع بدائل إذا ملف الهيدر غير موجود."""
    candidates = (
        LIFTCORE_PRODUCT_LOGO,
        'images/liftcore-brand-logo.png',
        'logo.png',
    )
    for name in candidates:
        if os.path.isfile(os.path.join(app.static_folder, name.replace('/', os.sep))):
            return url_for('static', filename=name)
    return brand_logo_url(settings)


ROLE_LABELS = {
    'admin': 'مدير النظام',
    'manager': 'مدير عمليات',
    'viewer': 'عرض فقط',
    'custom': 'مخصص',
}

ROLE_LABELS_EN = {
    'admin': 'System Admin',
    'manager': 'Operations Manager',
    'viewer': 'View Only',
    'custom': 'Custom',
}

USER_THEMES = frozenset({'dark', 'light', 'report', 'premium'})

USER_THEME_OPTIONS = (
    {'id': 'dark', 'label_ar': 'داكن', 'hint_ar': 'الوضع الافتراضي', 'swatch': 'swatch-dark'},
    {'id': 'light', 'label_ar': 'فاتح', 'hint_ar': 'مناسب للإضاءة القوية', 'swatch': 'swatch-light'},
    {'id': 'report', 'label_ar': 'احترافي', 'hint_ar': 'كحلي وذهبي — مثل التقارير', 'swatch': 'swatch-report'},
    {'id': 'premium', 'label_ar': 'LiftCore', 'hint_ar': 'أسود وذهبي — مثل شاشة الدخول', 'swatch': 'swatch-premium'},
)


def normalize_user_theme(value):
    theme = (value or 'dark').strip()
    return theme if theme in USER_THEMES else 'dark'


def resolve_user_language(user=None):
    lang = session.get('lang')
    if lang in ('ar', 'en'):
        return lang
    if user and getattr(user, 'language', None) in ('ar', 'en'):
        return user.language
    try:
        s = tenant_query(Settings).first()
        if s and getattr(s, 'language', None) in ('ar', 'en'):
            return s.language
    except Exception:
        db.session.rollback()
    return 'ar'

LIFTCORE_PRODUCT_LOGO = 'images/liftcore-header-logo.png'


def user_initials(user):
    if not user:
        return '?'
    name = (user.full_name or user.username or '?').strip()
    return name[0] if name else '?'


def user_avatar_url(user):
    if user and user.photo_path:
        return url_for('static', filename=user.photo_path.replace('\\', '/'))
    return None


@app.template_filter('dmY')
def format_date_dmy(value):
    if not value:
        return '—'
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    s = str(value)[:10]
    parts = s.split('-')
    if len(parts) == 3 and len(parts[0]) == 4:
        return f'{parts[2]}/{parts[1]}/{parts[0]}'
    return str(value)


def _platform_support_context(*, user=None, settings=None, lang: str = 'ar') -> dict:
    """روابط دعم LiftCore للمنصة (واتساب + بريد) — قابلة للضبط عبر البيئة."""
    from urllib.parse import quote

    from operations import whatsapp_url

    email = (os.environ.get('LIFTCORE_SUPPORT_EMAIL') or 'info@liftcoreapp.com').strip()
    if 'LIFTCORE_SUPPORT_WHATSAPP' in os.environ:
        phone = (os.environ.get('LIFTCORE_SUPPORT_WHATSAPP') or '').strip()
    else:
        phone = '0566299626'
    brand = (getattr(settings, 'company_name', None) or 'LiftCore') if settings else 'LiftCore'
    who = ''
    if user:
        who = (getattr(user, 'full_name', None) or getattr(user, 'username', None) or '').strip()
    if lang == 'en':
        msg = f'Hello, I need LiftCore support. Company: {brand}.'
        if who:
            msg += f' User: {who}.'
        subject = f'LiftCore support — {brand}'
    else:
        msg = f'مرحباً، أحتاج دعم LiftCore. المنشأة: {brand}.'
        if who:
            msg += f' المستخدم: {who}.'
        subject = f'دعم LiftCore — {brand}'
    wa = whatsapp_url(phone, msg) if phone else ''
    mail = ''
    if email and '@' in email:
        mail = f'mailto:{email}?subject={quote(subject)}&body={quote(msg)}'
    return {
        'support_email': email if mail else '',
        'support_email_url': mail,
        'support_whatsapp_url': wa,
    }


@app.context_processor
def inject_global_template_vars():
    try:
        s = tenant_query(Settings).first()
    except Exception:
        db.session.rollback()
        s = None
    uid = session.get('user_id')
    user = None
    if uid:
        try:
            user = db.session.get(User, uid)
        except Exception:
            db.session.rollback()
    theme = 'dark'
    if user and getattr(user, 'theme', None):
        theme = normalize_user_theme(user.theme)
    lang = resolve_user_language(user)
    role_label = ''
    if user:
        role_label = ROLE_LABELS.get(user.role, user.role)
        if lang == 'en':
            role_label = ROLE_LABELS_EN.get(user.role, role_label)
    try:
        from liftcore_permissions import (
            effective_permissions,
            permission_groups_for_ui,
            user_can_write_module,
        )
        user_perms = effective_permissions(user, s) if user else frozenset()
        perm_groups = permission_groups_for_ui()
        can_write = user_can_write_module(user, s) if user else False
    except Exception:
        db.session.rollback()
        user_perms = frozenset()
        perm_groups = []
        can_write = False
    try:
        from operator_onboarding import is_platform_operator as _is_op
        platform_op = bool(user and _is_op(user))
    except Exception:
        platform_op = False
    support = _platform_support_context(user=user, settings=s, lang=lang)
    from department_portals import DEPARTMENT_PORTALS, visible_department_portals

    def _perm_ok(perm):
        if not user:
            return False
        try:
            from liftcore_permissions import user_has_permission
            return user_has_permission(user, perm, s)
        except Exception:
            return False
    requested_department = (request.args.get('department') or '').strip()
    if requested_department in DEPARTMENT_PORTALS:
        session['active_department'] = requested_department
    active_department = (
        requested_department or session.get('active_department') or ''
    ).strip()
    active_department_portal = None
    if user and active_department:
        try:
            active_department_portal = next(
                (
                    portal for portal in visible_department_portals(
                        permission_ok=_perm_ok,
                        install_enabled=install_module_enabled(),
                        lang=lang,
                    )
                    if portal['slug'] == active_department
                ),
                None,
            )
        except Exception:
            active_department_portal = None
    return {
        'google_maps_api_key': resolve_google_maps_api_key(s),
        'google_maps_key_source': google_maps_key_source(s),
        'brand_logo_url': brand_logo_url(s),
        'liftcore_logo_url': liftcore_header_logo_url(s),
        'company_stamp_url': upload_url(getattr(s, 'company_stamp_path', None)) if s else '',
        'company_sign_url': upload_url(getattr(s, 'company_sign_path', None)) if s else '',
        'company_stamp_width': (getattr(s, 'company_stamp_width', None) or 110) if s else 110,
        'company_stamp_offset_x': (getattr(s, 'company_stamp_offset_x', None) or 0) if s else 0,
        'company_stamp_offset_y': (getattr(s, 'company_stamp_offset_y', None) or 0) if s else 0,
        'company_sign_width': (getattr(s, 'company_sign_width', None) or 140) if s else 140,
        'company_sign_offset_x': (getattr(s, 'company_sign_offset_x', None) or 0) if s else 0,
        'company_sign_offset_y': (getattr(s, 'company_sign_offset_y', None) or 0) if s else 0,
        'logo_width_sidebar': (getattr(s, 'logo_width_sidebar', None) or 150) if s else 150,
        'logo_width_report': (getattr(s, 'logo_width_report', None) or 150) if s else 150,
        'logo_width_login': (getattr(s, 'logo_width_login', None) or 180) if s else 180,
        'user_theme': theme,
        'user_theme_options': USER_THEME_OPTIONS,
        'user_language': lang,
        'company_settings': s,
        'brand_name': (s.company_name if s and s.company_name else 'LiftCore'),
        'role_labels': ROLE_LABELS,
        'auth_user': user,
        'user_initials': user_initials(user),
        'user_avatar_url': user_avatar_url(user),
        'user_display_name': (user.full_name or user.username) if user else '',
        'user_role_label': role_label,
        'install_module_enabled': install_module_enabled(),
        'session_locked': session_is_locked(),
        'idle_screensaver_enabled': idle_screensaver_enabled(s),
        'idle_screensaver_seconds': idle_screensaver_seconds(s),
        'azkar_ticker_enabled': azkar_ticker_enabled(s),
        'can_write': can_write,
        'is_viewer': bool(user and user.role == 'viewer'),
        'user_permissions': user_perms,
        'permission_groups': perm_groups,
        'must_change_password': bool(user and getattr(user, 'must_change_password', False)),
        'is_platform_operator': platform_op,
        'platform_admin_host': bool(getattr(g, 'platform_admin_host', False)),
        'active_department': active_department if active_department_portal else '',
        'active_department_portal': active_department_portal,
        **support,
        'ui': lambda ar, en: en if lang == 'en' else ar,
    }


@app.template_global()
def has_perm(perm: str) -> bool:
    user = current_user()
    if not user:
        return False
    try:
        s = tenant_query(Settings).first()
    except Exception:
        db.session.rollback()
        s = None
    from liftcore_permissions import user_has_permission
    return user_has_permission(user, perm, s)


@app.template_global()
def has_any_perm(*perms: str) -> bool:
    return any(has_perm(perm) for perm in perms)


@app.template_global()
def csrf_token():
    from liftcore_security import ensure_csrf_token
    return ensure_csrf_token()


def _money_round(n):
    return round(float(n or 0), 2)


def _invoice_status_from_paid(contract, paid, today=None):
    """حالة الفاتورة من المبلغ المحصّل المخزّن (بدون إعادة حساب كامل)."""
    from billing_consistency import _contract_invoice_status

    return _contract_invoice_status(contract, paid, today)


def _refresh_contract_billing_cache(contract):
    """تحديث paid_amount و invoice_status لعقد واحد."""
    from billing_consistency import refresh_contract_cache

    refresh_contract_cache(contract)


def _backfill_contract_billing_cache():
    """ملء كاش الفوترة لجميع العقود (عند إضافة العمود أو الترقية)."""
    contracts = tenant_query(Contract).all()
    if not contracts:
        return
    app.logger.info('Backfilling contract billing cache (%d contracts)...', len(contracts))
    for c in contracts:
        _refresh_contract_billing_cache(c)
    db.session.commit()
    app.logger.info('Contract billing cache backfill complete.')


def contract_to_js_dict(c, *, renewed_ids=None):
    """تسلسل عقد لـ JSON في الصفحة (بدون استعلامات إضافية)."""
    from contract_cost_allocation import contract_cost_allocation

    cid = getattr(c, 'id', None)
    is_renewed = bool(getattr(c, '_is_renewed', False))
    if renewed_ids is not None and cid is not None:
        is_renewed = int(cid) in renewed_ids
    return {
        'id': c.id,
        'code': c.code,
        'customer_id': c.customer_id,
        'customer': c.customer.name if c.customer else '',
        'customer_name_en': (c.customer.name_en or '') if c.customer else '',
        'customer_city': (c.customer.city or '') if c.customer else '',
        'customer_district': (c.customer.district or '') if c.customer else '',
        'customer_lat': (c.customer.lat or '') if c.customer else '',
        'customer_lng': (c.customer.lng or '') if c.customer else '',
        'customer_status': ((c.customer.status or 'نشط') if c.customer else 'نشط'),
        'contract_type': c.contract_type or '',
        'start_date': c.start_date.isoformat() if c.start_date else '',
        'end_date': c.end_date.isoformat() if c.end_date else '',
        'duration': c.duration_months or 0,
        'elevator_ids': [ce.elevator_id for ce in c.elevators],
        'elevators': len(c.elevators),
        'maint_freq': c.maint_frequency or '',
        'visits_month': c.visits_per_month or 1,
        'value': _money_round(c.value or 0),
        'tax_pct': c.tax_pct or 15,
        'tax_amount': _money_round(c.tax_amount or 0),
        'total': _money_round(c.total or 0),
        'pay_terms': c.payment_terms or '',
        'paid_amount': _money_round(c.paid_amount or 0),
        'inv_status': c.invoice_status or 'غير مدفوع',
        'status': c.status or 'نشط',
        'renewed': is_renewed,
        'display_status': contract_display_status(c, renewed_ids=renewed_ids),
        'reminder_date': c.reminder_date.isoformat() if c.reminder_date else '',
        'due_date': c.due_date.isoformat() if getattr(c, 'due_date', None) else '',
        'city': c.city or '',
        'district': c.district or '',
        'address': c.address or '',
        'notes': c.notes or '',
        'file_url': upload_url(c.file_path),
        'file_name': contract_file_display_name(c.file_path),
        'cost_allocation': contract_cost_allocation(c),
    }


def contract_customer_js_dict(c):
    return {
        'id': c.id,
        'name': c.name,
        'name_en': c.name_en or '',
        'code': c.code,
        'city': c.city or '',
        'district': c.district or '',
        'address': c.address or '',
        'phone': c.phone or '',
        'contact_person': c.contact_person or '',
        'lat': c.lat or '',
        'lng': c.lng or '',
        'maps_url': c.maps_url or '',
        'building_photo_url': upload_url(c.building_photo_path),
        'status': c.status or 'نشط',
    }


def client_to_js_dict(c):
    """تسلسل عميل لـ JSON (مع علاقات محمّلة مسبقاً)."""
    cust_contracts = list(c.contracts or [])
    renewed_ids = _annotate_contract_renewals(cust_contracts)
    primary = None
    for ct in sorted(
        cust_contracts,
        key=lambda x: (x.end_date or date.min, x.id or 0),
        reverse=True,
    ):
        st = contract_display_status(ct, renewed_ids=renewed_ids)
        if st in ('نشط', 'على وشك الانتهاء'):
            primary = ct
            break
    if primary is None and cust_contracts:
        primary = cust_contracts[0]
    return {
        'id': c.id,
        'code': c.code,
        'name': c.name,
        'name_en': c.name_en or '',
        'city': c.city or '',
        'district': c.district or '',
        'phone': c.phone or '',
        'phone2': c.phone2 or '',
        'extra_phones': parse_customer_extra_phones(getattr(c, 'extra_phones', None)),
        'email': c.email or '',
        'contact': c.contact_person or '',
        'role': c.contact_role or '',
        'entity_type': c.entity_type or 'فرد',
        'national_id': c.national_id or '',
        'cr_number': c.cr_number or '',
        'vat_number': c.vat_number or '',
        'national_address': c.national_address or '',
        'elevators': len(c.elevators),
        'fleet_status': customer_fleet_status(c),
        'contracts': len(c.contracts),
        'contract_status': contract_display_status(primary, renewed_ids=renewed_ids) if primary else 'بدون عقد',
        'status': c.status,
        'notes': c.notes or '',
        'address': c.address or '',
        'lat': c.lat or '',
        'lng': c.lng or '',
        'maps_url': c.maps_url or '',
        'building_photo_url': upload_url(c.building_photo_path),
    }


def elevator_to_js_dict(e):
    """تسلسل مصعد لـ JSON (مع علاقة العميل)."""
    return {
        'id': e.id,
        'code': e.code,
        'customer_id': e.customer_id,
        'customer': e.customer.name if e.customer else '',
        'customer_name_en': (e.customer.name_en or '') if e.customer else '',
        'building': e.building_name or '',
        'city': e.city or '',
        'district': e.district or '',
        'elev_type': e.elev_type or '',
        'brand': e.brand or '',
        'model': e.model or '',
        'capacity': e.capacity_kg or 0,
        'capacity_persons': e.capacity_persons or 0,
        'floors': e.floors or 0,
        'stops': e.stops or 0,
        'doors': e.doors_count or 0,
        'speed': e.speed or '',
        'serial': e.serial_number or '',
        'machine_type': e.machine_type or '',
        'door_type': e.door_type or '',
        'control_type': e.control_type or '',
        'control_drive': e.control_drive or '',
        'control_operation': e.control_operation or '',
        'control_detail': e.control_detail or '',
        'install_date': e.install_date.isoformat() if e.install_date else '',
        'warranty_end': e.warranty_end.isoformat() if e.warranty_end else '',
        'last_maint': e.last_maintenance.isoformat() if e.last_maintenance else '',
        'next_maint': e.next_maintenance.isoformat() if e.next_maintenance else '',
        'maint_freq': e.maint_frequency or '',
        'address': e.address or '',
        'status': e.status,
        'notes': e.notes or '',
        'customer_lat': (e.customer.lat if e.customer else '') or '',
        'customer_lng': (e.customer.lng if e.customer else '') or '',
        'customer_status': ((e.customer.status or 'نشط') if e.customer else 'نشط'),
    }


def expense_to_js_dict(e):
    return {
        'id': e.id,
        'code': e.code or '',
        'expense_date': str(e.expense_date or ''),
        'expense_type': e.expense_type or '',
        'description': e.description or '',
        'responsible': e.responsible or '',
        'pay_method': e.payment_method or '',
        'amount': e.amount or 0,
        'reference': e.reference or '',
        'proof_url': _upload_url_fast(e.proof_path) if getattr(e, 'proof_path', None) else '',
        'has_proof': bool(getattr(e, 'proof_path', None)),
        'notes': e.notes or '',
        'created_by': created_by_display(e) or '—',
    }


def revenue_to_js_dict(r):
    return {
        'id': r.id,
        'code': r.code or '',
        'customer_id': r.customer_id,
        'contract_id': r.contract_id,
        'customer': r.customer.name if r.customer else '—',
        'contract': r.contract.code if r.contract else '—',
        'revenue_date': str(r.revenue_date or ''),
        'revenue_type': r.revenue_type or '',
        'pay_method': r.payment_method or '',
        'amount': r.amount or 0,
        'tax_amount': r.tax_amount or 0,
        'total': r.total or 0,
        'status': r.status or 'محصّل',
        'reference': r.reference or '',
        'proof_url': _upload_url_fast(r.proof_path) if getattr(r, 'proof_path', None) else '',
        'has_proof': bool(getattr(r, 'proof_path', None)),
        'notes': r.notes or '',
        'created_by': created_by_display(r) or '—',
    }


def invoice_to_js_dict(i):
    return {
        'id': i.id,
        'code': i.code,
        'invoice_type': i.invoice_type or 'فاتورة',
        'customer_id': i.customer_id,
        'contract_id': i.contract_id,
        'customer': i.customer.name if i.customer else '—',
        'customer_name_en': (i.customer.name_en or '') if i.customer else '',
        'contract': i.contract.code if i.contract else '—',
        'invoice_date': str(i.invoice_date or ''),
        'due_date': str(i.due_date or ''),
        'description': i.description or '',
        'amount': i.amount or 0,
        'tax_amount': i.tax_amount or 0,
        'total': i.total or 0,
        'pay_method': i.payment_method or '',
        'status': i.status or 'غير مدفوعة',
        'notes': i.notes or '',
        'parent_invoice_id': getattr(i, 'parent_invoice_id', None),
        'revenue_id': getattr(i, 'revenue_id', None),
        'is_receipt': 'سند' in (i.invoice_type or ''),
        'customer_whatsapp': (
            (i.customer.phone2 or i.customer.phone or '') if i.customer else ''
        ),
        'customer_contact': (
            (i.customer.contact_person or i.customer.name or '') if i.customer else ''
        ),
    }


def stock_movement_to_js_dict(m, tech_names=None):
    tech_names = tech_names or {}
    return {
        'id': m.id,
        'code': m.code,
        'item_id': m.item_id,
        'item_name': m.item.name if m.item else '—',
        'item_code': m.item.code if m.item else '—',
        'movement_date': str(m.movement_date or ''),
        'direction': m.direction or '',
        'movement_type': m.movement_type or '',
        'quantity': m.quantity or 0,
        'unit_price': m.unit_price or 0,
        'total_value': m.total_value or 0,
        'technician': tech_names.get(m.technician_id, '—') if m.technician_id else '—',
        'tech_id': m.technician_id,
        'reason': m.reason or '',
        'notes': m.notes or '',
    }


def inventory_item_js_dict(i):
    return {
        'id': i.id,
        'code': i.code,
        'name': i.name,
        'unit': i.unit or 'قطعة',
        'buy_price': i.buy_price or 0,
    }


def _monthly_aggregate(year, date_col, value_col=None):
    """مجموع أو عدد شهري في 12 استعلاماً مجمّعاً بدل 48."""
    from sqlalchemy import extract, func

    result = [0] * 12
    if value_col is not None:
        rows = db.session.query(
            extract('month', date_col).label('m'),
            func.sum(value_col),
        ).filter(extract('year', date_col) == year).group_by('m').all()
        for m, val in rows:
            result[int(m) - 1] = round(float(val or 0), 2)
    else:
        rows = db.session.query(
            extract('month', date_col).label('m'),
            func.count(),
        ).filter(extract('year', date_col) == year).group_by('m').all()
        for m, val in rows:
            result[int(m) - 1] = int(val or 0)
    return result


# إنشاء الجداول عند التشغيل الأول (يُتخطى عند أوامر Alembic: LIFTCORE_ALEMBIC=1)
def _sqlite_legacy_schema_patches():
    """ترقيات أعمدة يدوية — SQLite فقط (PostgreSQL يستخدم Alembic)."""
    try:
        insp = inspect(db.engine)
        if 'technicians' in insp.get_table_names():
            tech_cols = {c['name'] for c in insp.get_columns('technicians')}
            if 'photo_path' not in tech_cols:
                db.session.execute(text('ALTER TABLE technicians ADD COLUMN photo_path VARCHAR(300)'))
                db.session.commit()
        if 'customers' in insp.get_table_names():
            cust_cols = {c['name'] for c in insp.get_columns('customers')}
            if 'building_photo_path' not in cust_cols:
                db.session.execute(text(
                    'ALTER TABLE customers ADD COLUMN building_photo_path VARCHAR(300)'
                ))
                db.session.commit()
            if 'extra_phones' not in cust_cols:
                db.session.execute(text(
                    'ALTER TABLE customers ADD COLUMN extra_phones TEXT'
                ))
                db.session.commit()
        _migrate_cols = {
            'maintenance_visits': [
                ('fault_id', 'INTEGER'),
                ('plan_month', 'VARCHAR(7)'),
                ('route_order', 'INTEGER'),
                ('dispatched_at', 'DATETIME'),
                ('checklist_json', 'TEXT'),
                ('checklist_template_key', 'VARCHAR(50)'),
                ('completed_at', 'DATETIME'),
                ('maintenance_team_id', 'INTEGER'),
            ],
            'settings': [
                ('google_maps_api_key', 'VARCHAR(200)'),
                ('checklist_template_key', 'VARCHAR(50)'),
                ('rep_name', 'VARCHAR(200)'),
                ('rep_mobile', 'VARCHAR(20)'),
                ('rep_national_id', 'VARCHAR(20)'),
                ('rep_signature_path', 'VARCHAR(300)'),
                ('rep_sign_pin_hash', 'VARCHAR(200)'),
                ('default_sign_method', 'VARCHAR(20)'),
                ('idle_screensaver_enabled', 'BOOLEAN'),
                ('idle_screensaver_seconds', 'INTEGER'),
                ('azkar_ticker_enabled', 'BOOLEAN'),
                ('logo_width_sidebar', 'INTEGER'),
                ('logo_width_report', 'INTEGER'),
                ('logo_width_login', 'INTEGER'),
                ('company_stamp_path', 'VARCHAR(300)'),
                ('company_sign_path', 'VARCHAR(300)'),
                ('company_stamp_width', 'INTEGER DEFAULT 110'),
                ('company_stamp_offset_x', 'INTEGER DEFAULT 0'),
                ('company_stamp_offset_y', 'INTEGER DEFAULT 0'),
                ('company_sign_width', 'INTEGER DEFAULT 140'),
                ('company_sign_offset_x', 'INTEGER DEFAULT 0'),
                ('company_sign_offset_y', 'INTEGER DEFAULT 0'),
                ('address_en', 'TEXT'),
                ('company_website', 'VARCHAR(200)'),
                ('bank_name', 'VARCHAR(100)'),
                ('bank_account_name', 'VARCHAR(200)'),
                ('bank_iban', 'VARCHAR(50)'),
                ('bank_account_no', 'VARCHAR(50)'),
                ('work_country', 'VARCHAR(2)'),
                ('work_weekdays_json', 'TEXT'),
                ('work_hours_start', 'VARCHAR(5)'),
                ('work_hours_end', 'VARCHAR(5)'),
                ('respect_public_holidays', 'BOOLEAN'),
                ('custom_holidays_json', 'TEXT'),
                ('extra_work_days_json', 'TEXT'),
                ('custom_permissions_enabled', 'BOOLEAN'),
            ],
            'users': [
                ('theme', 'VARCHAR(10)'),
                ('language', 'VARCHAR(10)'),
                ('photo_path', 'VARCHAR(300)'),
                ('must_change_password', 'BOOLEAN'),
                ('permissions_extra', 'TEXT'),
                ('session_version', 'INTEGER DEFAULT 0'),
            ],
            'faults': [
                ('visit_id', 'INTEGER'),
                ('client_report', 'TEXT'),
                ('reporter_name', 'VARCHAR(100)'),
                ('reporter_phone', 'VARCHAR(20)'),
                ('tech_notes', 'TEXT'),
                ('needs_parts', 'BOOLEAN'),
                ('dispatched_at', 'DATETIME'),
                ('report_json', 'TEXT'),
            ],
            'elevators': [
                ('machine_type', 'VARCHAR(30)'),
                ('door_type', 'VARCHAR(50)'),
                ('capacity_persons', 'INTEGER'),
                ('stops', 'INTEGER'),
                ('doors_count', 'INTEGER'),
                ('warranty_end', 'DATE'),
                ('maint_frequency', 'VARCHAR(50)'),
                ('control_type', 'VARCHAR(50)'),
                ('control_drive', 'VARCHAR(50)'),
                ('control_operation', 'VARCHAR(50)'),
                ('control_detail', 'VARCHAR(200)'),
                ('address', 'TEXT'),
            ],
            'contracts': [
                ('city', 'VARCHAR(100)'),
                ('district', 'VARCHAR(100)'),
                ('address', 'TEXT'),
                ('paid_amount', 'FLOAT'),
            ],
            'parts_billing': [
                ('visit_id', 'INTEGER'), ('fault_id', 'INTEGER'), ('paid_amount', 'FLOAT'),
                ('payment_note', 'TEXT'),
            ],
            'invoices': [
                ('paid_amount', 'FLOAT'),
                ('parts_billing_id', 'INTEGER'),
                ('parent_invoice_id', 'INTEGER'),
                ('revenue_id', 'INTEGER'),
            ],
            'revenues': [
                ('invoice_id', 'INTEGER'),
                ('parts_billing_id', 'INTEGER'),
                ('proof_path', 'VARCHAR(300)'),
                ('account_id', 'INTEGER'),
            ],
            'expenses': [
                ('proof_path', 'VARCHAR(300)'),
                ('account_id', 'INTEGER'),
            ],
            'technicians': [
                ('team', 'VARCHAR(30)'),
                ('name_en', 'VARCHAR(100)'),
                ('signature_path', 'VARCHAR(300)'),
                ('sign_pin_hash', 'VARCHAR(200)'),
                ('nationality', 'VARCHAR(100)'),
                ('experience_years', 'INTEGER'),
                ('email', 'VARCHAR(120)'),
                ('national_id_expiry', 'DATE'),
                ('license_number', 'VARCHAR(50)'),
                ('license_expiry', 'DATE'),
                ('districts_json', 'TEXT'),
            ],
            'customers': [
                ('name_en', 'VARCHAR(200)'),
                ('entity_type', 'VARCHAR(20)'),
                ('cr_number', 'VARCHAR(50)'),
            ],
            'sales_leads': [
                ('fulfilled_at', 'DATETIME'),
                ('result_org_id', 'INTEGER'),
                ('customer_mail_sent', 'BOOLEAN'),
                ('action_note', 'VARCHAR(500)'),
                ('utm_source', 'VARCHAR(80)'),
                ('utm_medium', 'VARCHAR(80)'),
                ('utm_campaign', 'VARCHAR(120)'),
                ('gclid', 'VARCHAR(120)'),
            ],
            'purchase_orders': [
                ('supplier_phone', 'VARCHAR(30)'),
                ('supplier_email', 'VARCHAR(120)'),
                ('signature_data', 'TEXT'),
                ('pdf_path', 'VARCHAR(300)'),
            ],
            'installation_quotations': [
                ('customer_id', 'INTEGER'),
                ('approved_at', 'DATETIME'),
                ('pay_advance_pct', 'FLOAT'),
                ('pay_supply_pct', 'FLOAT'),
                ('pay_final_pct', 'FLOAT'),
            ],
            'installation_projects': [
                ('accepted_quotation_id', 'INTEGER'),
                ('execution_started_at', 'DATETIME'),
                ('contract_value', 'FLOAT'),
                ('contract_id', 'INTEGER'),
            ],
            'installation_leads': [
                ('customer_id', 'INTEGER'),
            ],
            'installation_timeline_steps': [
                ('started_at', 'DATETIME'),
            ],
            'organizations': [
                ('billing_cycle', 'VARCHAR(20)'),
                ('billing_amount', 'FLOAT'),
                ('billing_status', 'VARCHAR(20)'),
                ('current_period_start', 'DATETIME'),
                ('current_period_end', 'DATETIME'),
                ('last_payment_at', 'DATETIME'),
                ('last_payment_amount', 'FLOAT'),
                ('last_payment_ref', 'VARCHAR(100)'),
                ('billing_notes', 'TEXT'),
                ('elevators_limit_override', 'INTEGER'),
                ('office_users_limit_override', 'INTEGER'),
                ('technicians_limit_override', 'INTEGER'),
                ('storage_gb_limit_override', 'INTEGER'),
            ],
            'onboarding_invites': [
                ('admin_username', 'VARCHAR(50)'),
                ('login_url', 'VARCHAR(300)'),
                ('credentials_email_sent_at', 'DATETIME'),
                ('credentials_email_error', 'VARCHAR(300)'),
            ],
        }
        for table, cols in _migrate_cols.items():
            if table not in insp.get_table_names():
                continue
            existing = {c['name'] for c in insp.get_columns(table)}
            for col_name, col_type in cols:
                if col_name in existing:
                    continue
                try:
                    db.session.execute(text(
                        f'ALTER TABLE {table} ADD COLUMN {col_name} {col_type}'
                    ))
                    db.session.commit()
                except Exception as exc:
                    db.session.rollback()
                    app.logger.warning('Migration skip %s.%s: %s', table, col_name, exc)
        if 'faults' in insp.get_table_names():
            try:
                db.session.execute(text(
                    "UPDATE faults SET status = 'تم الاصلاح' WHERE status = 'محلول'"
                ))
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                app.logger.warning('Fault status migration skip: %s', exc)
        if 'customers' in insp.get_table_names():
            try:
                db.session.execute(text(
                    "UPDATE customers SET status = 'نشط' "
                    "WHERE status IS NULL OR status = '' "
                    "OR status NOT IN ('نشط', 'غير نشط')"
                ))
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                app.logger.warning('Customer status migration skip: %s', exc)
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Schema migration error: %s', exc)


def _startup_schema_and_data_sync():
    db.create_all()
    if is_sqlite(app.config.get('SQLALCHEMY_DATABASE_URI')):
        _sqlite_legacy_schema_patches()
        try:
            from multitenant_schema import ensure_multitenant_schema
            ensure_multitenant_schema(db.session, db.engine)
        except Exception as exc:
            db.session.rollback()
            app.logger.warning('multitenant schema bootstrap: %s', exc)
    else:
        app.logger.info(
            'LiftCore DB backend=%s — Alembic migrations; skip SQLite legacy ALTER',
            database_backend(app.config.get('SQLALCHEMY_DATABASE_URI')),
        )
    # أعمدة تُضاف تلقائياً إن غابت (SQLite/Postgres) — لا تعتمد على Alembic وحده
    try:
        insp = inspect(db.engine)
        tables = set(insp.get_table_names())
        if 'customers' in tables:
            cust_cols = {c['name'] for c in insp.get_columns('customers')}
            if 'extra_phones' not in cust_cols:
                db.session.execute(text('ALTER TABLE customers ADD COLUMN extra_phones TEXT'))
                db.session.commit()
                app.logger.info('Added customers.extra_phones column')
        if 'settings' in tables:
            settings_cols = {c['name'] for c in insp.get_columns('settings')}
            seal_columns = {
                'company_stamp_path': 'VARCHAR(300)',
                'company_sign_path': 'VARCHAR(300)',
                'company_stamp_width': 'INTEGER DEFAULT 110',
                'company_stamp_offset_x': 'INTEGER DEFAULT 0',
                'company_stamp_offset_y': 'INTEGER DEFAULT 0',
                'company_sign_width': 'INTEGER DEFAULT 140',
                'company_sign_offset_x': 'INTEGER DEFAULT 0',
                'company_sign_offset_y': 'INTEGER DEFAULT 0',
                'azkar_ticker_enabled': 'BOOLEAN DEFAULT TRUE',
            }
            for col_name, column_type in seal_columns.items():
                if col_name in settings_cols:
                    continue
                db.session.execute(text(
                    f'ALTER TABLE settings ADD COLUMN {col_name} {column_type}'
                ))
                db.session.commit()
                app.logger.info('Added settings.%s column', col_name)
                settings_cols.add(col_name)
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('settings/customers column ensure skip: %s', exc)
    try:
        from chart_of_accounts import ensure_chart_schema
        ensure_chart_schema()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Chart of accounts schema ensure skip: %s', exc)
    try:
        from accounting_journals import ensure_journal_schema
        ensure_journal_schema()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Journal schema ensure skip: %s', exc)
    try:
        from installation.project_card import ensure_project_card_schema
        ensure_project_card_schema()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Install project card schema ensure skip: %s', exc)
    try:
        from installation.schema import ensure_install_tenant_uniques
        ensure_install_tenant_uniques()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Install tenant unique constraints ensure skip: %s', exc)
    try:
        from liftcore_permissions import ensure_permissions_schema
        ensure_permissions_schema(db.session, db.engine)
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Permissions schema ensure skip: %s', exc)
    try:
        from technician_assignments import backfill_technician_assignments
        backfill_technician_assignments()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Technician assignments backfill skip: %s', exc)
    from live_sync import ensure_live_state
    ensure_live_state()
    try:
        insp2 = inspect(db.engine)
        if 'contracts' in insp2.get_table_names():
            cols = {c['name'] for c in insp2.get_columns('contracts')}
            if 'paid_amount' in cols:
                marker = os.path.join(app.instance_path, '.contract_billing_cache_v1')
                if not os.path.isfile(marker):
                    _backfill_contract_billing_cache()
                    os.makedirs(app.instance_path, exist_ok=True)
                    with open(marker, 'w', encoding='utf-8') as mf:
                        mf.write('ok')
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Contract billing cache backfill skip: %s', exc)


if os.environ.get('LIFTCORE_ALEMBIC', '').strip().lower() not in ('1', 'true', 'yes'):
    with app.app_context():
        _startup_schema_and_data_sync()

from live_sync import register_live_sync

register_live_sync()

TECH_UPLOAD_ROOT = os.path.join(app.root_path, 'static', 'uploads', 'technicians')
VISIT_UPLOAD_ROOT = os.path.join(app.root_path, 'static', 'uploads', 'visits')
COMPANY_UPLOAD_ROOT = os.path.join(app.root_path, 'static', 'uploads', 'company')
USER_UPLOAD_ROOT = os.path.join(app.root_path, 'static', 'uploads', 'users')
CLIENT_UPLOAD_ROOT = os.path.join(app.root_path, 'static', 'uploads', 'clients')
PO_UPLOAD_ROOT = os.path.join(app.root_path, 'static', 'uploads', 'purchase_orders')
ALLOWED_TECH_PHOTO_EXT = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_LOGO_EXT = {'png', 'jpg', 'jpeg', 'webp', 'svg'}
ALLOWED_TECH_DOC_EXT = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}
ALLOWED_CLIENT_PHOTO_EXT = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_CONTRACT_FILE_EXT = {'pdf'}
ALLOWED_FIN_PROOF_EXT = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}
MAX_CONTRACT_FILE_BYTES = 10 * 1024 * 1024
MAX_FIN_PROOF_BYTES = 10 * 1024 * 1024
FIN_PROOF_UPLOAD_ROOT = os.path.join(app.root_path, 'static', 'uploads', 'financial_proofs')

# =============================================
# Helper — توليد الكودات التلقائية
# =============================================
def normalize_phone(phone):
    """توحيد الرقم: 966XXXXXXXXX بدون 0 بعد كود السعودية."""
    if not phone:
        return ''
    digits = re.sub(r'\D', '', str(phone))
    if digits.startswith('966'):
        rest = digits[3:]
        if rest.startswith('0'):
            rest = rest[1:]
        return '966' + rest
    if digits.startswith('0') and len(digits) >= 10:
        return '966' + digits[1:]
    return digits


def format_phone_storage(phone):
    d = normalize_phone(phone)
    return ('+' + d) if d else ''


def client_phone_error(phone):
    """تحقق من رقم جوال العميل — يقبل 05… / 5… / +9665… بعد التطبيع."""
    raw = re.sub(r'\D', '', phone or '')
    if not raw:
        return 'يرجى إدخال رقم الجوال'
    # طبّع أولاً حتى لا تُرفض أرقام Excel التي تبدأ بـ 0 أو بها مسافات
    d = normalize_phone(phone)
    if not d:
        return 'يرجى إدخال رقم الجوال'
    if d.startswith('9660'):
        return 'رقم الجوال غير صالح — أزل الصفر بعد رمز الدولة'
    local = d[3:] if d.startswith('966') else d
    if len(local) < 9:
        return 'رقم الجوال غير مكتمل — أدخل 9 أرقام على الأقل'
    if d.startswith('966') and not local.startswith('5'):
        return 'رقم الجوال يجب أن يبدأ بـ 5 بعد رمز السعودية'
    return None


def phone_key(phone):
    d = normalize_phone(phone)
    if d.startswith('966') and len(d) > 3:
        local = d[3:]
        return local[-9:] if len(local) >= 9 else local
    return d[-9:] if len(d) >= 9 else d


def phone_taken(phone, *, customer_id=None, technician_id=None):
    key = phone_key(phone)
    if not key or len(key) < 9:
        return False, None
    for c in tenant_query(Customer).all():
        if customer_id and c.id == customer_id:
            continue
        phones = [c.phone, c.phone2]
        phones.extend(
            item.get('number') for item in parse_customer_extra_phones(
                getattr(c, 'extra_phones', None)
            )
        )
        for p in phones:
            if p and phone_key(p) == key:
                return True, f'رقم الجوال مستخدم للعميل «{c.name}» ({c.code})'
    for t in tenant_query(Technician).all():
        if technician_id and t.id == technician_id:
            continue
        for p in (t.phone, t.phone2):
            if p and phone_key(p) == key:
                return True, f'رقم الجوال مستخدم للفني «{t.name}» ({t.code})'
    return False, None


def parse_customer_extra_phones(raw) -> list[dict]:
    """قراءة أرقام إضافية من JSON نصي."""
    import json

    if not raw:
        return []
    if isinstance(raw, list):
        data = raw
    else:
        try:
            data = json.loads(raw)
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, str):
            num = format_phone_storage(item)
            if num:
                out.append({'label': '', 'number': num})
            continue
        if not isinstance(item, dict):
            continue
        label = str(item.get('label') or '').strip()[:40]
        num = format_phone_storage(item.get('number') or item.get('phone') or '')
        if num:
            out.append({'label': label, 'number': num})
    return out[:10]


def serialize_customer_extra_phones(items: list[dict] | None) -> str:
    import json

    cleaned = parse_customer_extra_phones(items or [])
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else ''


def parse_extra_phones_from_request(form) -> tuple[list[dict] | None, str | None]:
    """من form: extra_phones JSON أو حقول extra_phone[] / extra_phone_label[]."""
    import json

    raw = (form.get('extra_phones') or '').strip()
    items: list = []
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                items = parsed
        except Exception:
            return None, 'صيغة الأرقام الإضافية غير صالحة'

    if not items:
        nums = form.getlist('extra_phone') if hasattr(form, 'getlist') else []
        labels = form.getlist('extra_phone_label') if hasattr(form, 'getlist') else []
        for i, num in enumerate(nums):
            label = labels[i] if i < len(labels) else ''
            items.append({'label': label, 'number': num})

    cleaned = []
    for item in items:
        if isinstance(item, str):
            label, number = '', item
        elif isinstance(item, dict):
            label = str(item.get('label') or '').strip()[:40]
            number = item.get('number') or item.get('phone') or ''
        else:
            continue
        number = str(number or '').strip()
        if not number:
            continue
        err = client_phone_error(number)
        if err:
            tip = f'«{label}» — {err}' if label else err
            return None, f'رقم إضافي: {tip}'
        cleaned.append({'label': label, 'number': format_phone_storage(number)})
        if len(cleaned) >= 10:
            break
    return cleaned, None


def customer_fleet_status(customer):
    elevs = customer.elevators
    if not elevs:
        return 'بدون مصاعد'
    statuses = [e.status or '' for e in elevs]
    if any(s in ('متوقف', 'خارج الخدمة') for s in statuses):
        return 'يحتاج متابعة'
    if any(s == 'تحت الصيانة' for s in statuses):
        return 'تحت الصيانة'
    if all(s == 'نشط' for s in statuses):
        return 'نشط'
    return statuses[0] or 'نشط'


def _client_account_status(raw):
    return 'غير نشط' if (raw or '').strip() == 'غير نشط' else 'نشط'


def sync_customer_from_elevators(customer):
    """حالة المصاعد تُحسب عبر customer_fleet_status() — لا تُخزَّن في Customer.status."""
    return


app.jinja_env.globals['customer_fleet_status'] = customer_fleet_status


def next_code(model, prefix, field='code', digits=4):
    """التالي من التسلسل داخل المستأجر — مع تجنّب تعارض القيد العالمي القديم على code إن وُجد."""
    import re

    from models import TenantMixin

    max_num = 0
    pattern = re.compile(r'^' + re.escape(prefix) + r'(\d+)$')
    q = tenant_query(model) if issubclass(model, TenantMixin) else model.query
    for row in q.with_entities(getattr(model, field)).all():
        code = row[0]
        if not code:
            continue
        m = pattern.match(str(code).strip())
        if m:
            max_num = max(max_num, int(m.group(1)))

    n = max_num + 1
    col = getattr(model, field)
    while True:
        candidate = f'{prefix}{str(n).zfill(digits)}'
        if issubclass(model, TenantMixin) and _legacy_global_code_unique(model.__tablename__):
            taken = (
                model.query.execution_options(skip_tenant=True)
                .filter(col == candidate)
                .first()
            )
            if taken:
                n += 1
                continue
        return candidate


def _legacy_global_code_unique(table_name: str) -> bool:
    """True إذا بقي UNIQUE(code) القديم من قبل عزل المستأجر."""
    cache = getattr(g, '_legacy_code_unique', None)
    if cache is None:
        cache = {}
        g._legacy_code_unique = cache
    if table_name in cache:
        return cache[table_name]
    try:
        # inspect(engine) على SQLite/StaticPool يفسد المعاملة المفتوحة ويلغي flush
        # غير المُلتزم (مثل paid_amount بعد apply_payment قبل next_code).
        if has_app_context():
            bind = db.session.connection()
        else:
            bind = db.engine
        insp = inspect(bind)
        for uq in insp.get_unique_constraints(table_name) or []:
            cols = list(uq.get('column_names') or [])
            if cols == ['code']:
                cache[table_name] = True
                return True
        for ix in insp.get_indexes(table_name) or []:
            if ix.get('unique') and list(ix.get('column_names') or []) == ['code']:
                cache[table_name] = True
                return True
    except Exception:
        cache[table_name] = False
        return False
    cache[table_name] = False
    return False


# =============================================
# تسجيل الدخول
# =============================================
def _git_commit_short():
    """أحدث commit في مجلد التطبيق — أدق من LIFTCORE_VERSION الثابت."""
    try:
        import subprocess
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=app.root_path,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).decode('utf-8', errors='ignore').strip() or None
    except Exception:
        pass
    # الخدمة غالباً بلا git في PATH — اقرأ .git مباشرة
    try:
        git_dir = os.path.join(app.root_path, '.git')
        head_path = os.path.join(git_dir, 'HEAD')
        if not os.path.isfile(head_path):
            return None
        head = open(head_path, encoding='utf-8').read().strip()
        if head.startswith('ref:'):
            ref = head.split(' ', 1)[1].strip()
            ref_path = os.path.join(git_dir, *ref.split('/'))
            if os.path.isfile(ref_path):
                return open(ref_path, encoding='utf-8').read().strip()[:7]
            return None
        return head[:7]
    except Exception:
        return None


@app.route('/api/version')
def api_version():
    """تحقق سريع من إصدار الكود على السيرفر (بدون تسجيل دخول)."""
    root = app.root_path
    db_info = dict(database_info(app))
    try:
        db_info['customers'] = tenant_query(Customer).count()
        db_info['elevators'] = tenant_query(Elevator).count()
    except Exception:
        pass
    if db_info.get('backend') == 'sqlite':
        db_path = (db_info.get('path') or '').replace('/', os.sep)
        if db_path and os.path.isfile(db_path):
            db_info['file'] = os.path.basename(os.path.dirname(db_path)) + '/' + os.path.basename(db_path)
            db_info['bytes'] = os.path.getsize(db_path)
    git_commit = _git_commit_short()
    return jsonify(
        version=git_commit or APP_VERSION,
        env_version=APP_VERSION,
        git_commit=git_commit,
        db=db_info,
        checks={
            'settings_full': os.path.isfile(os.path.join(root, 'templates/partials/app_header.html')),
            'settings_tabs': os.path.isfile(os.path.join(root, 'templates/settings.html'))
            and 'المظهر' in open(os.path.join(root, 'templates/settings.html'), encoding='utf-8').read(),
            'shell_css': os.path.isfile(os.path.join(root, 'static/liftcore-shell.css')),
            'theme_css': os.path.isfile(os.path.join(root, 'static/liftcore-theme.css')),
            'purchase_orders': os.path.isfile(os.path.join(root, 'templates/purchase-orders.html')),
            'enforce_auth': len(app.before_request_funcs.get(None, [])) > 0,
            'installation_module': os.path.isdir(os.path.join(root, 'installation')),
            'install_enabled': install_module_enabled(),
            'google_maps_key': bool(resolve_google_maps_api_key()),
            'google_maps_key_source': google_maps_key_source(),
        },
    )


@app.route('/api/health')
def api_health():
    """فحص صحة الخادم — DB + قرص + إصدار."""
    import shutil as _shutil
    ok = True
    db_ok = False
    try:
        db.session.execute(text('SELECT 1'))
        db_ok = True
    except Exception:
        ok = False
        db.session.rollback()
    disk = {}
    try:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if is_sqlite(db_uri):
            db_path = db_uri.replace('sqlite:///', '') if db_uri.startswith('sqlite:///') else app.instance_path
            usage_root = os.path.dirname(db_path) or app.root_path
        else:
            usage_root = app.instance_path or app.root_path
        usage = _shutil.disk_usage(usage_root)
        disk = {
            'free_mb': round(usage.free / (1024 * 1024)),
            'total_mb': round(usage.total / (1024 * 1024)),
        }
        if usage.free < 50 * 1024 * 1024:
            ok = False
    except Exception:
        pass
    from liftcore_security import is_production_env, DEFAULT_SECRET_KEYS
    secret_ok = (app.config.get('SECRET_KEY') or '') not in DEFAULT_SECRET_KEYS
    if is_production_env() and not secret_ok:
        ok = False
    status = 200 if ok and db_ok else 503
    return jsonify({
        'ok': ok and db_ok,
        'version': APP_VERSION,
        'database': db_ok,
        'database_backend': database_backend(app.config.get('SQLALCHEMY_DATABASE_URI')),
        'disk': disk,
        'secret_key_ok': secret_ok,
        'production': is_production_env(),
        'monitoring': monitoring_status(),
    }), status


@app.route('/api/admin/billing/consistency')
def api_admin_billing_consistency():
    if not require_admin():
        return jsonify({'error': 'صلاحية المدير مطلوبة'}), 403
    from billing_consistency import audit_billing_consistency

    return jsonify(audit_billing_consistency())


@app.route('/api/admin/billing/consistency/repair', methods=['POST'])
def api_admin_billing_consistency_repair():
    if not require_admin():
        return jsonify({'error': 'صلاحية المدير مطلوبة'}), 403
    from billing_consistency import repair_billing_consistency

    result = repair_billing_consistency(commit=True)
    return jsonify(result)


@app.route('/api/live/revision')
def api_live_revision():
    from live_sync import get_live_revision
    return jsonify({'revision': get_live_revision()})


@app.route('/api/live/sync')
def api_live_sync():
    from live_sync import build_sync_payload, get_live_revision, resolve_page_key

    page_key = request.args.get('page') or resolve_page_key(request.referrer or '') or resolve_page_key(request.path)
    if not page_key:
        return jsonify({'revision': get_live_revision(), 'unsupported': True})
    data = build_sync_payload(page_key)
    if data is None:
        return jsonify({'revision': get_live_revision(), 'page': page_key, 'unsupported': True})
    return jsonify({'revision': get_live_revision(), 'page': page_key, 'data': data})


def _pricing_context(*, seo_page: str = 'landing'):
    from marketing_site import marketing_page_context, marketing_seo_context
    from tenant_signup import coming_soon_enabled, signup_enabled

    signup_open = signup_enabled() and not coming_soon_enabled()
    ctx = marketing_page_context(
        signup_open=signup_open,
        signup_href=url_for('signup') if signup_open else '',
        signup_label='ابدأ الآن' if signup_open else 'تواصل مع المبيعات',
    )
    if not signup_open:
        # نموذج طلب تجربة عبر الإيميل — بدون mailto (يفتح نافذة ويندوز)
        ctx['signup_href'] = '#contact'
        ctx['signup_label'] = 'اطلب عرضاً تجريبياً'
        ctx['signup_external'] = False
    ctx.update(marketing_seo_context(page=seo_page))
    ctx.update(_ads_tracking_context())
    for key in ('utm_source', 'utm_medium', 'utm_campaign', 'gclid'):
        ctx[key] = session.get(key) or request.args.get(key) or ''
    return ctx


def _ads_tracking_context() -> dict:
    import os
    return {
        'gtag_id': (os.environ.get('LIFTCORE_GTAG_ID') or 'AW-18388162918').strip(),
        'ads_conversion_id': (os.environ.get('LIFTCORE_ADS_CONVERSION_ID') or '').strip(),
        'ads_conversion_label': (os.environ.get('LIFTCORE_ADS_CONVERSION_LABEL') or '').strip(),
        'fire_ads_conversion': False,
    }


@app.route('/robots.txt')
def robots_txt():
    body = (
        'User-agent: *\n'
        'Allow: /\n'
        'Allow: /pricing\n'
        'Allow: /product\n'
        'Allow: /start\n'
        'Allow: /elevator-management\n'
        'Allow: /%D8%A8%D8%B1%D9%86%D8%A7%D9%85%D8%AC-%D8%A7%D8%AF%D8%A7%D8%B1%D8%A9-%D8%A7%D9%84%D9%85%D8%B5%D8%A7%D8%B9%D8%AF\n'
        'Disallow: /login\n'
        'Disallow: /dashboard\n'
        'Disallow: /platform\n'
        'Disallow: /field\n'
        'Disallow: /api/\n'
        'Disallow: /signup\n'
        'Disallow: /onboard\n'
        '\n'
        'Sitemap: https://liftcoreapp.com/sitemap.xml\n'
    )
    return app.response_class(body, mimetype='text/plain; charset=utf-8')


@app.route('/sitemap.xml')
def sitemap_xml():
    from datetime import date

    today = date.today().isoformat()
    urls = (
        ('https://liftcoreapp.com/', '1.0', 'weekly'),
        ('https://liftcoreapp.com/pricing', '0.9', 'weekly'),
        ('https://liftcoreapp.com/start', '0.9', 'weekly'),
        ('https://liftcoreapp.com/برنامج-ادارة-المصاعد', '0.95', 'weekly'),
        ('https://liftcoreapp.com/elevator-management', '0.8', 'weekly'),
        ('https://liftcoreapp.com/product', '0.8', 'monthly'),
    )
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, priority, freq in urls:
        parts.append(
            '<url>'
            f'<loc>{loc}</loc>'
            f'<lastmod>{today}</lastmod>'
            f'<changefreq>{freq}</changefreq>'
            f'<priority>{priority}</priority>'
            '</url>'
        )
    parts.append('</urlset>')
    return app.response_class('\n'.join(parts) + '\n', mimetype='application/xml; charset=utf-8')


@app.route('/googled3a45657a209d04b.html')
def google_site_verification():
    """ملف تحقق ملكية النطاق في Google Search Console."""
    return send_from_directory(
        app.static_folder,
        'googled3a45657a209d04b.html',
        mimetype='text/html; charset=utf-8',
    )


@app.route('/demo-request', methods=['POST'])
def demo_request():
    """طلب تجربة أو عرض سعر — يُحفظ في المنصة ويُرسل إيميل للمبيعات."""
    import time
    from liftcore_mail import send_demo_request_email
    from liftcore_security import ensure_csrf_token, validate_csrf
    from marketing_site import marketing_page_context
    from sales_leads import create_sales_lead, mark_lead_email_result

    ensure_csrf_token()
    if not app.config.get('TESTING'):
        validate_csrf(
            method=request.method,
            endpoint=request.endpoint,
            path=request.path or '',
        )

    next_url = (request.form.get('next') or '').strip()
    if next_url not in ('/', '/pricing', '/product', '/start', '/start/thanks'):
        next_url = '/'
    # بعد النجاح من صفحة الإعلان → صفحة شكر لتسجيل التحويل
    if next_url == '/start':
        redirect_to = '/start/thanks'
    else:
        redirect_to = f'{next_url}#contact'

    # honeypot
    if (request.form.get('website') or '').strip():
        flash('تم استلام طلبك. سنتواصل معك قريباً.', 'ok')
        if next_url == '/start':
            return redirect('/start')
        return redirect(redirect_to)

    now = time.time()
    last = float(session.get('demo_request_at') or 0)
    if last and (now - last) < 60:
        flash('انتظر دقيقة ثم أعد المحاولة.', 'warn')
        return redirect(redirect_to if next_url != '/start' else '/start#contact')

    company = (request.form.get('company_name') or '').strip()
    name = (request.form.get('contact_name') or '').strip()
    email = (request.form.get('contact_email') or '').strip()
    phone = (request.form.get('phone') or '').strip()
    city = (request.form.get('city') or '').strip()
    elevators = (request.form.get('elevators') or '').strip()
    notes = (request.form.get('notes') or '').strip()
    request_type = (request.form.get('request_type') or 'demo').strip().lower()
    utm_source = (request.form.get('utm_source') or session.get('utm_source') or '').strip()
    utm_medium = (request.form.get('utm_medium') or session.get('utm_medium') or '').strip()
    utm_campaign = (request.form.get('utm_campaign') or session.get('utm_campaign') or '').strip()
    gclid = (request.form.get('gclid') or session.get('gclid') or '').strip()

    if not company or not name or not email or '@' not in email:
        flash('أكمل اسم الشركة والمسؤول والبريد الإلكتروني.', 'warn')
        return redirect(redirect_to if next_url != '/start' else '/start#contact')

    try:
        lead = create_sales_lead(
            company_name=company,
            contact_name=name,
            contact_email=email,
            phone=phone,
            city=city,
            elevators=elevators,
            notes=notes,
            request_type=request_type,
            source_path=next_url if next_url != '/start/thanks' else '/start',
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            gclid=gclid,
        )
    except Exception:
        app.logger.exception('sales lead save failed')
        db.session.rollback()
        flash('تعذّر حفظ الطلب. أعد المحاولة أو راسل المبيعات مباشرة.', 'warn')
        return redirect('/start#contact' if next_url.startswith('/start') else f'{next_url}#contact')

    sales_email = marketing_page_context(
        signup_open=False, signup_href='#contact', signup_label='',
    )['sales_email']

    result = send_demo_request_email(
        sales_email=sales_email,
        company_name=company,
        contact_name=name,
        contact_email=email,
        phone=phone,
        city=city,
        elevators=elevators,
        notes=notes,
        request_type=request_type,
    )
    try:
        mark_lead_email_result(lead, result)
    except Exception:
        app.logger.exception('sales lead email meta failed')
        db.session.rollback()

    session['demo_request_at'] = now
    if next_url == '/start':
        session['ads_conversion_pending'] = True
    if result.get('ok'):
        flash('وصل طلبك — سيظهر لفريق المبيعات ونرد على بريدك قريباً.', 'ok')
    elif result.get('reason') == 'mail_not_configured':
        flash(
            'تم تسجيل طلبك في المنصة. الإيميل الآلي غير مضبوط حالياً وسنتواصل معك.',
            'ok',
        )
    else:
        flash(
            'تم تسجيل طلبك في المنصة. تعذّر إرسال إيميل تلقائي وسنتواصل معك.',
            'ok',
        )
    return redirect(redirect_to)


@app.route('/')
def index():
    from platform_admin import is_admin_host, is_platform_operator
    from tenant_signup import is_signup_host

    if is_admin_host():
        user = current_user()
        if user and is_platform_operator(user):
            return redirect(url_for('platform_home'))
        return redirect(url_for('login'))
    if is_signup_host():
        # الصفحة العامة: تعريف المنتج أولاً، ثم الأسعار
        return render_template('landing.html', **_pricing_context())
    if current_user():
        return redirect(url_for('home'))
    return redirect(url_for('login'))


@app.route('/home')
def home():
    user = require_login()
    if not user:
        return redirect(url_for('login'))
    session.pop('active_department', None)
    from department_portals import home_ui, visible_department_portals
    lang = resolve_user_language(user)
    return render_template(
        'home.html',
        departments=visible_department_portals(
            permission_ok=has_perm,
            install_enabled=install_module_enabled(),
            lang=lang,
        ),
        home_ui=home_ui(lang),
    )


@app.route('/departments/<department>')
def department_portal(department):
    user = require_login()
    if not user:
        return redirect(url_for('login'))
    from department_portals import portal_ui, visible_department_portals
    lang = resolve_user_language(user)
    portals = {
        portal['slug']: portal
        for portal in visible_department_portals(
            permission_ok=has_perm,
            install_enabled=install_module_enabled(),
            lang=lang,
        )
    }
    portal = portals.get(department)
    if not portal:
        abort(403)
    session['active_department'] = department
    return render_template('department_portal.html', portal=portal, portal_ui=portal_ui(lang))


@app.route('/coming-soon')
def coming_soon():
    """مسار قديم — يوجّه للصفحة التعريفية على النطاق العام."""
    from tenant_signup import require_signup_host

    require_signup_host()
    return redirect(url_for('index'))


@app.route('/pricing')
def pricing():
    """صفحة الباقات والأسعار — عرض عام للعملاء."""
    return render_template('pricing.html', **_pricing_context(seo_page='pricing'))


@app.route('/product')
def product_landing():
    """مسار مباشر للصفحة التعريفية (مفيد من روابط الأسعار)."""
    return render_template('landing.html', **_pricing_context(seo_page='landing'))


@app.route('/برنامج-ادارة-المصاعد')
@app.route('/elevator-management')
def seo_elevator_management():
    """صفحة محتوى SEO لكلمات: برنامج إدارة المصاعد / إدارة مصاعد / برنامج مصاعد."""
    from tenant_signup import require_signup_host

    require_signup_host()
    return render_template(
        'seo_elevator_management.html',
        **_pricing_context(seo_page='seo_elevator'),
    )


def _capture_ads_attribution():
    """يحفظ UTM/gclid من الرابط في الجلسة لاستخدامها مع نموذج الطلب."""
    for key in ('utm_source', 'utm_medium', 'utm_campaign', 'gclid'):
        val = (request.args.get(key) or '').strip()
        if val:
            session[key] = val[:120]


@app.route('/start')
def ads_landing():
    """صفحة هبوط إعلانات Google — نموذج طلب تجربة واضح."""
    from tenant_signup import require_signup_host

    require_signup_host()
    _capture_ads_attribution()
    ctx = _pricing_context(seo_page='ads')
    return render_template('ads_landing.html', **ctx)


@app.route('/start/thanks')
def ads_thanks():
    """صفحة شكر بعد الطلب — مكان إطلاق تحويل Google Ads."""
    from tenant_signup import require_signup_host

    require_signup_host()
    ctx = _pricing_context(seo_page='ads_thanks')
    ctx['fire_ads_conversion'] = bool(session.pop('ads_conversion_pending', None))
    return render_template('ads_thanks.html', **ctx)


def _find_login_user(login_id):
    login_id = (login_id or '').strip()
    if not login_id:
        return None
    return tenant_query(User).filter(
        User.is_active.is_(True),
        or_(User.username == login_id, db.func.lower(User.email) == login_id.lower()),
    ).first()


def _is_platform_login_host() -> bool:
    """بوابة المنشآت على النطاق العام فقط — ليس localhost (تطبيق/e2e محلي)."""
    from platform_admin import is_admin_host
    from tenant_signup import is_signup_host

    if is_admin_host():
        return True
    if not is_signup_host():
        return False
    host = (request.host or '').split(':')[0].lower().rstrip('.')
    # localhost مخصّص للتطبيق المحلي وليس نموذج دخول المنصة (يتطلب حقل المنشأة)
    if host in ('localhost', '127.0.0.1', '::1'):
        return False
    return True


def _require_platform_console_user():
    from platform_admin import is_platform_operator

    user = require_login()
    if not user or not is_platform_operator(user):
        return None
    return user


def _find_org_for_portal(org_key: str):
    """بحث مؤسسة بالمعرّف (slug) أو اسم المنشأة."""
    from models import Organization

    key = (org_key or '').strip()
    if not key:
        return None
    # بحث عبر المؤسسات (بوابة الدخول)
    org = Organization.query.filter(db.func.lower(Organization.slug) == key.lower()).first()  # tenant: platform
    if org:
        return org
    org = Organization.query.filter(db.func.lower(Organization.name) == key.lower()).first()  # tenant: platform
    if org:
        return org
    # اسم الشركة من الإعدادات — مطابقة عبر كل المؤسسات
    settings_row = Settings.query.filter(db.func.lower(Settings.company_name) == key.lower()).first()  # tenant: platform
    if settings_row and settings_row.organization_id:
        return db.session.get(Organization, settings_row.organization_id)
    return None


def _find_user_in_org(org_id: int, login_id: str):
    login_id = (login_id or '').strip()
    if not login_id or not org_id:
        return None
    return User.query.filter(  # tenant: platform — org محدد صراحةً
        User.organization_id == org_id,
        User.is_active.is_(True),
        or_(User.username == login_id, db.func.lower(User.email) == login_id.lower()),
    ).first()


def _tenant_login_base_url(slug: str) -> str:
    slug = (slug or '').strip().lower()
    if slug in ('', 'default', 'app', 'liftcore'):
        return 'https://app.liftcoreapp.com'
    return f'https://{slug}.liftcoreapp.com'


def _make_login_handoff_token(*, user_id: int, organization_id: int) -> str:
    from itsdangerous import URLSafeTimedSerializer

    ser = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='liftcore-login-handoff')
    return ser.dumps({'uid': int(user_id), 'oid': int(organization_id)})


def _load_login_handoff_token(token: str, *, max_age: int = 180) -> dict | None:
    from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

    if not token:
        return None
    ser = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='liftcore-login-handoff')
    try:
        data = ser.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _complete_user_login(user, *, next_url: str | None = None):
    """ضبط الجلسة بعد تحقق كلمة المرور."""
    bump_user_session_version(user)
    session.clear()
    session['user_id'] = user.id
    session['session_version'] = int(user.session_version or 0)
    session['username'] = user.full_name or user.username
    form_lang = (request.form.get('lang') or '').strip()
    if form_lang in ('ar', 'en'):
        user.language = form_lang
        session['lang'] = form_lang
    else:
        session['lang'] = resolve_user_language(user)
    session.permanent = True
    user.last_login = datetime.utcnow()
    db.session.commit()
    from audit_log import log_audit
    log_audit('login_success', user=user)
    session['just_logged_in'] = True
    if getattr(user, 'must_change_password', False):
        session['settings_notice'] = 'يجب تغيير كلمة المرور قبل متابعة العمل.'
        return redirect(url_for('settings', tab='account', force_password=1))
    if next_url and str(next_url).startswith('/'):
        return redirect(next_url)
    return redirect(url_for('welcome'))


@app.route('/manifest.webmanifest')
def web_manifest():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'manifest.webmanifest',
        mimetype='application/manifest+json',
    )


@app.route('/sw.js')
def admin_service_worker():
    resp = send_from_directory(
        os.path.join(app.root_path, 'static'),
        'admin-sw.js',
        mimetype='application/javascript',
    )
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/login', methods=['GET', 'POST'])
def login():
    from liftcore_security import (
        check_login_rate_limit,
        clear_login_attempts,
        ensure_csrf_token,
        is_weak_password,
        record_login_failure,
    )
    from models import Organization
    from platform_admin import find_operator_user, is_admin_host, is_platform_operator

    admin_console = is_admin_host()
    platform = (not admin_console) and _is_platform_login_host()
    error = None
    if current_user():
        if admin_console and is_platform_operator(current_user()):
            return redirect(url_for('platform_home'))
        if not platform and not admin_console:
            return redirect(url_for('home'))
    if request.method == 'GET':
        ensure_csrf_token()
    if request.method == 'POST':
        allowed, retry_sec = check_login_rate_limit()
        if not allowed:
            error = f'محاولات كثيرة — انتظر {retry_sec} ثانية ثم حاول مجدداً.'
        else:
            org_key = (request.form.get('organization') or request.form.get('org') or '').strip()
            login_id = (request.form.get('email') or request.form.get('username') or '').strip()
            password = request.form.get('password') or ''

            user = None
            org = None
            if admin_console:
                user = find_operator_user(login_id)
                if user and user.organization_id:
                    org = db.session.get(Organization, user.organization_id)
            elif platform:
                if not org_key:
                    error = 'أدخل اسم المنشأة أو المعرّف'
                else:
                    from demo_provisioning import organization_access_allowed

                    org = _find_org_for_portal(org_key)
                    if not org or not organization_access_allowed(org):
                        error = 'المنشأة غير موجودة أو انتهت صلاحية التجربة'
                    else:
                        user = _find_user_in_org(org.id, login_id)
            else:
                from demo_provisioning import organization_access_allowed

                user = _find_login_user(login_id)
                if user and user.organization_id:
                    org = db.session.get(Organization, user.organization_id)
                    if org and not organization_access_allowed(org):
                        error = 'انتهت صلاحية الحساب التجريبي — تواصل مع LiftCore'
                        user = None
                        org = None

            if not error and user and verify_password(user.password_hash, password):
                if not password_is_hashed(user.password_hash):
                    user.password_hash = hash_password(password)
                if is_weak_password(password):
                    user.must_change_password = True
                clear_login_attempts()

                if admin_console:
                    if not is_platform_operator(user):
                        error = 'هذا الحساب غير مخوّل للوحة المنصة'
                    else:
                        from audit_log import log_audit
                        log_audit(
                            'login_platform_admin',
                            user=user,
                            organization_id=user.organization_id,
                        )
                        return _complete_user_login(user, next_url=url_for('platform_home'))

                if not error and platform and org is not None:
                    token = _make_login_handoff_token(
                        user_id=user.id,
                        organization_id=org.id,
                    )
                    dest = _tenant_login_base_url(org.slug) + '/auth/handoff?t=' + token
                    from audit_log import log_audit
                    log_audit(
                        'login_portal',
                        user=user,
                        organization_id=org.id,
                        details={'slug': org.slug},
                    )
                    return redirect(dest)

                if not error:
                    return _complete_user_login(user)

            if not error:
                record_login_failure()
                from audit_log import log_audit
                log_audit(
                    'login_failed',
                    details={
                        'login_id': login_id[:80],
                        'org': org_key[:80] if platform else '',
                        'platform': platform,
                        'admin_console': admin_console,
                    },
                )
                if admin_console:
                    error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
                elif platform:
                    error = 'بيانات الدخول غير صحيحة — تحقق من المنشأة واسم المستخدم وكلمة المرور'
                else:
                    error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
    if not error:
        error = session.pop('login_notice', None)
    return render_template(
        'login.html',
        error=error,
        platform_login=bool(platform),
        admin_console_login=bool(admin_console),
        signup_enabled=(
            False if admin_console else
            os.environ.get('LIFTCORE_SIGNUP_ENABLED', '').strip().lower() in (
                '1', 'true', 'yes', 'on',
            )
        ),
    )


@app.route('/auth/handoff')
def auth_handoff():
    """استلام جلسة بعد دخول موحّد من liftcoreapp.com."""
    from models import Organization

    token = (request.args.get('t') or '').strip()
    data = _load_login_handoff_token(token)
    if not data:
        flash('انتهت صلاحية رابط الدخول — سجّل مجدداً.', 'error')
        return redirect(url_for('login'))

    user = db.session.get(User, int(data.get('uid') or 0))
    org = db.session.get(Organization, int(data.get('oid') or 0))
    from demo_provisioning import organization_access_allowed

    if not user or not user.is_active or not org or not organization_access_allowed(org):
        flash('تعذّر إكمال الدخول.', 'error')
        return redirect(url_for('login'))
    if user.organization_id != org.id:
        flash('تعذّر إكمال الدخول.', 'error')
        return redirect(url_for('login'))

    # تأكد أننا على subdomain الصحيح
    host = (request.host or '').split(':')[0].lower()
    expected = _tenant_login_base_url(org.slug).replace('https://', '').replace('http://', '')
    if host != expected and host not in ('localhost', '127.0.0.1'):
        # أعد التوجيه للنطاق الصحيح بنفس الرمز (مرة واحدة)
        return redirect(f'https://{expected}/auth/handoff?t={token}')

    g.organization = org
    g.organization_id = org.id
    return _complete_user_login(user)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    from liftcore_security import ensure_csrf_token, password_policy_error
    from liftcore_mail import send_welcome_email
    from tenant_signup import (
        coming_soon_enabled,
        create_tenant_signup,
        is_signup_host,
        require_signup_host,
        signup_enabled,
        validate_slug,
    )

    require_signup_host()
    if coming_soon_enabled() or not signup_enabled():
        # التسجيل مغلق مؤقتاً — اعرض الباقات واتصل بنا
        return redirect(url_for('pricing'))

    # جلسة من subdomain آخر قد تكسر CSRF/الطلب — امسحها ثم أعد رمز CSRF
    if session.get('user_id'):
        session.clear()
    ensure_csrf_token()

    error = None
    success = None

    if request.method == 'POST':
        company_name = request.form.get('company_name', '')
        slug = request.form.get('slug', '')
        admin_email = request.form.get('admin_email', '')
        admin_name = request.form.get('admin_name', '')
        password = request.form.get('password', '')
        password2 = request.form.get('password_confirm', '')

        slug_err = validate_slug(slug)
        pwd_err = password_policy_error(password)
        if slug_err:
            error = slug_err
        elif pwd_err:
            error = pwd_err
        elif password != password2:
            error = 'تأكيد كلمة المرور غير متطابق.'
        else:
            try:
                result = create_tenant_signup(
                    company_name=company_name,
                    slug=slug,
                    admin_email=admin_email,
                    admin_name=admin_name,
                    password_hash=hash_password(password),
                )
            except Exception:
                app.logger.exception('tenant signup failed')
                db.session.rollback()
                error = 'تعذّر إنشاء الحساب بسبب خطأ في الخادم. جرّب معرّفاً أو بريداً مختلفاً.'
                result = None
            if result is not None and not result.get('ok'):
                error = ' — '.join(result.get('errors') or ['تعذّر إنشاء الحساب.'])
            elif result is not None:
                try:
                    send_welcome_email(
                        to_email=admin_email,
                        company_name=company_name.strip(),
                        slug=result['slug'],
                        admin_name=admin_name.strip(),
                        login_url=result['login_url'],
                    )
                except Exception:
                    app.logger.exception('signup welcome email failed')
                success = result
                try:
                    from audit_log import log_audit

                    log_audit(
                        'tenant_signup',
                        organization_id=result['organization_id'],
                        details={'slug': result['slug'], 'organization_id': result['organization_id']},
                    )
                except Exception:
                    app.logger.exception('signup audit failed')

    return render_template(
        'signup.html',
        error=error,
        success=success,
        signup_enabled=signup_enabled(),
    )


@app.route('/api/signup', methods=['POST'])
def api_signup():
    from liftcore_security import password_policy_error
    from liftcore_mail import send_welcome_email
    from tenant_signup import (
        coming_soon_enabled,
        create_tenant_signup,
        require_signup_host,
        signup_enabled,
    )

    require_signup_host()
    if coming_soon_enabled() or not signup_enabled():
        return jsonify({'ok': False, 'error': 'signup_disabled'}), 404

    data = request.get_json(silent=True) if request.is_json else None
    if not isinstance(data, dict):
        data = request.form

    password = (data.get('password') or '').strip()
    pwd_err = password_policy_error(password, lang='en')
    if pwd_err:
        return jsonify({'ok': False, 'errors': [pwd_err]}), 400

    result = create_tenant_signup(
        company_name=data.get('company_name', ''),
        slug=data.get('slug', ''),
        admin_email=data.get('admin_email', ''),
        admin_name=data.get('admin_name', ''),
        password_hash=hash_password(password),
        username=(data.get('username') or '').strip() or None,
    )
    if not result.get('ok'):
        return jsonify({'ok': False, 'errors': result.get('errors', [])}), 400

    try:
        send_welcome_email(
            to_email=(data.get('admin_email') or '').strip(),
            company_name=(data.get('company_name') or '').strip(),
            slug=result['slug'],
            admin_name=(data.get('admin_name') or '').strip(),
            login_url=result['login_url'],
        )
    except Exception:
        app.logger.exception('api signup welcome email failed')
    try:
        from audit_log import log_audit

        log_audit(
            'tenant_signup',
            organization_id=result['organization_id'],
            details={'slug': result['slug'], 'organization_id': result['organization_id']},
        )
    except Exception:
        app.logger.exception('api signup audit failed')
    return jsonify({
        'ok': True,
        'slug': result['slug'],
        'login_url': result['login_url'],
        'username': result['username'],
    }), 201


@app.route('/onboard/<token>', methods=['GET', 'POST'])
def onboard_form(token):
    """فورم العميل عبر رابط دعوة لمرة واحدة — على نطاق المنصة فقط."""
    from liftcore_security import ensure_csrf_token
    from operator_onboarding import get_invite, invite_is_open, submit_invite_form
    from tenant_signup import is_signup_host, require_signup_host

    require_signup_host()
    if session.get('user_id'):
        session.clear()
    ensure_csrf_token()

    inv = get_invite(token)
    error = None
    success = False
    closed = None
    form = {}

    if not inv:
        return render_template(
            'onboard.html',
            invite=None,
            error=None,
            success=False,
            closed='رابط الدعوة غير صالح أو منتهي. اطلب رابطاً جديداً من فريق LiftCore.',
            form={},
            signup_host=is_signup_host(),
        ), 404

    if request.method == 'POST':
        form = request.form.to_dict()
        result = submit_invite_form(inv, form)
        if result.get('ok'):
            success = True
            inv = result['invite']
        else:
            error = ' — '.join(result.get('errors') or ['تعذّر حفظ البيانات.'])
    else:
        ok, msg = invite_is_open(inv)
        if not ok:
            closed = msg

    return render_template(
        'onboard.html',
        invite=inv,
        error=error,
        success=success,
        closed=closed,
        form=form,
        signup_host=is_signup_host(),
    )


def _require_platform_operator():
    from operator_onboarding import is_platform_operator
    from platform_admin import is_admin_host

    if not is_admin_host():
        return None
    user = require_admin()
    if not user or not is_platform_operator(user):
        return None
    return user


@app.route('/operator/onboarding')
def operator_onboarding():
    from liftcore_mail import mail_configured
    from operator_onboarding import PLANS, invite_public_url, is_platform_operator, list_invites
    from platform_admin import is_admin_host

    user = require_login()
    if not user:
        return redirect(url_for('login'))
    if not is_platform_operator(user):
        abort(404)
    if not is_admin_host():
        return redirect('https://admin.liftcoreapp.com/operator/onboarding')

    return render_template(
        'operator_onboarding.html',
        nav='create_invite',
        invites=list_invites(100),
        plans=PLANS,
        invite_url=invite_public_url,
        notice=session.pop('op_notice', None),
        notice_type=session.pop('op_notice_type', None),
        created_url=session.pop('op_created_url', None),
        activated=session.pop('op_activated', None),
        mail_ready=mail_configured(),
        current_user=user,
    )


@app.route('/operator/onboarding/create', methods=['POST'])
def operator_onboarding_create():
    from liftcore_mail import mail_result_message, send_onboarding_invite_email
    from operator_onboarding import create_invite
    from platform_admin import is_admin_host

    if not is_admin_host():
        abort(404)
    user = _require_platform_operator()
    if not user:
        abort(404)
    try:
        days = int(request.form.get('days') or 14)
    except (TypeError, ValueError):
        days = 14
    contact_email = (request.form.get('contact_email') or '').strip()
    contact_name = (request.form.get('contact_name') or '').strip()
    result = create_invite(
        plan=request.form.get('plan') or 'basic',
        suggested_slug=request.form.get('suggested_slug') or '',
        contact_email=contact_email,
        contact_name=contact_name,
        notes=request.form.get('notes') or '',
        created_by_user_id=user.id,
        days=days,
    )
    if result.get('ok'):
        inv = result['invite']
        session['op_created_url'] = result['url']
        mail_result = {'ok': False, 'reason': 'failed'}
        try:
            mail_result = send_onboarding_invite_email(
                to_email=inv.contact_email,
                contact_name=inv.contact_name or '',
                invite_url=result['url'],
                plan=inv.plan or 'basic',
                days=result.get('ttl_days'),
            )
        except Exception:
            app.logger.exception('invite email failed')
        notice, ntype = mail_result_message(mail_result, to_email=inv.contact_email)
        if mail_result.get('ok'):
            session['op_notice'] = f'تم إنشاء الدعوة. {notice}'
        else:
            session['op_notice'] = f'تم إنشاء الدعوة. {notice}'
        session['op_notice_type'] = ntype
        try:
            from audit_log import log_audit

            log_audit(
                'onboarding_invite_created',
                details={
                    'invite_id': inv.id,
                    'plan': inv.plan,
                    'email_sent': bool(mail_result.get('ok')),
                    'email_reason': mail_result.get('reason'),
                    'contact_email': inv.contact_email,
                },
            )
        except Exception:
            app.logger.exception('invite audit failed')
    else:
        session['op_notice'] = ' — '.join(result.get('errors') or ['فشل إنشاء الدعوة.'])
        session['op_notice_type'] = 'warn'
    return redirect(url_for('operator_onboarding'))


@app.route('/operator/onboarding/<int:invite_id>/resend', methods=['POST'])
def operator_onboarding_resend(invite_id):
    from liftcore_mail import mail_result_message, send_onboarding_invite_email
    from models import OnboardingInvite
    from operator_onboarding import invite_public_url

    user = _require_platform_operator()
    if not user:
        abort(404)
    inv = db.session.get(OnboardingInvite, invite_id)
    if not inv or inv.status not in ('pending', 'submitted'):
        session['op_notice'] = 'لا يمكن إعادة إرسال هذه الدعوة.'
        session['op_notice_type'] = 'warn'
        return redirect(url_for('operator_onboarding'))
    if not inv.contact_email and not inv.admin_email:
        session['op_notice'] = 'لا يوجد بريد على الدعوة.'
        session['op_notice_type'] = 'warn'
        return redirect(url_for('operator_onboarding'))

    to_email = inv.contact_email or inv.admin_email
    ttl = None
    if inv.expires_at:
        ttl = max(1, (inv.expires_at - datetime.utcnow()).days)
    mail_result = send_onboarding_invite_email(
        to_email=to_email,
        contact_name=inv.contact_name or inv.admin_name or '',
        invite_url=invite_public_url(inv.token),
        plan=inv.plan or 'basic',
        days=ttl,
    )
    notice, ntype = mail_result_message(mail_result, to_email=to_email)
    session['op_notice'] = notice
    session['op_notice_type'] = ntype
    return redirect(url_for('operator_onboarding_detail', invite_id=invite_id))


@app.route('/operator/onboarding/<int:invite_id>')
def operator_onboarding_detail(invite_id):
    from models import OnboardingInvite
    from operator_onboarding import PLANS, invite_public_url, is_platform_operator
    from platform_admin import is_admin_host

    user = require_login()
    if not user:
        return redirect(url_for('login'))
    if not is_platform_operator(user):
        abort(404)
    if not is_admin_host():
        return redirect(f'https://admin.liftcoreapp.com/operator/onboarding/{invite_id}')
    inv = db.session.get(OnboardingInvite, invite_id)
    if not inv:
        abort(404)
    return render_template(
        'operator_onboarding_detail.html',
        nav='invites',
        inv=inv,
        plans=PLANS,
        invite_url=invite_public_url(inv.token),
        notice=session.pop('op_notice', None),
        notice_type=session.pop('op_notice_type', None),
        issued_password=session.pop('op_issued_password', None),
        issued_to=session.pop('op_issued_to', None),
        current_user=user,
    )


@app.route('/operator/onboarding/<int:invite_id>/activate', methods=['POST'])
def operator_onboarding_activate(invite_id):
    from liftcore_mail import mail_result_message, send_onboarding_activated_email
    from liftcore_security import password_policy_error
    from models import OnboardingInvite
    from operator_onboarding import activate_invite

    user = _require_platform_operator()
    if not user:
        abort(404)
    inv = db.session.get(OnboardingInvite, invite_id)
    if not inv:
        abort(404)

    password = (request.form.get('password') or '').strip()
    if not password:
        password = generate_password(14)
    pwd_err = password_policy_error(password)
    if pwd_err:
        session['op_notice'] = pwd_err
        session['op_notice_type'] = 'warn'
        return redirect(url_for('operator_onboarding_detail', invite_id=invite_id))

    result = activate_invite(
        inv,
        slug=request.form.get('slug'),
        plan=request.form.get('plan'),
        password=password,
        password_hash=hash_password(password),
    )
    if not result.get('ok'):
        session['op_notice'] = ' — '.join(result.get('errors') or ['فشل التفعيل.'])
        session['op_notice_type'] = 'warn'
        return redirect(url_for('operator_onboarding_detail', invite_id=invite_id))

    inv = db.session.get(OnboardingInvite, invite_id)
    session['op_activated'] = {
        'login_url': result['login_url'],
        'username': result['username'],
        'password': result['password'],
        'plan': result['plan'],
    }
    session['op_issued_password'] = result['password']
    to_email = (inv.admin_email or inv.contact_email or '').strip() if inv else ''
    session['op_issued_to'] = to_email
    session['op_notice'] = f"تم تفعيل {result['slug']}."
    session['op_notice_type'] = 'ok'

    try:
        from audit_log import log_audit

        log_audit(
            'onboarding_invite_activated',
            organization_id=result['organization_id'],
            details={'slug': result['slug'], 'plan': result['plan']},
        )
    except Exception:
        app.logger.exception('activate invite audit failed')

    if to_email and inv:
        try:
            mail_result = send_onboarding_activated_email(
                to_email=to_email,
                company_name=inv.company_name or result['slug'],
                admin_name=inv.admin_name or inv.contact_name or '',
                slug=result['slug'],
                username=result['username'],
                password=result['password'],
                login_url=result['login_url'],
                plan=result['plan'],
            )
            if mail_result.get('ok'):
                inv.credentials_email_sent_at = datetime.utcnow()
                inv.credentials_email_error = None
            else:
                inv.credentials_email_error = (
                    mail_result.get('detail') or mail_result.get('reason') or 'failed'
                )[:300]
            db.session.commit()
            notice, ntype = mail_result_message(mail_result, to_email=to_email)
            session['op_notice'] = f"تم تفعيل {result['slug']}. {notice}"
            session['op_notice_type'] = ntype
        except Exception:
            app.logger.exception('activate invite email failed')
            session['op_notice'] = (
                f"تم تفعيل {result['slug']}، لكن تعذّر إرسال البريد. "
                'افتح التفاصيل وأعد إرسال بيانات الدخول.'
            )
            session['op_notice_type'] = 'warn'
    return redirect(url_for('operator_onboarding_detail', invite_id=invite_id))


@app.route('/operator/onboarding/<int:invite_id>/resend-credentials', methods=['POST'])
def operator_onboarding_resend_credentials(invite_id):
    from liftcore_mail import mail_result_message
    from liftcore_security import password_policy_error
    from models import OnboardingInvite
    from operator_onboarding import reset_and_email_credentials

    user = _require_platform_operator()
    if not user:
        abort(404)
    inv = db.session.get(OnboardingInvite, invite_id)
    if not inv:
        abort(404)

    password = (request.form.get('password') or '').strip()
    if not password:
        password = generate_password(14)
    pwd_err = password_policy_error(password)
    if pwd_err:
        session['op_notice'] = pwd_err
        session['op_notice_type'] = 'warn'
        return redirect(url_for('operator_onboarding_detail', invite_id=invite_id))

    result = reset_and_email_credentials(
        inv,
        password=password,
        password_hash=hash_password(password),
    )
    if not result.get('ok'):
        session['op_notice'] = ' — '.join(result.get('errors') or ['فشل إرسال بيانات الدخول.'])
        session['op_notice_type'] = 'warn'
        return redirect(url_for('operator_onboarding_detail', invite_id=invite_id))

    session['op_issued_password'] = result['password']
    session['op_issued_to'] = result.get('to_email')
    notice, ntype = mail_result_message(result.get('mail') or {}, to_email=result.get('to_email') or '')
    session['op_notice'] = notice
    session['op_notice_type'] = ntype
    return redirect(url_for('operator_onboarding_detail', invite_id=invite_id))


@app.route('/operator/onboarding/<int:invite_id>/cancel', methods=['POST'])
def operator_onboarding_cancel(invite_id):
    from models import OnboardingInvite

    user = _require_platform_operator()
    if not user:
        abort(404)
    inv = db.session.get(OnboardingInvite, invite_id)
    if inv and inv.status in ('pending', 'submitted'):
        inv.status = 'cancelled'
        db.session.commit()
        session['op_notice'] = 'تم إلغاء الدعوة.'
        session['op_notice_type'] = 'info'
    return redirect(url_for('operator_onboarding'))


# =============================================
# لوحة إدارة المنصة (admin.liftcoreapp.com)
# =============================================
@app.route('/platform')
@app.route('/platform/')
def platform_home():
    from platform_admin import is_admin_host, list_organizations, org_stats, recent_invites, server_status, tenant_ops_by_id
    from sales_leads import list_sales_leads, sales_lead_stats

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))
    lead_stats = sales_lead_stats()
    stats = org_stats()
    stats['leads_new'] = lead_stats.get('new', 0)
    orgs = list_organizations(limit=12)
    return render_template(
        'platform/home.html',
        nav='home',
        stats=stats,
        server=server_status(),
        orgs=orgs,
        ops=tenant_ops_by_id(orgs),
        invites=recent_invites(12),
        leads=list_sales_leads(limit=12),
        notice=session.pop('plat_notice', None),
        notice_type=session.pop('plat_notice_type', None),
    )


@app.route('/platform/leads')
def platform_leads():
    from platform_admin import is_admin_host
    from sales_leads import (
        LEAD_STATUSES,
        REQUEST_TYPES,
        list_sales_leads,
        request_type_label,
        sales_lead_stats,
        status_label,
    )

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))
    status = (request.args.get('status') or '').strip()
    return render_template(
        'platform/leads.html',
        nav='leads',
        leads=list_sales_leads(status=status, limit=300),
        lead_stats=sales_lead_stats(),
        status_filter=status,
        lead_statuses=LEAD_STATUSES,
        request_types=REQUEST_TYPES,
        request_type_label=request_type_label,
        status_label=status_label,
        notice=session.pop('plat_notice', None),
        notice_type=session.pop('plat_notice_type', None),
    )


@app.route('/platform/leads/<int:lead_id>/status', methods=['POST'])
def platform_lead_status(lead_id):
    from platform_admin import is_admin_host
    from sales_leads import set_sales_lead_status

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))
    status = (request.form.get('status') or '').strip()
    lead = set_sales_lead_status(lead_id, status)
    if lead:
        session['plat_notice'] = f'تم تحديث حالة الطلب #{lead.id}.'
        session['plat_notice_type'] = 'ok'
    else:
        session['plat_notice'] = 'تعذّر تحديث الحالة.'
        session['plat_notice_type'] = 'warn'
    nxt = (request.form.get('next') or '').strip()
    if nxt.startswith('/platform/leads'):
        return redirect(nxt)
    return redirect(url_for('platform_leads'))


@app.route('/platform/leads/<int:lead_id>/send-demo', methods=['POST'])
def platform_lead_send_demo(lead_id):
    """موافقة على طلب تجربة: إنشاء حساب + إرسال بيانات الدخول للعميل."""
    from platform_admin import is_admin_host
    from sales_leads import fulfill_demo_lead

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))

    result = fulfill_demo_lead(lead_id, password_hasher=hash_password)
    if not result.get('ok'):
        session['plat_notice'] = result.get('error') or 'فشل إرسال التجربة.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_leads'))

    demo = result.get('demo') or {}
    mail_ok = bool((result.get('mail') or {}).get('ok'))
    session['plat_issued_password'] = result.get('password')
    session['plat_issued_username'] = demo.get('username')
    session['plat_issued_login_url'] = demo.get('login_url')
    session['plat_issued_company'] = demo.get('company_name')
    ends = demo.get('trial_ends_at')
    session['plat_issued_trial_ends'] = ends.strftime('%Y-%m-%d %H:%M') if ends else ''
    if mail_ok:
        session['plat_notice'] = (
            f"تم إنشاء التجربة وإرسال بيانات الدخول إلى {demo.get('admin_email') or ''}."
        )
        session['plat_notice_type'] = 'ok'
    else:
        session['plat_notice'] = (
            'تم إنشاء الحساب التجريبي لكن تعذّر إرسال الإيميل — انسخ بيانات الدخول من التفاصيل.'
        )
        session['plat_notice_type'] = 'warn'

    try:
        from audit_log import log_audit
        log_audit(
            'platform_lead_demo_sent',
            user=user,
            organization_id=demo.get('organization_id'),
            details={'lead_id': lead_id, 'slug': demo.get('slug'), 'mail_ok': mail_ok},
        )
    except Exception:
        app.logger.exception('lead demo audit failed')

    org_id = demo.get('organization_id')
    if org_id:
        return redirect(url_for('platform_org_detail', org_id=org_id))
    return redirect(url_for('platform_leads'))


@app.route('/platform/leads/<int:lead_id>/send-quote', methods=['POST'])
def platform_lead_send_quote(lead_id):
    """إرسال عرض أسعار للعميل بضغطة واحدة."""
    from platform_admin import is_admin_host
    from sales_leads import fulfill_quote_lead, get_sales_lead

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))

    result = fulfill_quote_lead(lead_id)
    if not result.get('ok'):
        session['plat_notice'] = result.get('error') or 'فشل إرسال عرض السعر.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_leads'))

    lead = result.get('lead') or get_sales_lead(lead_id)
    session['plat_notice'] = f'تم إرسال عرض السعر إلى {lead.contact_email if lead else ""}.'
    session['plat_notice_type'] = 'ok'
    try:
        from audit_log import log_audit
        log_audit(
            'platform_lead_quote_sent',
            user=user,
            details={'lead_id': lead_id, 'email': getattr(lead, 'contact_email', None)},
        )
    except Exception:
        app.logger.exception('lead quote audit failed')
    return redirect(url_for('platform_leads'))


@app.route('/platform/leads/clear', methods=['POST'])
def platform_leads_clear():
    """تصفير كل طلبات المبيعات."""
    from platform_admin import is_admin_host
    from sales_leads import clear_all_sales_leads

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))

    confirm = (request.form.get('confirm') or '').strip()
    if confirm != 'CLEAR':
        session['plat_notice'] = 'لتصفير الطلبات اكتب CLEAR في خانة التأكيد.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_leads'))

    n = clear_all_sales_leads()
    try:
        from audit_log import log_audit
        log_audit('platform_leads_cleared', user=user, details={'count': n})
    except Exception:
        app.logger.exception('leads clear audit failed')
    session['plat_notice'] = f'تم تصفير طلبات المبيعات ({n}).'
    session['plat_notice_type'] = 'ok'
    return redirect(url_for('platform_leads'))


@app.route('/platform/orgs')
def platform_orgs():
    from demo_provisioning import demo_days_default
    from platform_admin import is_admin_host, list_organizations, server_status, tenant_ops_by_id

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))
    q = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or '').strip()
    orgs = list_organizations(q=q, status=status, limit=300)
    return render_template(
        'platform/orgs.html',
        nav='orgs',
        orgs=orgs,
        ops=tenant_ops_by_id(orgs),
        server=server_status(),
        q=q,
        status=status,
        demo_days=demo_days_default(),
        notice=session.pop('plat_notice', None),
        notice_type=session.pop('plat_notice_type', None),
    )


@app.route('/platform/ops')
def platform_ops():
    from platform_admin import is_admin_host, list_organizations, org_stats, server_status, tenant_ops_by_id

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))
    orgs = list_organizations(limit=300)
    stats = org_stats()
    return render_template(
        'platform/ops.html',
        nav='ops',
        server=server_status(),
        stats=stats,
        orgs=orgs,
        ops=tenant_ops_by_id(orgs),
        notice=session.pop('plat_notice', None),
        notice_type=session.pop('plat_notice_type', None),
    )


@app.route('/platform/demos/create', methods=['GET', 'POST'])
def platform_demo_create():
    """إصدار حساب تجريبي مؤقت (يوزر + كلمة مرور + 4 مصاعد)."""
    from demo_provisioning import create_demo_account, demo_days_default
    from platform_admin import is_admin_host

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))

    if request.method == 'GET':
        return redirect(url_for('platform_orgs'))

    try:
        days = int(request.form.get('days') or demo_days_default())
    except (TypeError, ValueError):
        days = demo_days_default()

    result = create_demo_account(
        company_name=(request.form.get('company_name') or '').strip() or None,
        contact_name=(request.form.get('contact_name') or '').strip() or None,
        contact_email=(request.form.get('contact_email') or '').strip() or None,
        days=days,
        password_hasher=hash_password,
    )
    if not result.get('ok'):
        session['plat_notice'] = ' — '.join(result.get('errors') or ['فشل إنشاء الحساب التجريبي.'])
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_orgs'))

    try:
        from audit_log import log_audit

        log_audit(
            'platform_demo_created',
            user=user,
            organization_id=result.get('organization_id'),
            details={
                'slug': result.get('slug'),
                'days': result.get('days'),
                'elevators': (result.get('seed') or {}).get('elevators'),
            },
        )
    except Exception:
        app.logger.exception('platform demo audit failed')

    session['plat_issued_password'] = result['password']
    session['plat_issued_username'] = result['username']
    session['plat_issued_login_url'] = result['login_url']
    session['plat_issued_company'] = result.get('company_name')
    ends = result.get('trial_ends_at')
    session['plat_issued_trial_ends'] = ends.strftime('%Y-%m-%d %H:%M') if ends else ''
    session['plat_notice'] = (
        f"تم إنشاء حساب تجريبي «{result.get('company_name')}» "
        f"({result.get('slug')}) — صلاحية {result.get('days')} يوم، 4 مصاعد جاهزة للتجربة."
    )
    session['plat_notice_type'] = 'ok'
    return redirect(url_for('platform_org_detail', org_id=result['organization_id']))


@app.route('/platform/orgs/<int:org_id>')
def platform_org_detail(org_id):
    from platform_admin import get_org_detail, is_admin_host

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))
    detail = get_org_detail(org_id)
    if not detail:
        abort(404)
    from tenant_lifecycle import is_protected_operator_org
    return render_template(
        'platform/org_detail.html',
        nav='orgs',
        org=detail['org'],
        settings=detail['settings'],
        users=detail['users'],
        admin=detail['admin'],
        invites=detail['invites'],
        payments=detail.get('payments') or [],
        billing_amount=detail.get('billing_amount') or 0,
        login_url=detail['login_url'],
        plans=detail['plans'],
        entitlements=detail.get('entitlements') or {},
        org_addons=detail.get('org_addons') or [],
        addon_catalog=detail.get('addon_catalog') or [],
        can_delete=not is_protected_operator_org(detail['org']),
        notice=session.pop('plat_notice', None),
        notice_type=session.pop('plat_notice_type', None),
        issued_password=session.pop('plat_issued_password', None),
        issued_username=session.pop('plat_issued_username', None),
        issued_login_url=session.pop('plat_issued_login_url', None),
        issued_company=session.pop('plat_issued_company', None),
        issued_trial_ends=session.pop('plat_issued_trial_ends', None),
        issued_to=session.pop('plat_issued_to', None),
    )


@app.route('/platform/orgs/<int:org_id>/update', methods=['POST'])
def platform_org_update(org_id):
    from models import Organization
    from platform_admin import is_admin_host, update_org

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        abort(404)
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)
    # زر الإيقاف يرسل status=suspended كقيمة الزر
    status = request.form.get('status')
    result = update_org(
        org,
        plan=request.form.get('plan'),
        status=status,
        notes=request.form.get('notes'),
        name=request.form.get('name'),
        admin_email=request.form.get('admin_email'),
    )
    if result.get('ok'):
        session['plat_notice'] = 'تم حفظ تغييرات المؤسسة.'
        session['plat_notice_type'] = 'ok'
        try:
            from audit_log import log_audit
            log_audit(
                'platform_org_updated',
                organization_id=org.id,
                details={'status': org.status, 'plan': org.plan},
            )
        except Exception:
            app.logger.exception('platform org audit failed')
    else:
        session['plat_notice'] = ' — '.join(result.get('errors') or ['فشل الحفظ.'])
        session['plat_notice_type'] = 'warn'
    return redirect(url_for('platform_org_detail', org_id=org_id))


@app.route('/platform/orgs/<int:org_id>/reset-password', methods=['POST'])
def platform_org_reset_password(org_id):
    from liftcore_mail import mail_result_message, send_onboarding_activated_email
    from liftcore_security import password_policy_error
    from models import Organization, User
    from platform_admin import is_admin_host, tenant_login_url

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        abort(404)
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)
    password = generate_password(14)
    pwd_err = password_policy_error(password)
    if pwd_err:
        session['plat_notice'] = pwd_err
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_org_detail', org_id=org_id))

    prev = getattr(g, '_resolving_default_org', False)
    g._resolving_default_org = True
    try:
        admin = (
            User.query.filter_by(organization_id=org.id, role='admin', is_active=True)  # tenant: platform
            .order_by(User.id.asc())
            .first()
        )
        if not admin:
            session['plat_notice'] = 'لا يوجد مستخدم admin لهذه المؤسسة.'
            session['plat_notice_type'] = 'warn'
            return redirect(url_for('platform_org_detail', org_id=org_id))
        admin.password_hash = hash_password(password)
        db.session.commit()
    finally:
        g._resolving_default_org = prev

    to_email = (admin.email or org.admin_email or '').strip()
    login_url = tenant_login_url(org.slug)
    session['plat_issued_password'] = password
    session['plat_issued_to'] = to_email
    if to_email:
        mail_result = send_onboarding_activated_email(
            to_email=to_email,
            company_name=org.name,
            admin_name=admin.full_name or admin.username,
            slug=org.slug,
            username=admin.username,
            password=password,
            login_url=login_url,
            plan=org.plan or 'basic',
        )
        notice, ntype = mail_result_message(mail_result, to_email=to_email)
        session['plat_notice'] = notice
        session['plat_notice_type'] = ntype
    else:
        session['plat_notice'] = 'تم توليد كلمة المرور، لكن لا يوجد بريد للإرسال.'
        session['plat_notice_type'] = 'warn'
    return redirect(url_for('platform_org_detail', org_id=org_id))


@app.route('/platform/billing')
def platform_billing():
    from platform_admin import is_admin_host
    from platform_billing import billing_overview

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))
    overview = billing_overview(300)
    return render_template(
        'platform/billing.html',
        nav='billing',
        rows=overview['rows'],
        stats=overview['stats'],
        plan_prices=overview['plan_prices'],
        plan_prices_yearly=overview['plan_prices_yearly'],
        notice=session.pop('plat_notice', None),
        notice_type=session.pop('plat_notice_type', None),
    )


@app.route('/platform/orgs/<int:org_id>/subscription', methods=['POST'])
def platform_org_subscription(org_id):
    from datetime import datetime as dt

    from models import Organization
    from platform_admin import is_admin_host
    from platform_billing import set_subscription

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        abort(404)
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)

    amount_raw = (request.form.get('billing_amount') or '').strip()
    clear_amount = amount_raw == ''
    amount = None
    if not clear_amount:
        try:
            amount = float(amount_raw)
        except ValueError:
            session['plat_notice'] = 'مبلغ الاشتراك غير صالح.'
            session['plat_notice_type'] = 'warn'
            return redirect(url_for('platform_org_detail', org_id=org_id))

    period_end = None
    period_raw = (request.form.get('period_end') or '').strip()
    if period_raw:
        try:
            period_end = dt.strptime(period_raw[:10], '%Y-%m-%d')
        except ValueError:
            session['plat_notice'] = 'تاريخ نهاية الفترة غير صالح.'
            session['plat_notice_type'] = 'warn'
            return redirect(url_for('platform_org_detail', org_id=org_id))

    result = set_subscription(
        org,
        plan=request.form.get('plan'),
        cycle=request.form.get('billing_cycle'),
        amount=amount,
        clear_amount=clear_amount,
        period_end=period_end,
        billing_status=request.form.get('billing_status'),
        billing_notes=request.form.get('billing_notes'),
    )
    if result.get('ok'):
        session['plat_notice'] = 'تم حفظ إعدادات الاشتراك.'
        session['plat_notice_type'] = 'ok'
    else:
        session['plat_notice'] = ' — '.join(result.get('errors') or ['فشل الحفظ.'])
        session['plat_notice_type'] = 'warn'
    return redirect(url_for('platform_org_detail', org_id=org_id))


@app.route('/platform/orgs/<int:org_id>/addons', methods=['POST'])
def platform_org_addon_add(org_id):
    from models import Organization
    from platform_admin import is_admin_host
    from entitlements import upsert_org_addon

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        abort(404)
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)
    try:
        qty = int(request.form.get('quantity') or 1)
    except (TypeError, ValueError):
        qty = 1
    price_raw = (request.form.get('unit_price_monthly') or '').strip()
    unit_price = None
    if price_raw:
        try:
            unit_price = float(price_raw)
        except ValueError:
            session['plat_notice'] = 'سعر الإضافة غير صالح.'
            session['plat_notice_type'] = 'warn'
            return redirect(url_for('platform_org_detail', org_id=org_id))
    result = upsert_org_addon(
        org,
        addon_key=request.form.get('addon_key') or '',
        quantity=qty,
        note=request.form.get('note') or '',
        unit_price_monthly=unit_price,
        created_by_user_id=user.id,
    )
    if result.get('ok'):
        session['plat_notice'] = 'تم إضافة/تحديث الإضافة على باقة العميل.'
        session['plat_notice_type'] = 'ok'
    else:
        session['plat_notice'] = ' — '.join(result.get('errors') or ['فشل حفظ الإضافة.'])
        session['plat_notice_type'] = 'warn'
    return redirect(url_for('platform_org_detail', org_id=org_id))


@app.route('/platform/orgs/<int:org_id>/addons/<int:addon_id>/cancel', methods=['POST'])
def platform_org_addon_cancel(org_id, addon_id):
    from models import Organization
    from platform_admin import is_admin_host
    from entitlements import cancel_org_addon

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        abort(404)
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)
    result = cancel_org_addon(org, addon_id)
    if result.get('ok'):
        session['plat_notice'] = 'تم إلغاء الإضافة.'
        session['plat_notice_type'] = 'ok'
    else:
        session['plat_notice'] = ' — '.join(result.get('errors') or ['تعذّر الإلغاء.'])
        session['plat_notice_type'] = 'warn'
    return redirect(url_for('platform_org_detail', org_id=org_id))


@app.route('/platform/orgs/<int:org_id>/limits', methods=['POST'])
def platform_org_limits(org_id):
    from models import Organization
    from platform_admin import is_admin_host
    from entitlements import set_limit_overrides

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        abort(404)
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)

    def _opt_int(name):
        raw = (request.form.get(name) or '').strip()
        if raw == '':
            return None
        return int(raw)

    if request.form.get('clear_overrides') == '1':
        result = set_limit_overrides(org, clear=True)
    else:
        try:
            result = set_limit_overrides(
                org,
                elevators=_opt_int('elevators_limit_override'),
                office_users=_opt_int('office_users_limit_override'),
                technicians=_opt_int('technicians_limit_override'),
                storage_gb=_opt_int('storage_gb_limit_override'),
            )
        except ValueError:
            session['plat_notice'] = 'قيم الحدود غير صالحة.'
            session['plat_notice_type'] = 'warn'
            return redirect(url_for('platform_org_detail', org_id=org_id))
    if result.get('ok'):
        session['plat_notice'] = 'تم حفظ تجاوزات الحدود.'
        session['plat_notice_type'] = 'ok'
    else:
        session['plat_notice'] = ' — '.join(result.get('errors') or ['فشل الحفظ.'])
        session['plat_notice_type'] = 'warn'
    return redirect(url_for('platform_org_detail', org_id=org_id))


@app.route('/platform/orgs/<int:org_id>/payment', methods=['POST'])
def platform_org_payment(org_id):
    from models import Organization
    from platform_admin import is_admin_host
    from platform_billing import record_payment

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        abort(404)
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)

    try:
        months = int(request.form.get('months') or 1)
    except (TypeError, ValueError):
        months = 1
    result = record_payment(
        org,
        amount=request.form.get('amount'),
        method=request.form.get('method') or 'transfer',
        reference=request.form.get('reference') or '',
        note=request.form.get('note') or '',
        months=months,
        recorded_by_user_id=user.id,
    )
    if result.get('ok'):
        session['plat_notice'] = 'تم تسجيل الدفعة وتجديد فترة الاشتراك.'
        session['plat_notice_type'] = 'ok'
        try:
            from audit_log import log_audit
            log_audit(
                'platform_payment_recorded',
                organization_id=org.id,
                details={
                    'amount': result['payment'].amount,
                    'months': months,
                    'method': result['payment'].method,
                },
            )
        except Exception:
            app.logger.exception('platform payment audit failed')
    else:
        session['plat_notice'] = ' — '.join(result.get('errors') or ['فشل تسجيل الدفعة.'])
        session['plat_notice_type'] = 'warn'
    return redirect(url_for('platform_org_detail', org_id=org_id))


@app.route('/platform/orgs/<int:org_id>/export')
def platform_org_export(org_id):
    """تنزيل نسخة احتياطية JSON (داخل ZIP) لبيانات العميل على جهاز المشغّل."""
    from flask import Response
    from models import Organization
    from platform_admin import is_admin_host
    from tenant_lifecycle import build_tenant_export_zip

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)
    try:
        data, filename, counts = build_tenant_export_zip(org)
    except Exception:
        app.logger.exception('platform org export failed org_id=%s', org_id)
        session['plat_notice'] = 'فشل تصدير بيانات المؤسسة.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_org_detail', org_id=org_id))
    try:
        from audit_log import log_audit
        log_audit(
            'platform_org_exported',
            organization_id=org.id,
            details={'slug': org.slug, 'counts': counts, 'bytes': len(data)},
        )
    except Exception:
        app.logger.exception('platform export audit failed')
    return Response(
        data,
        mimetype='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-store',
        },
    )


@app.route('/platform/orgs/<int:org_id>/delete', methods=['POST'])
def platform_org_delete(org_id):
    """إلغاء العميل ومسح كل بياناته من المنصة (بعد تصدير اختياري)."""
    from models import Organization
    from platform_admin import is_admin_host
    from tenant_lifecycle import is_protected_operator_org, wipe_tenant

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        abort(404)
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)

    if is_protected_operator_org(org):
        session['plat_notice'] = 'لا يمكن حذف مؤسسة مشغّل المنصة.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_org_detail', org_id=org_id))

    confirm_slug = (request.form.get('confirm_slug') or '').strip().lower()
    confirm_phrase = (request.form.get('confirm_phrase') or '').strip().upper()
    pwd = (request.form.get('admin_password') or request.form.get('password') or '').strip()
    ack = (request.form.get('acknowledge') or '').strip() in ('1', 'on', 'true', 'yes')

    if confirm_slug != (org.slug or '').lower():
        session['plat_notice'] = 'اكتب معرّف المؤسسة (slug) بشكل صحيح للتأكيد.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_org_detail', org_id=org_id))
    if confirm_phrase != 'DELETE':
        session['plat_notice'] = 'اكتب DELETE بالإنجليزية للتأكيد النهائي.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_org_detail', org_id=org_id))
    if not ack:
        session['plat_notice'] = 'يجب الموافقة على أن الحذف نهائي ولا يمكن التراجع عنه.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_org_detail', org_id=org_id))
    if not pwd or not verify_password(user.password_hash, pwd):
        session['plat_notice'] = 'كلمة مرور مشغّل المنصة غير صحيحة — لم يتم الحذف.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_org_detail', org_id=org_id))

    slug = org.slug
    name = org.name
    try:
        result = wipe_tenant(org, keep_users=False, delete_organization=True)
    except ValueError as exc:
        session['plat_notice'] = str(exc)
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_org_detail', org_id=org_id))
    except Exception:
        app.logger.exception('platform org delete failed org_id=%s', org_id)
        session['plat_notice'] = 'فشل حذف المؤسسة — راجع سجلات السيرفر.'
        session['plat_notice_type'] = 'warn'
        return redirect(url_for('platform_org_detail', org_id=org_id))

    try:
        from audit_log import log_audit
        log_audit(
            'platform_org_deleted',
            details={
                'slug': slug,
                'name': name,
                'before': result.get('before'),
                'deleted': result.get('deleted'),
            },
        )
    except Exception:
        app.logger.exception('platform delete audit failed')

    session['plat_notice'] = (
        f'تم إلغاء العميل «{name}» ({slug}) ومسح كل بياناته من قاعدة المنصة.'
    )
    session['plat_notice_type'] = 'ok'
    return redirect(url_for('platform_orgs'))


@app.route('/platform/orgs/<int:org_id>/extend-trial', methods=['POST'])
def platform_org_extend_trial(org_id):
    from models import Organization
    from platform_admin import is_admin_host
    from platform_billing import extend_trial

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        abort(404)
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)
    try:
        days = int(request.form.get('days') or 14)
    except (TypeError, ValueError):
        days = 14
    result = extend_trial(org, days=days)
    if result.get('ok'):
        session['plat_notice'] = f"تم تمديد التجربة حتى {result['trial_ends_at']}."
        session['plat_notice_type'] = 'ok'
    else:
        session['plat_notice'] = 'فشل تمديد التجربة.'
        session['plat_notice_type'] = 'warn'
    return redirect(url_for('platform_org_detail', org_id=org_id))


@app.route('/platform/invites')
def platform_invites():
    from platform_admin import is_admin_host, recent_invites

    if not is_admin_host():
        abort(404)
    user = _require_platform_console_user()
    if not user:
        return redirect(url_for('login'))
    return render_template(
        'platform/invites.html',
        nav='invites',
        invites=recent_invites(100),
        notice=session.pop('plat_notice', None),
        notice_type=session.pop('plat_notice_type', None),
    )


@app.route('/welcome')
def welcome():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if not session.pop('just_logged_in', False):
        return redirect(url_for('home'))
    display_name = session.get('username') or user.full_name or user.username
    return render_template('welcome.html', current_user_name=display_name)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =============================================
# الداشبورد — إحصائيات وتنبيهات ذكية
# =============================================
_DASH_UNPAID_STATUSES = ['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً']


def _count_created_between(model, start, end, date_field='created_at', **filters):
    col = getattr(model, date_field)
    q = tenant_query(model).filter(col >= start, col < end)
    for key, val in filters.items():
        q = q.filter(getattr(model, key) == val)
    return q.count()


def _period_created_delta(model, date_field='created_at', **filters):
    now = datetime.utcnow()
    cur_start = now - timedelta(days=30)
    prev_start = now - timedelta(days=60)
    current = _count_created_between(model, cur_start, now, date_field, **filters)
    previous = _count_created_between(model, prev_start, cur_start, date_field, **filters)
    return current - previous


def _trend_badge(delta, higher_is_good=True, title_ar=None, title_en=None):
    if delta == 0:
        text, css = '0', 'trend-neu'
    elif delta > 0:
        text = f'+{delta}'
        css = 'trend-up' if higher_is_good else 'trend-down'
    else:
        text = str(delta)
        css = 'trend-down' if higher_is_good else 'trend-up'
    default_ar = 'مقارنة آخر 30 يوماً بالـ 30 يوم السابقة'
    default_en = 'Last 30 days vs prior 30 days'
    return {
        'text': text,
        'class': css,
        'delta': delta,
        'title_ar': title_ar or default_ar,
        'title_en': title_en or default_en,
    }


def get_dashboard_trends(today=None):
    """مؤشرات التغيّر على كروت الداشبورد (حقيقية من قاعدة البيانات)."""
    today = today or date.today()
    now = datetime.utcnow()
    cur_start = now - timedelta(days=30)
    prev_start = now - timedelta(days=60)
    yesterday = today - timedelta(days=1)

    def expired_between(d1, d2):
        return tenant_query(Contract).filter(
            Contract.end_date >= d1,
            Contract.end_date < d2,
        ).count()

    exp_this = expired_between(cur_start.date(), today + timedelta(days=1))
    exp_prev = expired_between(prev_start.date(), cur_start.date())

    def unpaid_created(start, end):
        return tenant_query(Invoice).filter(
            Invoice.created_at >= start,
            Invoice.created_at < end,
            Invoice.status.in_(_DASH_UNPAID_STATUSES),
        ).count()

    visits_today = tenant_query(MaintenanceVisit).filter_by(visit_date=today).count()
    visits_yesterday = tenant_query(MaintenanceVisit).filter_by(visit_date=yesterday).count()

    return {
        'customers': _trend_badge(_period_created_delta(Customer)),
        'elevators': _trend_badge(_period_created_delta(Elevator)),
        'contracts': _trend_badge(
            _period_created_delta(Contract, status='نشط'),
            title_ar='عقود نشطة جديدة — آخر 30 يوماً مقارنة بالسابقة',
            title_en='New active contracts vs prior 30 days',
        ),
        'expired_contracts': _trend_badge(
            exp_this - exp_prev,
            higher_is_good=False,
            title_ar='عقود انتهت خلال آخر 30 يوماً مقارنة بالفترة السابقة',
            title_en='Contracts expired in last 30 days vs prior period',
        ),
        'visits_today': _trend_badge(
            visits_today - visits_yesterday,
            title_ar='مقارنة بزيارات أمس',
            title_en='Compared to yesterday\'s visits',
        ),
        'faults_open': _trend_badge(
            _period_created_delta(Fault, date_field='reported_at'),
            higher_is_good=False,
            title_ar='أعطال مُبلَّغ عنها — آخر 30 يوماً مقارنة بالسابقة',
            title_en='New fault reports vs prior 30 days',
        ),
        'unpaid_invoices': _trend_badge(
            unpaid_created(cur_start, now) - unpaid_created(prev_start, cur_start),
            higher_is_good=False,
            title_ar='فواتير غير مدفوعة جديدة — آخر 30 يوماً مقارنة بالسابقة',
            title_en='New unpaid invoices vs prior 30 days',
        ),
        'technicians': _trend_badge(
            _period_created_delta(Technician),
            title_ar='فنيون جدد — آخر 30 يوماً مقارنة بالسابقة',
            title_en='New technicians vs prior 30 days',
        ),
    }


def get_dashboard_stats():
    """تجميع كل أرقام لوحة التحكم والتنبيهات من قاعدة البيانات."""
    today = date.today()
    in_30_days = today + timedelta(days=30)

    from customer_billing import (
        is_receipt_voucher,
        tenant_outstanding_collectible,
    )

    outstanding = tenant_outstanding_collectible(today=today)

    # فواتير ضريبية فقط (بدون سندات قبض) — المتبقي = الإجمالي − المدفوع
    tax_invoices = [
        inv for inv in tenant_query(Invoice).all()
        if not is_receipt_voucher(inv.invoice_type) and not getattr(inv, 'revenue_id', None)
    ]
    total_invoices = sum(_money_round(inv.total) for inv in tax_invoices)
    paid_invoices = sum(
        _money_round(getattr(inv, 'paid_amount', 0) or 0)
        for inv in tax_invoices
    )
    unpaid_total = sum(
        max(_money_round(inv.total) - _money_round(getattr(inv, 'paid_amount', 0) or 0), 0)
        for inv in tax_invoices
        if max(_money_round(inv.total) - _money_round(getattr(inv, 'paid_amount', 0) or 0), 0) > 0.01
    )
    overdue_invoices = [
        inv for inv in tax_invoices
        if inv.due_date and inv.due_date < today
        and max(_money_round(inv.total) - _money_round(getattr(inv, 'paid_amount', 0) or 0), 0) > 0.01
    ]
    overdue_total = sum(
        max(_money_round(inv.total) - _money_round(getattr(inv, 'paid_amount', 0) or 0), 0)
        for inv in overdue_invoices
    )
    overdue_count = len(overdue_invoices)

    expiring_contracts = tenant_query(Contract).filter(
        Contract.status == 'نشط',
        Contract.end_date >= today,
        Contract.end_date <= in_30_days,
    ).order_by(Contract.end_date).all()

    low_stock_items = tenant_query(InventoryItem).filter(
        InventoryItem.min_qty > 0,
        InventoryItem.current_qty < InventoryItem.min_qty,
    ).order_by(InventoryItem.current_qty).all()

    all_contracts_for_status = tenant_query(Contract).all()
    renewed_contract_ids = _annotate_contract_renewals(all_contracts_for_status)
    expired_contracts_count = sum(
        1
        for c in all_contracts_for_status
        if contract_display_status(c, renewed_ids=renewed_contract_ids) == 'منتهي'
    )

    stats = {
        'customers':        tenant_query(Customer).count(),
        'elevators':        tenant_query(Elevator).count(),
        'contracts':        tenant_query(Contract).filter_by(status='نشط').count(),
        'expired_contracts': expired_contracts_count,
        'visits_today':     tenant_query(MaintenanceVisit).filter_by(visit_date=today).count(),
        'visits_done':      tenant_query(MaintenanceVisit).filter_by(status='مكتملة').count(),
        'faults_open':      tenant_query(Fault).filter(
            Fault.status.in_(['مفتوح', 'قيد المعالجة'])
        ).count(),
        'unpaid_invoices':  tenant_query(Invoice).filter(
            Invoice.status.in_(['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً'])
        ).count(),
        'technicians':      tenant_query(Technician).filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).count(),
        'revenue':          round(db.session.query(db.func.sum(Revenue.total)).scalar() or 0, 2),
        'parts_profit':     round(db.session.query(db.func.sum(PartsBilling.profit)).scalar() or 0, 2),
        'total_invoices':   round(total_invoices, 2),
        'paid_invoices':    round(paid_invoices, 2),
        'unpaid_total':     round(unpaid_total, 2),
        'overdue_total':    round(overdue_total, 2),
        'overdue_count':    overdue_count,
        'paid_pct':         round(paid_invoices / total_invoices * 100) if total_invoices else 0,
        'unpaid_pct':       round(unpaid_total / total_invoices * 100) if total_invoices else 0,
        'outstanding_collectible': outstanding['total'],
        'outstanding_count': outstanding['items_count'],
        'outstanding_contracts': outstanding['contracts_count'],
        'outstanding_contracts_total': outstanding['contracts_total'],
    }

    alerts = {
        'expiring_contracts':       expiring_contracts,
        'expiring_contracts_count': len(expiring_contracts),
        'expiring_contracts_names': '، '.join(
            c.customer.name for c in expiring_contracts[:3]
        ) + ('...' if len(expiring_contracts) > 3 else ''),
        'low_stock_items':          low_stock_items,
        'low_stock_count':          len(low_stock_items),
        'low_stock_names':          '، '.join(
            i.name for i in low_stock_items[:3]
        ) + ('...' if len(low_stock_items) > 3 else ''),
    }

    return stats, alerts


@app.route('/dashboard')
def dashboard():
    stats, alerts = get_dashboard_stats()
    trends = get_dashboard_trends()
    return render_template(
        'dashboard.html',
        stats=stats,
        alerts=alerts,
        trends=trends,
    )


UNPAID_INVOICE_STATUSES = ['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً']
PAID_INVOICE_STATUSES = ['مدفوعة', 'مدفوع', 'محصّل']
OPEN_FAULT_STATUSES = ['مفتوح', 'قيد المعالجة']


def _drill_row(cells, *, wa_type=None, wa_id=None):
    row = {'cells': cells}
    if wa_type and wa_id:
        row['wa'] = {'type': wa_type, 'id': wa_id}
    return row


def _invoice_drill_wa(i):
    from operations import invoice_whatsapp_eligible
    if invoice_whatsapp_eligible(i):
        return 'invoice', i.id
    return None, None


@app.route('/api/dashboard/drill/<card_type>')
def api_dashboard_drill(card_type):
    """بيانات تفصيلية لكل كارت في لوحة التحكم."""
    today = date.today()

    if card_type == 'customers':
        rows = [
            [c.code, c.name, c.city or '—', c.district or '—', c.phone or '—', c.status]
            for c in tenant_query(Customer).order_by(Customer.name).all()
        ]
        payload = {
            'title': 'إجمالي العملاء', 'link': '/clients',
            'columns': ['الكود', 'الاسم', 'المدينة', 'الحي', 'الهاتف', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'elevators':
        rows = [
            [e.code, e.customer.name, e.building_name or '—', e.elev_type or '—', e.brand or '—', e.status]
            for e in tenant_query(Elevator).join(Customer).order_by(Elevator.code).all()
        ]
        payload = {
            'title': 'إجمالي المصاعد', 'link': '/elevators',
            'columns': ['الكود', 'العميل', 'المبنى', 'النوع', 'العلامة', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'contracts':
        rows = [
            [c.code, c.customer.name, c.contract_type or '—',
             str(c.start_date), str(c.end_date),
             f'{c.total:,.0f} \u20c1' if c.total else '—', c.status]
            for c in tenant_query(Contract).filter_by(status='نشط').order_by(Contract.end_date).all()
        ]
        payload = {
            'title': 'العقود الفعّالة', 'link': '/contracts',
            'columns': ['الكود', 'العميل', 'النوع', 'البداية', 'النهاية', 'القيمة', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'expired_contracts':
        all_c = tenant_query(Contract).order_by(Contract.end_date.desc()).all()
        renewed_ids = _annotate_contract_renewals(all_c)
        rows = [
            [c.code, c.customer.name if c.customer else '—', c.contract_type or '—',
             str(c.start_date), str(c.end_date),
             contract_display_status(c, renewed_ids=renewed_ids)]
            for c in all_c
            if contract_display_status(c, renewed_ids=renewed_ids) == 'منتهي'
        ]
        payload = {
            'title': 'العقود المنتهية', 'link': '/contracts',
            'columns': ['الكود', 'العميل', 'النوع', 'البداية', 'النهاية', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'visits_today':
        rows = [
            [v.code, v.elevator.customer.name, v.elevator.code,
             v.visit_type or '—', v.visit_time or '—',
             v.technician.name if v.technician else '—', v.status]
            for v in tenant_query(MaintenanceVisit).filter_by(visit_date=today)
            .order_by(MaintenanceVisit.visit_time).all()
        ]
        payload = {
            'title': 'زيارات اليوم', 'link': '/maintenance-visits',
            'columns': ['الكود', 'العميل', 'المصعد', 'النوع', 'الوقت', 'الفني', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'faults_open':
        rows = [
            [f.code, f.elevator.customer.name, f.elevator.code,
             f.fault_type or '—', f.priority or '—',
             f.technician.name if f.technician else 'غير مكلف', f.status]
            for f in tenant_query(Fault).filter(Fault.status.in_(OPEN_FAULT_STATUSES))
            .order_by(Fault.reported_at.desc()).all()
        ]
        payload = {
            'title': 'الأعطال المفتوحة', 'link': '/faults',
            'columns': ['الكود', 'العميل', 'المصعد', 'نوع العطل', 'الأولوية', 'الفني', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'unpaid_invoices':
        invs = (
            db.session.query(Invoice, Customer)
            .outerjoin(Customer, Invoice.customer_id == Customer.id)
            .filter(Invoice.status.in_(UNPAID_INVOICE_STATUSES))
            .order_by(Invoice.due_date)
            .all()
        )
        rows = []
        for i, cust in invs:
            wa_type, wa_id = _invoice_drill_wa(i)
            rows.append(_drill_row(
                [i.code, (cust.name if cust else '—'),
                 str(i.invoice_date), str(i.due_date or '—'),
                 f'{i.total:,.0f} \u20c1' if i.total else '—', i.status],
                wa_type=wa_type, wa_id=wa_id,
            ))
        payload = {
            'title': 'الفواتير غير المدفوعة', 'link': '/invoices',
            'columns': ['الكود', 'العميل', 'التاريخ', 'الاستحقاق', 'الإجمالي', 'الحالة', 'واتساب'],
            'rows': rows,
        }
    elif card_type == 'outstanding_collectible':
        from customer_billing import tenant_outstanding_collectible
        data = tenant_outstanding_collectible(today=today)
        rows = []
        for r in data['rows'][:100]:
            rows.append([
                r['kind'],
                r['code'],
                r['customer'],
                r.get('due_date') or '—',
                f"{r['total']:,.0f} \u20c1",
                f"{r['paid']:,.0f} \u20c1",
                f"{r['remaining']:,.0f} \u20c1",
                r['status'],
            ])
        payload = {
            'title': f"مستحق التحصيل — {data['total']:,.0f} ⃁",
            'link': '/contracts',
            'columns': ['النوع', 'الكود', 'العميل', 'الاستحقاق', 'الإجمالي', 'المدفوع', 'المتبقي', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'technicians':
        rows = [
            [t.code, t.name, t.phone or '—', t.job_title or '—',
             t.specialization or '—', t.city or '—', t.status]
            for t in tenant_query(Technician).filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).order_by(Technician.name).all()
        ]
        payload = {
            'title': 'الفنيون المتاحون', 'link': '/technicians',
            'columns': ['الكود', 'الاسم', 'الهاتف', 'المسمى', 'التخصص', 'المدينة', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'expiring_contracts':
        in_30_days = today + timedelta(days=30)
        rows = [
            [c.code, c.customer.name, c.contract_type or '—',
             str(c.end_date), f'{(c.end_date - today).days} يوم', c.status]
            for c in tenant_query(Contract).filter(
                Contract.status == 'نشط',
                Contract.end_date >= today,
                Contract.end_date <= in_30_days,
            ).order_by(Contract.end_date).all()
        ]
        payload = {
            'title': 'عقود تنتهي خلال 30 يوم', 'link': '/contracts',
            'columns': ['الكود', 'العميل', 'النوع', 'تاريخ الانتهاء', 'المتبقي', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'low_stock':
        rows = [
            [i.code, i.name, i.category or '—',
             f'{i.current_qty:g}', f'{i.min_qty:g}', i.unit or '—', i.order_status]
            for i in tenant_query(InventoryItem).filter(
                InventoryItem.min_qty > 0,
                InventoryItem.current_qty < InventoryItem.min_qty,
            ).order_by(InventoryItem.current_qty).all()
        ]
        payload = {
            'title': 'أصناف تحت الحد الأدنى', 'link': '/inventory',
            'columns': ['الكود', 'الصنف', 'الفئة', 'الكمية', 'الحد الأدنى', 'الوحدة', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'all_invoices':
        invs = (
            db.session.query(Invoice, Customer)
            .outerjoin(Customer, Invoice.customer_id == Customer.id)
            .order_by(Invoice.invoice_date.desc())
            .all()
        )
        rows = []
        for i, cust in invs:
            wa_type, wa_id = _invoice_drill_wa(i)
            rows.append(_drill_row(
                [i.code, cust.name if cust else '—', str(i.invoice_date),
                 f'{i.total:,.0f} \u20c1' if i.total else '—', i.status],
                wa_type=wa_type, wa_id=wa_id,
            ))
        payload = {
            'title': 'إجمالي الفواتير', 'link': '/invoices',
            'columns': ['الكود', 'العميل', 'التاريخ', 'الإجمالي', 'الحالة', 'واتساب'],
            'rows': rows,
        }
    elif card_type == 'paid_invoices':
        invs = (
            db.session.query(Invoice, Customer)
            .outerjoin(Customer, Invoice.customer_id == Customer.id)
            .filter(Invoice.status.in_(PAID_INVOICE_STATUSES))
            .order_by(Invoice.invoice_date.desc())
            .all()
        )
        rows = [
            [i.code, cust.name if cust else '—', str(i.invoice_date),
             f'{i.total:,.0f} \u20c1' if i.total else '—', i.status]
            for i, cust in invs
        ]
        payload = {
            'title': 'الفواتير المحصّلة', 'link': '/invoices',
            'columns': ['الكود', 'العميل', 'التاريخ', 'الإجمالي', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'overdue_invoices':
        invs = (
            db.session.query(Invoice, Customer)
            .outerjoin(Customer, Invoice.customer_id == Customer.id)
            .filter(
                Invoice.due_date < today,
                Invoice.status.in_(UNPAID_INVOICE_STATUSES),
            )
            .order_by(Invoice.due_date)
            .all()
        )
        rows = []
        for i, cust in invs:
            wa_type, wa_id = _invoice_drill_wa(i)
            rows.append(_drill_row(
                [i.code, cust.name if cust else '—', str(i.due_date or '—'),
                 f'{i.total:,.0f} \u20c1' if i.total else '—', i.status],
                wa_type=wa_type, wa_id=wa_id,
            ))
        payload = {
            'title': 'الفواتير المتأخرة', 'link': '/invoices',
            'columns': ['الكود', 'العميل', 'تاريخ الاستحقاق', 'الإجمالي', 'الحالة', 'واتساب'],
            'rows': rows,
        }
    elif card_type == 'all_visits':
        rows = [
            [v.code, v.elevator.customer.name, v.elevator.code,
             str(v.visit_date), v.visit_type or '—',
             v.technician.name if v.technician else '—', v.status]
            for v in tenant_query(MaintenanceVisit).order_by(MaintenanceVisit.visit_date.desc()).limit(50).all()
        ]
        payload = {
            'title': 'زيارات الصيانة', 'link': '/maintenance-visits',
            'columns': ['الكود', 'العميل', 'المصعد', 'التاريخ', 'النوع', 'الفني', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'all_faults':
        rows = [
            [f.code, f.elevator.customer.name, f.elevator.code,
             f.fault_type or '—', f.priority or '—',
             f.technician.name if f.technician else '—', f.status]
            for f in tenant_query(Fault).order_by(Fault.reported_at.desc()).limit(50).all()
        ]
        payload = {
            'title': 'سجل الأعطال', 'link': '/faults',
            'columns': ['الكود', 'العميل', 'المصعد', 'نوع العطل', 'الأولوية', 'الفني', 'الحالة'],
            'rows': rows,
        }
    else:
        return jsonify({'error': 'نوع الكارت غير معروف'}), 404

    return jsonify({
        'title': payload['title'],
        'link': payload['link'],
        'columns': payload['columns'],
        'rows': payload['rows'],
        'count': len(payload['rows']),
    })


# =============================================
# العملاء
# =============================================
@app.route('/clients')
def clients():
    from sqlalchemy.orm import joinedload

    client_scope = (request.args.get('scope') or '').strip().lower()
    if client_scope not in ('maintenance', 'installation'):
        client_scope = ''
    customers = (
        tenant_query(Customer)
        .options(joinedload(Customer.elevators), joinedload(Customer.contracts))
        .order_by(Customer.id.desc())
        .all()
    )
    return render_template(
        'clients.html',
        customers=customers,
        customers_js=[client_to_js_dict(c) for c in customers],
        next_client_code=next_code(Customer, 'C-', digits=4),
        client_scope=client_scope,
        clients_page_title=(
            'عملاء الصيانة' if client_scope == 'maintenance'
            else 'عملاء التركيبات' if client_scope == 'installation'
            else 'العملاء'
        ),
    )


@app.after_request
def _clients_page_no_cache(response):
    if request.path.rstrip('/') == '/clients':
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
    return response


@app.route('/clients/template')
def clients_import_template():
    """تحميل نموذج استيراد العملاء (عربي أو إنجليزي حسب لغة الواجهة)."""
    lang = request.args.get('lang')
    if lang not in ('ar', 'en'):
        lang = resolve_user_language(getattr(g, 'auth_user', None))
    basename = 'clients_template_en.xlsx' if lang == 'en' else 'clients_template.xlsx'
    download_name = 'clients_import_template_en.xlsx' if lang == 'en' else 'clients_import_template.xlsx'
    path = os.path.join(app.root_path, 'static', 'templates', basename)
    if not os.path.isfile(path):
        script = os.path.join(app.root_path, 'scripts', 'build_clients_template.py')
        if os.path.isfile(script):
            import importlib.util
            spec = importlib.util.spec_from_file_location('build_clients_template', script)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.build_xlsx(path, lang=lang)
        if not os.path.isfile(path):
            abort(404)
    return send_from_directory(
        os.path.dirname(path),
        os.path.basename(path),
        as_attachment=True,
        download_name=download_name,
    )


@app.route('/clients/import', methods=['POST'])
def clients_import():
    """استيراد عملاء بالجملة (JSON) — يُرجع عدد النجاح/الفشل مع الأخطاء."""
    payload = request.get_json(silent=True) or {}
    rows = payload.get('rows')
    if not isinstance(rows, list) or not rows:
        return jsonify({'error': 'لا توجد سجلات للاستيراد'}), 400
    if len(rows) > 500:
        return jsonify({'error': 'الحد الأقصى 500 سجل في المرة الواحدة'}), 400
    from client_bulk_import import import_customer_rows

    result = import_customer_rows(rows)
    return jsonify(result)


@app.route('/clients/import-addresses', methods=['POST'])
def clients_import_addresses():
    """تحديث عناوين عملاء موجودين من Excel + إحداثيات للخريطة."""
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'error': 'لم يُرفَع ملف Excel'}), 400
    if not upload.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'الملف يجب أن يكون .xlsx'}), 400

    dry_run = request.form.get('dry_run') == '1'
    # افتراضي الواجهة: بدون geocode لتفادي timeout nginx عند مئات الصفوف
    # مرّر geocode=1 لتفعيل تحديد المواقع
    if 'no_geocode' in request.form:
        no_geocode = request.form.get('no_geocode') == '1'
    elif 'geocode' in request.form:
        no_geocode = request.form.get('geocode') != '1'
    else:
        no_geocode = True

    try:
        from client_address_import import import_client_addresses_file

        result = import_client_addresses_file(
            upload.read(),
            dry_run=dry_run,
            no_geocode=no_geocode,
            db_session=None if dry_run else db.session,
        )
        return jsonify(result)
    except ImportError:
        return jsonify({'error': 'مكتبة openpyxl غير مثبتة على السيرفر'}), 500
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('clients import-addresses failed')
        return jsonify({'error': f'فشل الاستيراد: {exc}'}), 500


def _client_dir(client_id):
    path = os.path.join(CLIENT_UPLOAD_ROOT, str(client_id))
    os.makedirs(path, exist_ok=True)
    return path


def _save_client_building_photo(customer, file_storage):
    if not file_storage or not file_storage.filename:
        return None
    if not _ext_ok(file_storage.filename, ALLOWED_CLIENT_PHOTO_EXT):
        return 'صيغة صورة المبنى غير مدعومة — استخدم JPG أو PNG أو WEBP'
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    folder = _client_dir(customer.id)
    for old in os.listdir(folder):
        if old.startswith('building.'):
            try:
                os.remove(os.path.join(folder, old))
            except OSError:
                pass
    filename = f'building.{ext}'
    file_storage.save(os.path.join(folder, filename))
    customer.building_photo_path = f'uploads/clients/{customer.id}/{filename}'
    return None


def _delete_client_building_photo(customer):
    if not customer.building_photo_path:
        return
    folder = _client_dir(customer.id)
    if os.path.isdir(folder):
        for old in os.listdir(folder):
            if old.startswith('building.'):
                try:
                    os.remove(os.path.join(folder, old))
                except OSError:
                    pass
    customer.building_photo_path = None


def default_building_photo_url():
    """شعار LiftCore الافتراضي عند عدم رفع صورة مبنى."""
    for name in (LIFTCORE_PRODUCT_LOGO, 'logo.png'):
        if os.path.isfile(os.path.join(app.static_folder, name)):
            return url_for('static', filename=name)
    return url_for('static', filename='logo.png')


def _customer_location_payload(customer):
    return {
        'id': customer.id,
        'code': customer.code,
        'name': customer.name,
        'address': customer.address or '',
        'city': customer.city or '',
        'district': customer.district or '',
        'lat': customer.lat or '',
        'lng': customer.lng or '',
        'maps_url': customer.maps_url or '',
        'building_photo_url': _static_upload_url(customer.building_photo_path),
        'has_building_photo': bool(customer.building_photo_path),
        'default_building_photo_url': default_building_photo_url(),
        'phone': customer.phone or '',
    }


@app.route('/api/customers/<int:customer_id>/location', methods=['GET', 'POST'])
def api_customer_location(customer_id):
    customer = tenant_get_or_404(Customer, customer_id)
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        lat = data.get('lat')
        lng = data.get('lng')
        if lat is not None and lng is not None:
            customer.lat = str(lat)
            customer.lng = str(lng)
        if data.get('maps_url'):
            customer.maps_url = data['maps_url']
        db.session.commit()
        return jsonify({'ok': True, **_customer_location_payload(customer)})
    return jsonify(_customer_location_payload(customer))


@app.route('/api/customers/<int:customer_id>/geocode', methods=['POST'])
def api_customer_geocode(customer_id):
    from geocode import geocode_customer

    customer = tenant_get_or_404(Customer, customer_id)
    ok = geocode_customer(customer, delay=0)
    db.session.commit()
    return jsonify({'ok': ok, **_customer_location_payload(customer)})


@app.route('/api/customers/<int:customer_id>/profile')
def api_customer_profile(customer_id):
    contract_id = request.args.get('contract_id', type=int)
    return jsonify(build_customer_profile(customer_id, contract_id))


@app.route('/api/customers/<int:customer_id>/invoicable-revenues')
def api_customer_invoicable_revenues(customer_id):
    from customer_billing import customer_invoicable_revenues

    tenant_get_or_404(Customer, customer_id)
    return jsonify({
        'customer_id': customer_id,
        'operations': customer_invoicable_revenues(customer_id),
    })


@app.route('/api/revenues/uncollected-ops')
def api_revenues_uncollected_ops():
    from customer_billing import tenant_uncollected_ops

    raw_cid = (request.args.get('customer_id') or '').strip()
    customer_id = int(raw_cid) if raw_cid.isdigit() else None
    if customer_id:
        tenant_get_or_404(Customer, customer_id)
    ops = tenant_uncollected_ops(customer_id=customer_id)
    return jsonify({
        'customer_id': customer_id,
        'count': len(ops),
        'remaining_total': round(sum(float(op.get('remaining') or 0) for op in ops), 2),
        'operations': ops,
    })


@app.route('/api/customers/<int:customer_id>/uncollected-ops')
def api_customer_uncollected_ops(customer_id):
    from customer_billing import customer_uncollected_ops

    tenant_get_or_404(Customer, customer_id)
    ops = customer_uncollected_ops(customer_id)
    return jsonify({
        'customer_id': customer_id,
        'operations': ops,
    })


@app.route('/api/customers/<int:customer_id>/billable-ops')
def api_customer_billable_ops(customer_id):
    from customer_billing import customer_billable_ops

    tenant_get_or_404(Customer, customer_id)
    return jsonify({
        'customer_id': customer_id,
        'operations': customer_billable_ops(customer_id),
    })


@app.route('/api/customers/<int:customer_id>/statement')
def api_customer_statement(customer_id):
    from customer_billing import build_customer_statement

    return jsonify(build_customer_statement(customer_id))


def _coords_from_customer(cust):
    if not cust or not cust.lat or not cust.lng:
        return None
    try:
        return float(cust.lat), float(cust.lng)
    except (TypeError, ValueError):
        return None


def _visits_js_list(visits):
    from checklist_templates import parse_report_json, report_completion_stats, checklist_flagged_items, checklist_all_ok
    from technician_assignments import (
        _ids_from_rows,
        _names_from_rows,
        _payload_from_rows,
        visit_technician_rows_by_visit_ids,
    )

    visit_ids = [v.id for v in visits]
    tech_map = visit_technician_rows_by_visit_ids(visit_ids)
    rows = []
    for v in visits:
        elev = v.elevator
        cust = elev.customer if elev else None
        linked = getattr(v, 'linked_fault', None)
        tech_rows = tech_map.get(v.id) or []
        tech_ids = _ids_from_rows(tech_rows) or ([v.technician_id] if v.technician_id else [])
        if tech_rows:
            tech_label = _names_from_rows(tech_rows)
        elif v.technician:
            tech_label = v.technician.name
        else:
            tech_label = '—'
        saved = parse_report_json(v.checklist_json) if (v.checklist_json or '').strip() else {}
        stats = report_completion_stats(saved, v.checklist_template_key) if saved else {'filled': 0, 'total': 0, 'percent': 0}
        filled = int(stats.get('filled', 0) or 0)
        rows.append({
            'id': v.id,
            'code': v.code,
            'elevator_id': v.elevator_id,
            'contract_id': v.contract_id,
            'fault_id': v.fault_id,
            'fault_code': linked.code if linked else '',
            'customer_id': cust.id if cust else None,
            'elevator': elev.code if elev else '',
            'building': (elev.building_name if elev else '') or '',
            'customer': cust.name if cust else '',
            'customer_name_en': (cust.name_en or '') if cust else '',
            'technician': tech_label,
            'tech_id': v.technician_id,
            'tech_ids': tech_ids,
            'technicians': _payload_from_rows(
                tech_rows, fallback_id=v.technician_id, fallback_tech=v.technician,
            ),
            'visit_type': v.visit_type or '',
            'visit_date': str(v.visit_date or ''),
            'plan_month': v.plan_month or '',
            'visit_time': v.visit_time or '',
            'priority': v.priority or 'عادية',
            'status': v.status or '',
            'completed_at': v.completed_at.strftime('%Y-%m-%d') if v.completed_at else '',
            'works_done': v.works_done or '',
            'observations': v.observations or '',
            'notes': v.notes or '',
            'has_report': bool(saved and filled > 0),
            'report_filled': filled,
            'report_total': int(stats.get('total', 0) or 0),
            'report_flagged_items': checklist_flagged_items(saved, v.checklist_template_key) if saved and filled else [],
            'report_all_ok': checklist_all_ok(saved, v.checklist_template_key) if saved and filled else False,
        })
    return rows


def _fault_registration_parts_lines(fault_id: int):
    from operations import fault_registration_parts_lines
    return fault_registration_parts_lines(fault_id)


def _faults_js_list(faults):
    from operations import fault_registration_parts_lines_map
    from technician_assignments import (
        _ids_from_rows,
        _names_from_rows,
        _payload_from_rows,
        fault_technician_rows_by_fault_ids,
    )
    from whatsapp_support import journey_snapshots_for_faults

    fault_ids = [f.id for f in faults]
    wa_map = journey_snapshots_for_faults(list(faults))
    tech_map = fault_technician_rows_by_fault_ids(fault_ids)
    parts_map = fault_registration_parts_lines_map(fault_ids)
    rows = []
    for f in faults:
        elev = f.elevator
        cust = elev.customer if elev else None
        linked = getattr(f, 'linked_visit', None)
        wa = wa_map.get(f.id) or {}
        tech_rows = tech_map.get(f.id) or []
        tech_ids = _ids_from_rows(tech_rows) or ([f.technician_id] if f.technician_id else [])
        if tech_rows:
            tech_label = _names_from_rows(tech_rows)
        elif f.technician:
            tech_label = f.technician.name
        else:
            tech_label = '—'
        rows.append({
            'id': f.id,
            'code': f.code,
            'elevator_id': f.elevator_id,
            'elevator': elev.code if elev else '',
            'customer': cust.name if cust else '',
            'customer_name_en': (cust.name_en or '') if cust else '',
            'customer_id': cust.id if cust else None,
            'tech_id': f.technician_id,
            'tech_ids': tech_ids,
            'technician': tech_label,
            'technicians': _payload_from_rows(
                tech_rows, fallback_id=f.technician_id, fallback_tech=f.technician,
            ),
            'fault_type': f.fault_type or '',
            'description': f.description or '',
            'client_report': f.client_report or f.description or '',
            'priority': f.priority or 'عادية',
            'reported_at': f.reported_at.strftime('%Y-%m-%d') if f.reported_at else '',
            'reported_at_local': f.reported_at.strftime('%Y-%m-%dT%H:%M') if f.reported_at else '',
            'response_time': f.response_time or '—',
            'status': f.status or '',
            'resolution': f.resolution or '',
            'billed': bool(f.billed),
            'visit_code': linked.code if linked else '',
            'notes': f.notes or '',
            'reporter_name': f.reporter_name or '',
            'reporter_phone': f.reporter_phone or '',
            'needs_parts': bool(f.needs_parts),
            'parts_lines': parts_map.get(f.id) or [],
            'has_report': bool(f.report_json),
            'wa': wa,
        })
    return rows


def _visit_map_points(visits, today_only=True):
    today = date.today()
    points = []
    for v in visits:
        if today_only and v.visit_date != today:
            continue
        elev = v.elevator
        cust = elev.customer if elev else None
        coords = _coords_from_customer(cust)
        if not coords:
            continue
        points.append({
            'lat': coords[0],
            'lng': coords[1],
            'label': f'{v.code} — {cust.name}',
            'status': v.status or '',
        })
    return points


def _parts_js_list(parts):
    from operations import parts_billing_notes_display

    rows = []
    for p in parts:
        rows.append({
            'id': p.id,
            'code': p.code,
            'customer_id': p.customer_id,
            'contract_id': p.contract_id,
            'customer': p.customer.name if p.customer else '—',
            'customer_name_en': (p.customer.name_en or '') if p.customer else '',
            'contract': p.contract.code if p.contract else '—',
            'elevator': p.elevator.code if p.elevator else '—',
            'technician': p.technician.name if p.technician else '—',
            'tech_id': p.technician_id,
            'billing_date': str(p.billing_date or ''),
            'description': p.description or '',
            'cost_price': p.cost_price or 0,
            'sell_price': p.sell_price or 0,
            'profit': p.profit or 0,
            'payment_note': (getattr(p, 'payment_note', None) or p.payment_method or '').strip(),
            'status': p.status or 'غير محصل',
            'visit_code': p.visit.code if p.visit else '',
            'fault_code': p.fault.code if p.fault else '',
            'notes': parts_billing_notes_display(p.notes),
            'parts_lines': _parts_billing_record_lines(p),
        })
    return rows


def _parts_billing_record_lines(pb):
    from operations import parts_billing_record_lines
    return parts_billing_record_lines(pb)


def _visit_json(v):
    from technician_assignments import visit_technicians_label, visit_technician_ids, visit_technicians_payload

    elev = v.elevator
    fault = tenant_query(Fault).filter_by(id=v.fault_id).first() if v.fault_id else None
    return {
        'id': v.id,
        'code': v.code,
        'fault_id': v.fault_id,
        'fault_code': fault.code if fault else '',
        'customer_id': elev.customer_id if elev else None,
        'customer': elev.customer.name if elev and elev.customer else '',
        'contract_id': v.contract_id,
        'elevator_id': v.elevator_id,
        'elevator': elev.code if elev else '',
        'technician': visit_technicians_label(v),
        'tech_ids': visit_technician_ids(v) or ([v.technician_id] if v.technician_id else []),
        'technicians': visit_technicians_payload(v),
        'visit_type': v.visit_type or '',
        'visit_date': str(v.visit_date or ''),
        'visit_time': v.visit_time or '',
        'priority': v.priority or 'عادية',
        'status': v.status or '',
        'works_done': v.works_done or '',
        'observations': v.observations or '',
        'notes': v.notes or '',
    }


def _fault_json(f):
    from entity_links import fault_parts_link_fields
    from technician_assignments import fault_technicians_label, fault_technician_ids, fault_technicians_payload

    elev = f.elevator
    link = fault_parts_link_fields(f)
    reported = f.reported_at.strftime('%Y-%m-%d') if f.reported_at else ''
    tech_ids = fault_technician_ids(f) or ([f.technician_id] if f.technician_id else [])
    return {
        'id': f.id,
        'code': f.code,
        'visit_id': link['visit_id'],
        'visit_code': link['visit_code'],
        'contract_code': link['contract_code'],
        'billing_date': link['billing_date'],
        'elevator_id': f.elevator_id,
        'elevator': elev.code if elev else '',
        'customer': elev.customer.name if elev and elev.customer else '',
        'customer_id': elev.customer_id if elev else None,
        'technician': fault_technicians_label(f),
        'tech_id': tech_ids[0] if tech_ids else None,
        'tech_ids': tech_ids,
        'technicians': fault_technicians_payload(f),
        'fault_type': f.fault_type or '',
        'description': f.description or '',
        'priority': f.priority or 'عادية',
        'reported_at': reported,
        'response_time': f.response_time or '—',
        'status': f.status or '',
        'resolution': f.resolution or '',
        'billed': bool(f.billed),
        'notes': f.notes or '',
        'parts_lines': _fault_registration_parts_lines(f.id),
    }


def _part_json(p):
    from operations import parts_billing_notes_display

    return {
        'id': p.id,
        'code': p.code,
        'visit_id': p.visit_id,
        'fault_id': p.fault_id,
        'visit_code': p.visit.code if p.visit else '',
        'fault_code': p.fault.code if p.fault else '',
        'customer_id': p.customer_id,
        'contract_id': p.contract_id,
        'customer': p.customer.name if p.customer else '—',
        'contract': p.contract.code if p.contract else '—',
        'elevator': p.elevator.code if p.elevator else '—',
        'technician': p.technician.name if p.technician else '—',
        'billing_date': str(p.billing_date or ''),
        'description': p.description or '',
        'cost_price': p.cost_price or 0,
        'sell_price': p.sell_price or 0,
        'profit': p.profit or 0,
        'payment_note': (getattr(p, 'payment_note', None) or p.payment_method or '').strip(),
        'status': p.status or 'غير محصل',
        'notes': parts_billing_notes_display(p.notes),
    }


def _contract_json(c):
    elev_ids = [ce.elevator_id for ce in c.elevators]
    elev_codes = [
        e.code for e in tenant_query(Elevator).filter(Elevator.id.in_(elev_ids)).all()
    ] if elev_ids else []
    return {
        'id': c.id,
        'code': c.code,
        'customer_id': c.customer_id,
        'customer': c.customer.name if c.customer else '',
        'contract_type': c.contract_type or '',
        'start_date': c.start_date.isoformat() if c.start_date else '',
        'end_date': c.end_date.isoformat() if c.end_date else '',
        'duration': c.duration_months or 0,
        'elevator_ids': elev_ids,
        'elevators': ', '.join(elev_codes) if elev_codes else '—',
        'maint_freq': c.maint_frequency or '',
        'value': c.value or 0,
        'tax_pct': c.tax_pct or 15,
        'tax_amount': c.tax_amount or 0,
        'total': c.total or 0,
        'pay_terms': c.payment_terms or '',
        'paid_amount': contract_paid_total(c.id),
        'inv_status': contract_invoice_status(c),
        'status': contract_display_status(c),
        'due_date': c.due_date.isoformat() if getattr(c, 'due_date', None) else '',
        'notes': c.notes or '',
    }


@app.route('/api/maintenance-visits/<int:visit_id>')
def api_maintenance_visit(visit_id):
    v = tenant_get_or_404(MaintenanceVisit, visit_id)
    return jsonify(_visit_json(v))


@app.route('/api/faults/<int:fault_id>')
def api_fault(fault_id):
    f = tenant_get_or_404(Fault, fault_id)
    return jsonify(_fault_json(f))


@app.route('/api/faults/lookup')
def api_fault_lookup():
    from entity_links import lookup_fault

    code = request.args.get('code', '').strip()
    f = lookup_fault(code)
    if not f:
        return jsonify({'error': 'العطل غير موجود'}), 404
    return jsonify(_fault_json(f))


@app.route('/api/customers/<int:customer_id>/faults')
def api_customer_faults(customer_id):
    from entity_links import fault_parts_link_fields
    from technician_assignments import fault_technician_ids

    tenant_get_or_404(Customer, customer_id)
    faults = (
        tenant_query(Fault).join(Elevator, Fault.elevator_id == Elevator.id)
        .filter(Elevator.customer_id == customer_id)
        .order_by(Fault.reported_at.desc(), Fault.id.desc())
        .all()
    )
    rows = []
    for f in faults:
        elev = f.elevator
        link = fault_parts_link_fields(f)
        desc = (f.client_report or f.description or f.fault_type or '').strip()
        if len(desc) > 100:
            desc = desc[:97] + '...'
        tech_ids = fault_technician_ids(f) or ([f.technician_id] if f.technician_id else [])
        rows.append({
            'id': f.id,
            'code': f.code,
            'fault_type': f.fault_type or '',
            'description': desc,
            'status': f.status or '',
            'elevator': elev.code if elev else '',
            'visit_code': link['visit_code'],
            'contract_code': link['contract_code'],
            'billing_date': link['billing_date'],
            'reported_at': f.reported_at.strftime('%Y-%m-%d') if f.reported_at else '',
            'tech_id': tech_ids[0] if tech_ids else None,
            'billed': bool(f.billed),
            'has_parts': tenant_query(PartsBilling).filter_by(fault_id=f.id).count() > 0,
            'needs_parts': bool(f.needs_parts),
        })
    return jsonify({'faults': rows})


@app.route('/api/parts-billing/<int:part_id>')
def api_parts_billing(part_id):
    p = tenant_get_or_404(PartsBilling, part_id)
    return jsonify(_part_json(p))


@app.route('/api/contracts/<int:contract_id>')
def api_contract_detail(contract_id):
    c = tenant_get_or_404(Contract, contract_id)
    return jsonify(_contract_json(c))


@app.route('/clients/add', methods=['POST'])
def client_add():
    from form_validation import customer_name_error

    name_err = customer_name_error(request.form.get('name'))
    if name_err:
        flash(name_err, 'error')
        return redirect(url_for('clients'))
    phone_raw = request.form.get('phone', '')
    phone_err = client_phone_error(phone_raw)
    if phone_err:
        flash(phone_err, 'error')
        return redirect(url_for('clients'))
    phone = format_phone_storage(phone_raw)
    taken, msg = phone_taken(phone)
    if taken:
        flash(msg, 'error')
        return redirect(url_for('clients'))
    wa_raw = request.form.get('phone2', '')
    wa = ''
    if wa_raw:
        wa_err = client_phone_error(wa_raw)
        if wa_err:
            flash('واتساب المسؤول: ' + wa_err, 'error')
            return redirect(url_for('clients'))
        wa = format_phone_storage(wa_raw)
    if wa and phone_key(wa) != phone_key(phone):
        taken2, msg2 = phone_taken(wa)
        if taken2:
            flash(msg2, 'error')
            return redirect(url_for('clients'))
    extra_phones, extra_err = parse_extra_phones_from_request(request.form)
    if extra_err:
        flash(extra_err, 'error')
        return redirect(url_for('clients'))
    for item in extra_phones or []:
        num = item.get('number') or ''
        if phone_key(num) in (phone_key(phone), phone_key(wa) if wa else ''):
            continue
        taken_x, msg_x = phone_taken(num)
        if taken_x:
            flash(msg_x, 'error')
            return redirect(url_for('clients'))
    c = Customer(
        code         = next_code(Customer, 'C-', digits=4),
        name         = request.form['name'],
        name_en      = request.form.get('name_en', ''),
        city         = request.form.get('city',''),
        district     = request.form.get('district',''),
        address      = request.form.get('address',''),
        phone        = phone,
        phone2       = wa,
        extra_phones = serialize_customer_extra_phones(extra_phones),
        email        = request.form.get('email',''),
        contact_person = request.form.get('contact_person',''),
        contact_role   = request.form.get('contact_role',''),
        entity_type    = request.form.get('entity_type', 'فرد') or 'فرد',
        national_id    = request.form.get('national_id',''),
        cr_number      = request.form.get('cr_number',''),
        vat_number     = request.form.get('vat_number',''),
        national_address = request.form.get('national_address',''),
        status       = _client_account_status(request.form.get('status', 'نشط')),
        notes        = request.form.get('notes',''),
        lat          = request.form.get('lat',''),
        lng          = request.form.get('lng',''),
        maps_url     = request.form.get('maps_url',''),
    )
    assign_organization(c)
    db.session.add(c)
    db.session.flush()
    photo_err = _save_client_building_photo(c, request.files.get('building_photo'))
    db.session.commit()
    if photo_err:
        flash(photo_err, 'error')
    return redirect(url_for('clients', focus=c.id))

@app.route('/clients/edit/<int:id>', methods=['POST'])
def client_edit(id):
    from form_validation import customer_name_error

    c = tenant_get_or_404(Customer, id)
    name_err = customer_name_error(request.form.get('name'), customer_id=c.id)
    if name_err:
        flash(name_err, 'error')
        return redirect(url_for('clients'))
    phone_raw = request.form.get('phone', '')
    phone_err = client_phone_error(phone_raw)
    if phone_err:
        flash(phone_err, 'error')
        return redirect(url_for('clients'))
    phone = format_phone_storage(phone_raw)
    taken, msg = phone_taken(phone, customer_id=c.id)
    if taken:
        flash(msg, 'error')
        return redirect(url_for('clients'))
    wa_raw = request.form.get('phone2', '')
    wa = ''
    if wa_raw:
        wa_err = client_phone_error(wa_raw)
        if wa_err:
            flash('واتساب المسؤول: ' + wa_err, 'error')
            return redirect(url_for('clients'))
        wa = format_phone_storage(wa_raw)
    if wa and phone_key(wa) != phone_key(phone):
        taken2, msg2 = phone_taken(wa, customer_id=c.id)
        if taken2:
            flash(msg2, 'error')
            return redirect(url_for('clients'))
    extra_phones, extra_err = parse_extra_phones_from_request(request.form)
    if extra_err:
        flash(extra_err, 'error')
        return redirect(url_for('clients'))
    for item in extra_phones or []:
        num = item.get('number') or ''
        if phone_key(num) in (phone_key(phone), phone_key(wa) if wa else ''):
            continue
        taken_x, msg_x = phone_taken(num, customer_id=c.id)
        if taken_x:
            flash(msg_x, 'error')
            return redirect(url_for('clients'))
    c.name           = request.form['name']
    c.name_en        = request.form.get('name_en', '')
    c.city           = request.form.get('city','')
    c.district       = request.form.get('district','')
    c.address        = request.form.get('address','')
    c.phone          = phone
    c.phone2         = wa
    c.extra_phones   = serialize_customer_extra_phones(extra_phones)
    c.email          = request.form.get('email','')
    c.contact_person = request.form.get('contact_person','')
    c.status = _client_account_status(request.form.get('status', 'نشط'))
    c.notes          = request.form.get('notes','')
    c.contact_role   = request.form.get('contact_role','')
    c.entity_type    = request.form.get('entity_type', 'فرد') or 'فرد'
    c.national_id    = request.form.get('national_id','')
    c.cr_number      = request.form.get('cr_number','')
    c.vat_number     = request.form.get('vat_number','')
    c.national_address = request.form.get('national_address','')
    c.lat            = request.form.get('lat','')
    c.lng            = request.form.get('lng','')
    c.maps_url       = request.form.get('maps_url','')
    sync_customer_from_elevators(c)
    upload = request.files.get('building_photo')
    if upload and upload.filename:
        photo_err = _save_client_building_photo(c, upload)
    elif request.form.get('delete_building_photo') == '1':
        photo_err = 'حذف صورة المبنى متاح لمدير النظام عبر زر حذف المرفق فقط'
    else:
        photo_err = None
    db.session.commit()
    if photo_err:
        flash(photo_err, 'error')
    return redirect(url_for('clients', focus=c.id))


@app.route('/clients/<int:id>/remove-building-photo', methods=['POST'])
def client_remove_building_photo(id):
    """حذف صورة مبنى العميل — مدير النظام فقط."""
    err = enforce_admin_attachment_delete(json_response=True)
    if err:
        return err
    c = tenant_get_or_404(Customer, id)
    if not c.building_photo_path:
        return jsonify({'ok': True, 'removed': False, 'message': 'لا يوجد مرفق'})
    _delete_client_building_photo(c)
    db.session.commit()
    return jsonify({'ok': True, 'removed': True, 'id': c.id})


@app.route('/clients/delete/<int:id>', methods=['POST'])
def client_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    c = tenant_get_or_404(Customer, id)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('clients'))

@app.route('/api/clients')
def api_clients():
    customers = tenant_query(Customer).all()
    return jsonify([{'id':c.id,'code':c.code,'name':c.name,'city':c.city} for c in customers])


@app.route('/api/clients/create', methods=['POST'])
def api_clients_quick():
    """إنشاء عميل سريع من شاشات المبيعات (تركيب / صيانة)."""
    from form_validation import customer_name_error

    data = request.get_json(silent=True) or request.form
    name_err = customer_name_error(data.get('name'))
    if name_err:
        return jsonify(ok=False, error=name_err), 400
    phone_raw = data.get('phone') or ''
    phone_err = client_phone_error(phone_raw)
    if phone_err:
        return jsonify(ok=False, error=phone_err), 400
    phone = format_phone_storage(phone_raw)
    taken, msg = phone_taken(phone)
    if taken:
        return jsonify(ok=False, error=msg), 400

    wa_raw = (data.get('phone2') or '').strip()
    wa = ''
    if wa_raw:
        wa_err = client_phone_error(wa_raw)
        if wa_err:
            return jsonify(ok=False, error='واتساب: ' + wa_err), 400
        wa = format_phone_storage(wa_raw)
        if phone_key(wa) != phone_key(phone):
            taken2, msg2 = phone_taken(wa)
            if taken2:
                return jsonify(ok=False, error=msg2), 400

    city = (data.get('city') or '').strip() or 'مكة المكرمة'
    c = Customer(
        code=next_code(Customer, 'C-', digits=4),
        name=(data.get('name') or '').strip(),
        city=city,
        district=(data.get('district') or '').strip(),
        address=(data.get('address') or '').strip(),
        phone=phone,
        phone2=wa,
        email=(data.get('email') or '').strip(),
        contact_person=(data.get('contact_person') or '').strip(),
        entity_type=(data.get('entity_type') or 'فرد').strip() or 'فرد',
        status='نشط',
    )
    assign_organization(c)
    db.session.add(c)
    db.session.commit()
    return jsonify(
        ok=True,
        customer={
            'id': c.id,
            'code': c.code,
            'name': c.name,
            'phone': c.phone or c.phone2 or '',
            'email': c.email or '',
            'address': c.address or '',
            'address_display': ' — '.join([x for x in [c.city, c.district, c.address] if x]),
            'city': c.city or '',
            'district': c.district or '',
        },
    )

# =============================================
# المصاعد
# =============================================
def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


def _parse_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@app.route('/elevators')
def elevators():
    from sqlalchemy.orm import joinedload

    elevs = (
        tenant_query(Elevator)
        .options(joinedload(Elevator.customer))
        .order_by(Elevator.id.desc())
        .all()
    )
    customers = tenant_query(Customer).order_by(Customer.name).all()
    return render_template(
        'elevators.html',
        elevators=elevs,
        elevators_js=[elevator_to_js_dict(e) for e in elevs],
        customers=customers,
        customers_js=[
            {
                'id': c.id,
                'code': c.code,
                'name': c.name,
                'city': c.city or '',
                'district': c.district or '',
                'lat': c.lat or '',
                'lng': c.lng or '',
                'status': c.status or 'نشط',
            }
            for c in customers
        ],
        next_elevator_code=next_code(Elevator, 'EL-', digits=4),
    )


@app.route('/elevators/template')
def elevators_import_template():
    """تحميل نموذج استيراد المصاعد (عربي أو إنجليزي)."""
    lang = request.args.get('lang')
    if lang not in ('ar', 'en'):
        lang = resolve_user_language(getattr(g, 'auth_user', None))
    basename = 'elevators_template_en.xlsx' if lang == 'en' else 'elevators_template.xlsx'
    download_name = 'elevators_import_template_en.xlsx' if lang == 'en' else 'elevators_import_template.xlsx'
    path = os.path.join(app.root_path, 'static', 'templates', basename)
    if not os.path.isfile(path):
        script = os.path.join(app.root_path, 'scripts', 'build_elevators_template.py')
        if os.path.isfile(script):
            import importlib.util
            spec = importlib.util.spec_from_file_location('build_elevators_template', script)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.build_xlsx(path, lang=lang)
        if not os.path.isfile(path):
            abort(404)
    return send_from_directory(
        os.path.dirname(path),
        os.path.basename(path),
        as_attachment=True,
        download_name=download_name,
    )


@app.route('/elevators/add', methods=['POST'])
def elevator_add():
    from form_validation import elevator_form_error
    from entitlements import assert_capacity

    elev_err = elevator_form_error(request.form, parse_int=_parse_int)
    if elev_err:
        flash(elev_err, 'error')
        return redirect(url_for('elevators'))
    cap = assert_capacity('elevators')
    if not cap.get('ok'):
        flash(cap.get('error') or 'تجاوزت حد المصاعد في الباقة.', 'error')
        return redirect(url_for('elevators'))
    raw_code = (request.form.get('code') or '').strip()
    m_el = re.match(r'EL-(\d+)$', raw_code, re.I)
    if m_el:
        raw_code = f'EL-{int(m_el.group(1)):04d}'
        if tenant_query(Elevator).filter_by(code=raw_code).first():
            raw_code = ''
    e = Elevator(
        code            = raw_code or next_code(Elevator, 'EL-', digits=4),
        customer_id     = request.form['customer_id'],
        building_name   = request.form.get('building_name', ''),
        city            = request.form.get('city', ''),
        district        = request.form.get('district', ''),
        address         = request.form.get('address', ''),
        elev_type       = request.form.get('elev_type', ''),
        brand           = request.form.get('brand', ''),
        model           = request.form.get('model', ''),
        capacity_kg     = _parse_int(request.form.get('capacity_kg')),
        capacity_persons= _parse_int(request.form.get('capacity_persons')),
        floors          = _parse_int(request.form.get('floors')),
        stops           = _parse_int(request.form.get('stops')),
        doors_count     = _parse_int(request.form.get('doors_count')),
        serial_number   = request.form.get('serial_number', ''),
        machine_type    = request.form.get('machine_type', ''),
        door_type       = request.form.get('door_type', ''),
        control_type    = request.form.get('control_type', ''),
        control_drive   = request.form.get('control_drive', ''),
        control_operation = request.form.get('control_operation', ''),
        control_detail  = request.form.get('control_detail', ''),
        install_date    = _parse_date(request.form.get('install_date')),
        warranty_end    = _parse_date(request.form.get('warranty_end')),
        last_maintenance= _parse_date(request.form.get('last_maintenance')),
        next_maintenance= _parse_date(request.form.get('next_maintenance')),
        maint_frequency = request.form.get('maint_frequency', ''),
        status          = request.form.get('status', 'نشط'),
        notes           = request.form.get('notes', ''),
    )
    assign_organization(e)
    db.session.add(e)
    db.session.flush()
    sync_customer_from_elevators(e.customer)
    db.session.commit()
    return redirect(url_for('elevators'))


@app.route('/elevators/edit/<int:id>', methods=['POST'])
def elevator_edit(id):
    from form_validation import elevator_form_error

    elev_err = elevator_form_error(request.form, parse_int=_parse_int)
    if elev_err:
        flash(elev_err, 'error')
        return redirect(url_for('elevators'))
    e = tenant_get_or_404(Elevator, id)
    e.customer_id      = request.form['customer_id']
    e.building_name    = request.form.get('building_name', '')
    e.city             = request.form.get('city', '')
    e.district         = request.form.get('district', '')
    e.address          = request.form.get('address', '')
    e.elev_type        = request.form.get('elev_type', '')
    e.brand            = request.form.get('brand', '')
    e.model            = request.form.get('model', '')
    e.capacity_kg      = _parse_int(request.form.get('capacity_kg'))
    e.capacity_persons = _parse_int(request.form.get('capacity_persons'))
    e.floors           = _parse_int(request.form.get('floors'))
    e.stops            = _parse_int(request.form.get('stops'))
    e.doors_count      = _parse_int(request.form.get('doors_count'))
    e.serial_number    = request.form.get('serial_number', '')
    e.machine_type     = request.form.get('machine_type', '')
    e.door_type        = request.form.get('door_type', '')
    e.control_type     = request.form.get('control_type', '')
    e.control_drive      = request.form.get('control_drive', '')
    e.control_operation = request.form.get('control_operation', '')
    e.control_detail   = request.form.get('control_detail', '')
    e.install_date     = _parse_date(request.form.get('install_date'))
    e.warranty_end     = _parse_date(request.form.get('warranty_end'))
    e.last_maintenance = _parse_date(request.form.get('last_maintenance'))
    e.next_maintenance = _parse_date(request.form.get('next_maintenance'))
    e.maint_frequency  = request.form.get('maint_frequency', '')
    e.status           = request.form.get('status', 'نشط')
    e.notes            = request.form.get('notes', '')
    sync_customer_from_elevators(e.customer)
    db.session.commit()
    return redirect(url_for('elevators'))

@app.route('/elevators/delete/<int:id>', methods=['POST'])
def elevator_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    e = tenant_get_or_404(Elevator, id)
    customer = e.customer
    db.session.delete(e)
    db.session.flush()
    sync_customer_from_elevators(customer)
    db.session.commit()
    return redirect(url_for('elevators'))

@app.route('/api/elevators/<int:customer_id>')
def api_elevators_by_customer(customer_id):
    """مصاعد العميل مع بيان العقد الساري المرتبط مباشرة بالمصعد (إن وجد)."""
    elevs = tenant_query(Elevator).filter_by(customer_id=customer_id).all()
    elev_ids = [e.id for e in elevs]
    active_by_elev = {}
    if elev_ids:
        links = tenant_query(ContractElevator).filter(
            ContractElevator.elevator_id.in_(elev_ids)
        ).all()
        contract_ids = list({lk.contract_id for lk in links})
        contracts = {
            c.id: c
            for c in tenant_query(Contract).filter(Contract.id.in_(contract_ids)).all()
        } if contract_ids else {}
        for lk in links:
            c = contracts.get(lk.contract_id)
            if not c:
                continue
            st = contract_display_status(c)
            if st not in ('نشط', 'على وشك الانتهاء'):
                continue
            prev = active_by_elev.get(lk.elevator_id)
            if not prev or (c.end_date and (not prev.get('_end') or c.end_date > prev['_end'])):
                active_by_elev[lk.elevator_id] = {
                    'id': c.id,
                    'code': c.code or '',
                    'status': st,
                    '_end': c.end_date,
                }
    rows = []
    for e in elevs:
        ac = active_by_elev.get(e.id)
        if ac:
            ac = {'id': ac['id'], 'code': ac['code'], 'status': ac['status']}
        rows.append({
            'id': e.id,
            'code': e.code,
            'building': e.building_name,
            'active_contract': ac,
        })
    return jsonify(rows)

def contract_display_status(contract, today=None, *, renewed_ids=None):
    """حالة العرض: نشط / على وشك الانتهاء / تم تجديده / منتهي / ملغي."""
    today = today or date.today()
    raw = (contract.status or 'نشط').strip()
    if raw in ('ملغي', 'معلق'):
        return 'ملغي'
    if raw in ('تم تجديده', 'مجدد', 'مُجدَّد'):
        return 'تم تجديده'
    cid = getattr(contract, 'id', None)
    is_renewed = False
    if renewed_ids is not None and cid is not None:
        is_renewed = int(cid) in renewed_ids
    elif getattr(contract, '_is_renewed', None) is not None:
        is_renewed = bool(contract._is_renewed)
    if is_renewed:
        return 'تم تجديده'
    if raw == 'منتهي' or (contract.end_date and contract.end_date < today):
        return 'منتهي'
    if raw == 'على وشك الانتهاء':
        return 'على وشك الانتهاء'
    if contract.end_date and raw == 'نشط':
        days_left = (contract.end_date - today).days
        if 0 < days_left <= 30:
            return 'على وشك الانتهاء'
    return 'نشط'


def _annotate_contract_renewals(contracts):
    """يضع _is_renewed ويعيد مجموعة المعرّفات المجدَّدة."""
    from contract_codes import build_superseded_contract_ids

    renewed_ids = build_superseded_contract_ids(contracts)
    for c in contracts or []:
        try:
            c._is_renewed = int(c.id) in renewed_ids
        except Exception:
            pass
    return renewed_ids


def contract_paid_total(contract_id):
    from customer_billing import contract_paid_amount
    return contract_paid_amount(contract_id)


def contract_invoice_status(contract, today=None):
    paid = getattr(contract, 'paid_amount', None)
    if paid is not None:
        return _invoice_status_from_paid(contract, paid, today)
    paid = _money_round(contract_paid_total(contract.id))
    return _invoice_status_from_paid(contract, paid, today)


def sync_contract_invoice_status(contract_id):
    if not contract_id:
        return
    c = tenant_query(Contract).filter_by(id=contract_id).first()
    if c:
        _refresh_contract_billing_cache(c)


def format_money_amount(n):
    """عرض مبالغ بدون كسور عائمة (3000 لا 2999.9999)."""
    n = _money_round(n)
    if n == int(n):
        return f'{int(n):,}'
    return f'{n:,.2f}'


app.jinja_env.globals['contract_display_status'] = contract_display_status
app.jinja_env.globals['contract_invoice_status'] = contract_invoice_status
app.jinja_env.globals['contract_paid_total'] = contract_paid_total
app.jinja_env.globals['format_money_amount'] = format_money_amount
app.jinja_env.globals['money_round'] = _money_round


def customer_primary_contract(customer):
    contracts = (
        tenant_query(Contract).filter_by(customer_id=customer.id)
        .order_by(Contract.end_date.desc())
        .all()
    )
    if not contracts:
        return None
    renewed_ids = _annotate_contract_renewals(contracts)
    for c in contracts:
        if contract_display_status(c, renewed_ids=renewed_ids) in ('نشط', 'على وشك الانتهاء'):
            return c
    return contracts[0]


def _customer_in_period_filter(model, contract, date_field):
    """عناصر مرتبطة بالعقد مباشرة أو ضمن فترة العقد."""
    if not contract:
        return True
    col = getattr(model, date_field)
    return or_(
        model.contract_id == contract.id,
        and_(
            model.contract_id.is_(None),
            col >= contract.start_date,
            col <= contract.end_date,
        ),
    )


def build_customer_profile(customer_id, contract_id=None):
    from customer_billing import customer_uncollected_ops

    customer = tenant_get_or_404(Customer, customer_id)
    if contract_id:
        contract = tenant_query(Contract).filter_by(
            id=contract_id, customer_id=customer_id
        ).first_or_404()
    else:
        contract = customer_primary_contract(customer)

    contracts = (
        tenant_query(Contract).filter_by(customer_id=customer_id)
        .order_by(Contract.start_date.desc())
        .all()
    )

    rev_q = tenant_query(Revenue).filter(
        Revenue.customer_id == customer_id,
        Revenue.status.in_(('محصّل', 'محصل')),
    )
    parts_q = tenant_query(PartsBilling).filter(
        PartsBilling.customer_id == customer_id,
        PartsBilling.status.in_(('مكتملة', 'محصل', 'محصّل')),
    )
    inv_q = tenant_query(Invoice).filter(
        Invoice.customer_id == customer_id,
        Invoice.status.in_(PAID_INVOICE_STATUSES),
    )

    if contract:
        rev_q = rev_q.filter(_customer_in_period_filter(Revenue, contract, 'revenue_date'))
        parts_q = parts_q.filter(_customer_in_period_filter(PartsBilling, contract, 'billing_date'))
        inv_q = inv_q.filter(_customer_in_period_filter(Invoice, contract, 'invoice_date'))

    revenues = rev_q.order_by(Revenue.revenue_date.desc()).all()
    parts = parts_q.order_by(PartsBilling.billing_date.desc()).all()
    invoices = inv_q.order_by(Invoice.invoice_date.desc()).all()

    from customer_billing import customer_financial_totals

    fin = customer_financial_totals(revenues, parts, invoices)
    contract_payments = fin['contract_payments']
    parts_payments = fin['parts_payments']
    other_payments = fin['other_payments']
    total_paid = fin['total_paid']
    invoice_extra = fin['invoice_extra']

    contract_value = contract.total if contract else 0
    # المتبقي من حساب العقد (إيرادات فقط — بدون تكرار سند القبض)
    if contract:
        from customer_billing import contract_paid_amount as _cpa
        paid_on_contract = _cpa(contract.id)
        contract_payments = paid_on_contract
        balance = max(_money_round(contract_value) - paid_on_contract, 0)
    else:
        balance = 0

    visit_q = tenant_query(MaintenanceVisit).join(Elevator).filter(
        Elevator.customer_id == customer_id
    )
    fault_q = tenant_query(Fault).join(Elevator).filter(
        Elevator.customer_id == customer_id
    )
    if contract:
        visit_q = visit_q.filter(
            MaintenanceVisit.visit_date >= contract.start_date,
            MaintenanceVisit.visit_date <= contract.end_date,
        )
        fault_q = fault_q.filter(
            db.func.date(Fault.reported_at) >= contract.start_date,
            db.func.date(Fault.reported_at) <= contract.end_date,
        )

    visits = visit_q.order_by(MaintenanceVisit.visit_date.desc()).limit(50).all()
    faults = fault_q.order_by(Fault.reported_at.desc()).limit(50).all()

    timeline = []
    for r in revenues:
        timeline.append({
            'date': str(r.revenue_date or ''),
            'type': 'إيراد',
            'entity_type': 'revenue',
            'entity_id': r.id,
            'code': r.code,
            'title': r.revenue_type or 'إيراد',
            'amount': r.total or 0,
            'status': r.status or '',
            'detail': r.payment_method or '',
        })
    for p in parts:
        timeline.append({
            'date': str(p.billing_date or ''),
            'type': 'قطع غيار',
            'entity_type': 'part',
            'entity_id': p.id,
            'code': p.code,
            'title': p.description or 'تركيب قطع غيار',
            'amount': p.sell_price or 0,
            'status': p.status or '',
            'detail': p.elevator.code if p.elevator else '',
        })
    for i in invoice_extra:
        timeline.append({
            'date': str(i.invoice_date or ''),
            'type': 'فاتورة',
            'entity_type': 'invoice',
            'entity_id': i.id,
            'code': i.code,
            'title': i.description or i.invoice_type or 'فاتورة',
            'amount': i.total or 0,
            'status': i.status or '',
            'detail': i.payment_method or '',
        })
    for v in visits:
        timeline.append({
            'date': str(v.visit_date or ''),
            'type': 'صيانة',
            'entity_type': 'visit',
            'entity_id': v.id,
            'code': v.code,
            'title': v.visit_type or 'زيارة صيانة',
            'amount': 0,
            'status': v.status or '',
            'detail': v.elevator.code if v.elevator else '',
        })
    for f in faults:
        reported = f.reported_at.date() if f.reported_at else None
        timeline.append({
            'date': str(reported or ''),
            'type': 'عطل',
            'entity_type': 'fault',
            'entity_id': f.id,
            'code': f.code,
            'title': f.fault_type or 'عطل',
            'amount': 0,
            'status': f.status or '',
            'detail': f.elevator.code if f.elevator else '',
        })

    timeline.sort(key=lambda x: x['date'], reverse=True)

    sections = {
        'contracts': [{
            'id': ct.id,
            'code': ct.code,
            'date': str(ct.start_date or ''),
            'title': ct.contract_type or 'عقد',
            'status': contract_display_status(ct),
            'detail': str(ct.end_date or ''),
            'amount': ct.total or 0,
        } for ct in contracts],
        'visits': [{
            'id': v.id,
            'code': v.code,
            'date': str(v.visit_date or ''),
            'title': v.visit_type or 'زيارة صيانة',
            'status': v.status or '',
            'detail': v.elevator.code if v.elevator else '',
            'amount': 0,
        } for v in visits],
        'faults': [{
            'id': f.id,
            'code': f.code,
            'date': str(f.reported_at.date() if f.reported_at else ''),
            'title': f.fault_type or 'عطل',
            'status': f.status or '',
            'detail': f.elevator.code if f.elevator else '',
            'amount': 0,
        } for f in faults],
        'parts': [{
            'id': p.id,
            'code': p.code,
            'date': str(p.billing_date or ''),
            'title': p.description or 'تركيب قطع غيار',
            'status': p.status or '',
            'detail': ' / '.join(filter(None, [
                p.visit.code if p.visit else '',
                p.fault.code if p.fault else '',
                p.elevator.code if p.elevator else '',
            ])),
            'amount': p.sell_price or 0,
        } for p in parts],
    }

    return {
        'customer': {
            'id': customer.id,
            'code': customer.code,
            'name': customer.name,
            'city': customer.city or '',
            'phone': customer.phone or '',
            'status': _client_account_status(customer.status),
        },
        'contract': {
            'id': contract.id,
            'code': contract.code,
            'type': contract.contract_type or '',
            'start': str(contract.start_date or ''),
            'end': str(contract.end_date or ''),
            'total': contract.total or 0,
            'status': contract_display_status(contract),
        } if contract else None,
        'contracts': [{
            'id': ct.id,
            'code': ct.code,
            'type': ct.contract_type or '',
            'start': str(ct.start_date or ''),
            'end': str(ct.end_date or ''),
            'total': ct.total or 0,
            'status': contract_display_status(ct),
        } for ct in contracts],
        'financial': {
            'contract_value': contract_value,
            'contract_payments': round(contract_payments, 2),
            'parts_payments': round(parts_payments, 2),
            'other_payments': round(other_payments, 2),
            'total_paid': round(total_paid, 2),
            'balance': round(balance, 2),
            'outstanding_total': round(
                sum(op['remaining'] for op in customer_uncollected_ops(customer_id)), 2
            ),
        },
        'timeline': timeline[:80],
        'sections': sections,
        'counts': {
            'revenues': len(revenues),
            'parts': len(parts),
            'invoices': len(invoice_extra),
            'visits': len(visits),
            'faults': len(faults),
            'open_faults': len([f for f in faults if f.status in ('مفتوح', 'قيد المعالجة')]),
        },
    }


def _contract_duration_months(start, end):
    if not start or not end or end <= start:
        return None
    return (end.year - start.year) * 12 + (end.month - start.month)


def _sync_contract_elevators(contract_id, elevator_ids):
    tenant_query(ContractElevator).filter_by(contract_id=contract_id).delete()
    for eid in elevator_ids:
        if eid:
            link = ContractElevator(contract_id=contract_id, elevator_id=int(eid))
            assign_organization(link)
            db.session.add(link)


def _purge_contract_dependencies(contract_id, *, keep_visits=False):
    """إزالة الارتباطات التي تمنع حذف العقد."""
    visits_q = tenant_query(MaintenanceVisit).filter_by(contract_id=contract_id)
    if keep_visits:
        visits_q.update({MaintenanceVisit.contract_id: None}, synchronize_session=False)
    else:
        visits_q.delete(synchronize_session=False)
    tenant_query(ContractElevator).filter_by(contract_id=contract_id).delete(synchronize_session=False)
    tenant_query(Invoice).filter_by(contract_id=contract_id).update(
        {Invoice.contract_id: None}, synchronize_session=False
    )
    tenant_query(Revenue).filter_by(contract_id=contract_id).update(
        {Revenue.contract_id: None}, synchronize_session=False
    )
    tenant_query(PartsBilling).filter_by(contract_id=contract_id).update(
        {PartsBilling.contract_id: None}, synchronize_session=False
    )


def _apply_contract_paid_from_form(c, form):
    """المبلغ المسدد من النموذج — القيمة 0 تعني غير مدفوع صراحة (لا تُتجاهل)."""
    if 'paid_amount' in form:
        raw = (form.get('paid_amount') or '').strip().replace(',', '')
        try:
            paid_val = 0.0 if raw == '' else float(raw)
        except (TypeError, ValueError):
            paid_val = 0.0
        c.paid_amount = _money_round(paid_val)
    elif getattr(c, 'paid_amount', None) is None:
        c.paid_amount = 0
    c.invoice_status = _invoice_status_from_paid(c, c.paid_amount or 0)


def _apply_contract_form(c, form):
    from customer_billing import split_vat_amounts
    raw_tax = form.get('tax_pct')
    tax_pct = 15 if raw_tax in (None, '') else _money_round(raw_tax)
    total_raw = form.get('total')
    value_raw = form.get('value', 0)
    if total_raw not in (None, ''):
        value, tax_amount, total = split_vat_amounts(
            amount_ex_vat=value_raw if value_raw not in (None, '') else None,
            total_incl_vat=total_raw,
            tax_pct=tax_pct,
        )
    else:
        value, tax_amount, total = split_vat_amounts(
            amount_ex_vat=value_raw,
            tax_pct=tax_pct,
        )
    start = _parse_date(form.get('start_date'))
    end = _parse_date(form.get('end_date'))
    c.customer_id = form['customer_id']
    c.contract_type = form.get('contract_type', '')
    c.start_date = start
    c.end_date = end
    c.duration_months = _contract_duration_months(start, end)
    c.maint_frequency = form.get('maint_frequency', '')
    visits = form.get('visits_per_month') or 1
    c.visits_per_month = int(visits) if str(visits).isdigit() else 1
    c.value = value
    c.tax_pct = tax_pct
    c.tax_amount = tax_amount
    c.total = total
    c.payment_terms = form.get('payment_terms', '')
    c.status = form.get('status', 'نشط')
    c.reminder_date = _parse_date(form.get('reminder_date'))
    c.due_date = _parse_date(form.get('due_date'))
    c.city = form.get('city', '')
    c.district = form.get('district', '')
    c.address = form.get('address', '')
    c.notes = form.get('notes', '')
    _apply_contract_paid_from_form(c, form)
    _sync_customer_location_from_contract_form(c.customer_id, form)


def _sync_customer_location_from_contract_form(customer_id, form):
    """حفظ إحداثيات خريطة العقد على العميل حتى لا ترجع الدبوس لإحداثيات الحرم الافتراضية."""
    if not customer_id:
        return
    lat = (form.get('lat') or '').strip().replace(',', '.')
    lng = (form.get('lng') or '').strip().replace(',', '.')
    maps_url = (form.get('maps_url') or '').strip()
    try:
        la = float(lat)
        ln = float(lng)
    except (TypeError, ValueError):
        return
    if la == 0 and ln == 0:
        return
    if abs(la - 21.4225) < 0.0012 and abs(ln - 39.8262) < 0.0012:
        return
    cust = tenant_query(Customer).filter_by(id=int(customer_id)).first()
    if not cust:
        return
    cust.lat = str(la)
    cust.lng = str(ln)
    if maps_url:
        cust.maps_url = maps_url[:500]


def _fin_proof_upload_dir(kind, row_id):
    path = os.path.join(FIN_PROOF_UPLOAD_ROOT, kind, str(row_id))
    os.makedirs(path, exist_ok=True)
    return path


def _remove_fin_proof(row):
    path = getattr(row, 'proof_path', None) or ''
    if not path:
        return
    full = os.path.join(app.root_path, 'static', path.replace('/', os.sep))
    if os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass
    row.proof_path = None


def enforce_admin_attachment_delete(*, json_response=False):
    """حذف المرفقات: مدير النظام فقط + كلمة مرور."""
    return enforce_admin_password(
        json_response=json_response,
        action='admin_attachment_delete_confirmed',
        admin_only_ar='حذف المرفقات متاح لمدير النظام فقط.',
        admin_only_en='Attachment deletion is admin-only.',
        bad_password_ar='كلمة المرور غير صحيحة — لم يتم حذف المرفق.',
        bad_password_en='Incorrect password — attachment was not deleted.',
    )


def _save_fin_proof(row, file_storage, *, kind: str, required: bool = False):
    """يحفظ إثبات دفع/صرف إن وُجد ملف. required=True يفرض وجود مرفق."""
    has_file = bool(file_storage and file_storage.filename)
    if not has_file:
        if required and not getattr(row, 'proof_path', None):
            raise ValueError('يجب إرفاق مستند إثبات الدفع أو الصرف (PDF أو صورة)')
        return
    ok, err = _upload_ok(file_storage, ALLOWED_FIN_PROOF_EXT)
    if not ok:
        raise ValueError('مستند الإثبات: ' + (err or 'نوع الملف غير مسموح'))
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_FIN_PROOF_BYTES:
        raise ValueError('مستند الإثبات أكبر من الحد المسموح (10 ميجا)')
    if not row.id:
        db.session.flush()
    _remove_fin_proof(row)
    stored = _safe_stored_upload_name(
        file_storage.filename,
        allowed=ALLOWED_FIN_PROOF_EXT,
        default_stem='proof',
    )
    abs_path = os.path.join(_fin_proof_upload_dir(kind, row.id), stored)
    file_storage.save(abs_path)
    row.proof_path = f'uploads/financial_proofs/{kind}/{row.id}/{stored}'


def _contract_upload_dir(contract_id):
    path = os.path.join(app.root_path, 'static', 'uploads', 'contracts', str(contract_id))
    os.makedirs(path, exist_ok=True)
    return path


def contract_file_display_name(relative_path):
    if not relative_path:
        return ''
    base = os.path.basename(relative_path.replace('\\', '/'))
    if '_' in base:
        base = base.split('_', 1)[1]
    return _upload_download_name(base)


def _remove_contract_file(c):
    if not c.file_path:
        return
    full = os.path.join(app.root_path, 'static', c.file_path.replace('/', os.sep))
    if os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass
    c.file_path = None


def _save_contract_file(c, file_storage):
    if not file_storage or not file_storage.filename:
        return
    if not _ext_ok(file_storage.filename, ALLOWED_CONTRACT_FILE_EXT):
        return
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_CONTRACT_FILE_BYTES:
        return
    if not c.id:
        db.session.flush()
    _remove_contract_file(c)
    stored = _safe_stored_upload_name(
        file_storage.filename,
        allowed=ALLOWED_CONTRACT_FILE_EXT,
        default_stem='contract',
    )
    abs_path = os.path.join(_contract_upload_dir(c.id), stored)
    file_storage.save(abs_path)
    c.file_path = f'uploads/contracts/{c.id}/{stored}'


# =============================================
# العقود
# =============================================
@app.route('/api/debug/contract-zero')
def api_debug_contract_zero():
    """تشخيص سريع: هل نسخة التشغيل ما زالت فيها منع القيمة 0؟"""
    import subprocess

    path = os.path.join(app.root_path, 'templates', 'contracts.html')
    text = ''
    try:
        with open(path, encoding='utf-8') as f:
            text = f.read()
    except OSError as exc:
        return jsonify({'ok': False, 'error': str(exc), 'root': app.root_path}), 500
    commit = ''
    try:
        commit = subprocess.check_output(
            ['git', '-C', app.root_path, 'log', '-1', '--oneline'],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        commit = ''
    alert = 'قيمة العقد يجب أن تكون أكبر من صفر'
    return jsonify({
        'ok': True,
        'root': app.root_path,
        'commit': commit,
        'has_old_alert_string': alert in text,
        'has_allow_zero': 'saveContractAllowZero' in text,
        'has_hotfix_file': os.path.isfile(
            os.path.join(app.root_path, 'static', 'contracts-zero-hotfix.js')
        ),
        'open_contracts': '/contracts?z=4',
    })


@app.route('/contracts')
def contracts():
    from sqlalchemy.orm import joinedload

    # إجبار المتصفح على URL جديد لكسر كاش الصفحة القديمة التي ترفض القيمة 0
    if request.args.get('z') != '4':
        args = request.args.to_dict(flat=True)
        args['z'] = '4'
        return redirect(url_for('contracts', **args))

    contracts_list = (
        tenant_query(Contract)
        .options(joinedload(Contract.customer), joinedload(Contract.elevators))
        .order_by(Contract.id.desc())
        .all()
    )
    renewed_ids = _annotate_contract_renewals(contracts_list)
    contract_scope = (request.args.get('scope') or '').strip().lower()
    if contract_scope not in ('maintenance', 'installation'):
        contract_scope = ''
    customers = tenant_query(Customer).order_by(Customer.name).all()
    elev_lookup = {
        e.id: {'code': e.code, 'building': e.building_name or '', 'customer_id': e.customer_id}
        for e in tenant_query(Elevator).all()
    }
    resp = make_response(render_template(
        'contracts.html',
        contracts=contracts_list,
        contracts_js=[contract_to_js_dict(c, renewed_ids=renewed_ids) for c in contracts_list],
        customers_js=[contract_customer_js_dict(c) for c in customers],
        elev_lookup=elev_lookup,
        next_contract_codes={
            'CN-': next_code(Contract, 'CN-', digits=5),
            'CI-': next_code(Contract, 'CI-', digits=5),
        },
        next_contract_code=next_code(Contract, 'CN-', digits=5),
        contract_scope=contract_scope,
        contracts_page_title=(
            'عقود الصيانة' if contract_scope == 'maintenance'
            else 'عقود التركيبات والتحديث' if contract_scope == 'installation'
            else 'العقود'
        ),
    ))
    # منع كاش المتصفح للنسخة القديمة من سكربت حفظ العقد
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/contracts/template')
def contracts_import_template():
    """تحميل نموذج استيراد العقود (عربي أو إنجليزي حسب لغة الواجهة)."""
    lang = request.args.get('lang')
    if lang not in ('ar', 'en'):
        lang = resolve_user_language(getattr(g, 'auth_user', None))
    basename = 'contracts_template_en.xlsx' if lang == 'en' else 'contracts_template.xlsx'
    download_name = 'contracts_import_template_en.xlsx' if lang == 'en' else 'contracts_import_template.xlsx'
    path = os.path.join(app.root_path, 'static', 'templates', basename)
    if not os.path.isfile(path):
        script = os.path.join(app.root_path, 'scripts', 'build_contracts_template.py')
        if os.path.isfile(script):
            import importlib.util
            spec = importlib.util.spec_from_file_location('build_contracts_template', script)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.build_xlsx(path, lang=lang)
        if not os.path.isfile(path):
            abort(404)
    return send_from_directory(
        os.path.dirname(path),
        os.path.basename(path),
        as_attachment=True,
        download_name=download_name,
    )


@app.route('/contracts/edit/<int:id>', methods=['POST'])
def contract_edit(id):
    from form_validation import contract_form_error

    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.headers.get('Accept') or '')
    )
    err = contract_form_error(request.form, money_round=_money_round)
    if err:
        if wants_json:
            return jsonify({'ok': False, 'message': err}), 400
        flash(err, 'error')
        return redirect(url_for('contracts'))
    c = tenant_get_or_404(Contract, id)
    raw_cid = (request.form.get('customer_id') or '').strip()
    try:
        new_customer_id = int(raw_cid) if raw_cid else None
    except (TypeError, ValueError):
        new_customer_id = None
    customer_changed = (
        new_customer_id is not None
        and c.customer_id is not None
        and int(new_customer_id) != int(c.customer_id)
    )
    if customer_changed:
        # دائماً JSON عند رفض تغيير العميل — حتى لا يُفسَّر التوجيه كنجاح في الواجهة
        auth_err = enforce_admin_password(
            json_response=True,
            action='contract_customer_change_confirmed',
            admin_only_ar='تغيير عميل العقد متاح لمدير النظام فقط.',
            admin_only_en='Changing the contract client is admin-only.',
            bad_password_ar='كلمة المرور غير صحيحة — لم يتم تغيير عميل العقد.',
            bad_password_en='Incorrect password — contract client was not changed.',
            details={
                'contract_id': c.id,
                'contract_code': c.code,
                'from_customer_id': c.customer_id,
                'to_customer_id': new_customer_id,
            },
        )
        if auth_err:
            return auth_err
    try:
        _apply_contract_form(c, request.form)
        upload = request.files.get('contract_file')
        if upload and upload.filename:
            _save_contract_file(c, upload)
        elif (request.form.get('remove_contract_file') or '').strip().lower() in (
            '1', 'true', 'yes', 'on',
        ):
            # حذف المرفق عبر /contracts/<id>/remove-file فقط (مدير النظام + كلمة مرور)
            msg = 'حذف مرفق العقد متاح لمدير النظام عبر زر حذف المرفق فقط'
            if wants_json:
                return jsonify({'ok': False, 'message': msg}), 403
            flash(msg, 'error')
            return redirect(url_for('contracts'))
        _sync_contract_elevators(c.id, request.form.getlist('elevator_ids'))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('contract_edit failed')
        if wants_json:
            return jsonify({'ok': False, 'message': str(exc) or 'تعذّر حفظ العقد'}), 400
        flash(str(exc) or 'تعذّر حفظ العقد', 'error')
        return redirect(url_for('contracts'))
    if wants_json:
        return jsonify({'ok': True, 'id': c.id, 'code': c.code, 'redirect': url_for('contracts')})
    return redirect(url_for('contracts'))


@app.route('/contracts/add', methods=['POST'])
def contract_add():
    from form_validation import contract_form_error
    from contract_codes import unique_renewal_contract_code

    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.headers.get('Accept') or '')
    )
    err = contract_form_error(request.form, money_round=_money_round)
    if err:
        if wants_json:
            return jsonify({'ok': False, 'message': err}), 400
        flash(err, 'error')
        return redirect(url_for('contracts'))

    renew_from_id = request.form.get('renew_from_id', type=int)
    renew_src = tenant_get_or_404(Contract, renew_from_id) if renew_from_id else None
    existing = None

    import_code = (request.form.get('code') or '').strip()
    if import_code:
        from contract_codes import normalize_contract_code
        import_code = normalize_contract_code(import_code)
        existing = tenant_query(Contract).filter_by(code=import_code).first()
        code = import_code
    elif renew_src:
        start_raw = (request.form.get('start_date') or '').strip()
        try:
            year = int(start_raw[:4]) if start_raw else date.today().year
        except ValueError:
            year = date.today().year
        taken = [
            row[0]
            for row in tenant_query(Contract).with_entities(Contract.code).all()
            if row[0]
        ]
        code = unique_renewal_contract_code(renew_src.code, year, taken)
        if len(code) > 20:
            if wants_json:
                return jsonify({'ok': False, 'message': 'رقم العقد الناتج أطول من المسموح'}), 400
            flash('رقم العقد الناتج أطول من المسموح', 'error')
            return redirect(url_for('contracts'))
    else:
        from contract_codes import CONTRACT_CODE_DIGITS, contract_prefix_for_type

        prefix = contract_prefix_for_type(request.form.get('contract_type'))
        code = next_code(Contract, prefix, digits=CONTRACT_CODE_DIGITS)

    if import_code and len(code) > 20:
        msg = 'رقم العقد الناتج أطول من المسموح'
        if wants_json:
            return jsonify({'ok': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('contracts'))

    c = existing or Contract(code=code)
    try:
        _apply_contract_form(c, request.form)
        if existing is None:
            assign_organization(c)
            db.session.add(c)
            db.session.flush()
        if renew_src and (renew_src.status or '') not in ('تم تجديده', 'ملغي'):
            renew_src.status = 'تم تجديده'
        _save_contract_file(c, request.files.get('contract_file'))
        _sync_contract_elevators(c.id, request.form.getlist('elevator_ids'))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('contract_add failed')
        if wants_json:
            return jsonify({'ok': False, 'message': str(exc) or 'تعذّر حفظ العقد'}), 400
        flash(str(exc) or 'تعذّر حفظ العقد', 'error')
        return redirect(url_for('contracts'))
    if wants_json:
        return jsonify({'ok': True, 'id': c.id, 'code': c.code, 'redirect': url_for('contracts')})
    return redirect(url_for('contracts'))

@app.route('/contracts/<int:id>/remove-file', methods=['POST'])
def contract_remove_file(id):
    """حذف مرفق ملف العقد — مدير النظام فقط."""
    err = enforce_admin_attachment_delete(json_response=True)
    if err:
        return err
    c = tenant_get_or_404(Contract, id)
    if not c.file_path:
        return jsonify({'ok': True, 'removed': False, 'message': 'لا يوجد مرفق'})
    _remove_contract_file(c)
    db.session.commit()
    return jsonify({'ok': True, 'removed': True, 'id': c.id, 'code': c.code})


@app.route('/contracts/delete/<int:id>', methods=['POST'])
def contract_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    c = tenant_get_or_404(Contract, id)
    try:
        _remove_contract_file(c)
        _purge_contract_dependencies(id)
        db.session.delete(c)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('تعذّر حذف العقد — تحقق من السجلات المرتبطة', 'error')
    return redirect(url_for('contracts'))


@app.route('/contracts/<int:contract_id>/print')
def contract_print_page(contract_id):
    from contract_print import contract_print_payload

    return render_template('contract-print.html', **contract_print_payload(contract_id))


# =============================================
# الفنيون
# =============================================
def technician_display_status(tech, today=None):
    from technician_assignments import visits_for_technician_filter, faults_for_technician_filter

    today = today or date.today()
    raw = tech.status or 'متاح'
    if raw == 'نشط':
        raw = 'متاح'
    if raw in ('إجازة', 'غير نشط'):
        return raw
    busy_visit = tenant_query(MaintenanceVisit).filter(
        visits_for_technician_filter(tech.id),
        MaintenanceVisit.visit_date == today,
        MaintenanceVisit.status == 'جارٍ',
    ).count()
    open_fault = tenant_query(Fault).filter(
        faults_for_technician_filter(tech.id),
        Fault.status == 'قيد المعالجة',
    ).count()
    if busy_visit or open_fault:
        return 'مشغول'
    return raw if raw in ('متاح', 'مشغول') else 'متاح'


def _upload_url_fast(relative_path: str) -> str:
    """رابط static بدون فحص القرص (أسرع لقوائم الصفحات)."""
    if not relative_path:
        return ''
    rel = relative_path.replace('\\', '/').lstrip('/')
    return '/static/' + rel


def batch_technician_list_meta(techs, today=None) -> dict[int, dict]:
    """إحصاءات وحالة عرض لكل الفنيين باستعلامات مجمّعة بدل N+1."""
    from collections import defaultdict

    from sqlalchemy import func

    from models import FaultTechnician, VisitTechnician

    today = today or date.today()
    ids = [t.id for t in techs if t and t.id]
    if not ids:
        return {}

    visit_sets: dict[int, set] = defaultdict(set)
    for tid, vid in (
        tenant_query(MaintenanceVisit)
        .with_entities(MaintenanceVisit.technician_id, MaintenanceVisit.id)
        .filter(MaintenanceVisit.technician_id.in_(ids))
        .all()
    ):
        if tid and vid:
            visit_sets[int(tid)].add(int(vid))
    for tid, vid in (
        tenant_query(VisitTechnician)
        .with_entities(VisitTechnician.technician_id, VisitTechnician.visit_id)
        .filter(VisitTechnician.technician_id.in_(ids))
        .all()
    ):
        if tid and vid:
            visit_sets[int(tid)].add(int(vid))

    fault_sets: dict[int, set] = defaultdict(set)
    for tid, fid in (
        tenant_query(Fault)
        .with_entities(Fault.technician_id, Fault.id)
        .filter(Fault.technician_id.in_(ids))
        .all()
    ):
        if tid and fid:
            fault_sets[int(tid)].add(int(fid))
    for tid, fid in (
        tenant_query(FaultTechnician)
        .with_entities(FaultTechnician.technician_id, FaultTechnician.fault_id)
        .filter(FaultTechnician.technician_id.in_(ids))
        .all()
    ):
        if tid and fid:
            fault_sets[int(tid)].add(int(fid))

    busy_visit = {
        int(r[0])
        for r in (
            tenant_query(MaintenanceVisit)
            .with_entities(MaintenanceVisit.technician_id)
            .filter(
                MaintenanceVisit.visit_date == today,
                MaintenanceVisit.status == 'جارٍ',
                MaintenanceVisit.technician_id.in_(ids),
            )
            .all()
        )
        if r[0]
    }
    busy_visit |= {
        int(r[0])
        for r in (
            tenant_query(VisitTechnician)
            .join(MaintenanceVisit, MaintenanceVisit.id == VisitTechnician.visit_id)
            .with_entities(VisitTechnician.technician_id)
            .filter(
                MaintenanceVisit.visit_date == today,
                MaintenanceVisit.status == 'جارٍ',
                VisitTechnician.technician_id.in_(ids),
            )
            .all()
        )
        if r[0]
    }
    busy_fault = {
        int(r[0])
        for r in (
            tenant_query(Fault)
            .with_entities(Fault.technician_id)
            .filter(
                Fault.status == 'قيد المعالجة',
                Fault.technician_id.in_(ids),
            )
            .all()
        )
        if r[0]
    }
    busy_fault |= {
        int(r[0])
        for r in (
            tenant_query(FaultTechnician)
            .join(Fault, Fault.id == FaultTechnician.fault_id)
            .with_entities(FaultTechnician.technician_id)
            .filter(
                Fault.status == 'قيد المعالجة',
                FaultTechnician.technician_id.in_(ids),
            )
            .all()
        )
        if r[0]
    }

    out: dict[int, dict] = {}
    for t in techs:
        raw = t.status or 'متاح'
        if raw == 'نشط':
            raw = 'متاح'
        if raw in ('إجازة', 'غير نشط'):
            display = raw
        elif t.id in busy_visit or t.id in busy_fault:
            display = 'مشغول'
        else:
            display = raw if raw in ('متاح', 'مشغول') else 'متاح'
        out[t.id] = {
            'visits': len(visit_sets.get(t.id, ())),
            'faults': len(fault_sets.get(t.id, ())),
            'display_status': display,
        }
    return out


app.jinja_env.globals['technician_display_status'] = technician_display_status


def technician_to_js_dict(t, *, meta: dict | None = None):
    """تسلسل فني لـ JSON (حالة العرض تُحسب مرة واحدة في السيرفر)."""
    import json as _json

    docs = []
    for d in sorted(t.documents, key=lambda x: x.uploaded_at or datetime.min, reverse=True):
        fname = d.file_name or ''
        docs.append({
            'id': d.id,
            'doc_type': d.doc_type or '',
            'title': d.title or d.file_name or '',
            'file_name': fname,
            'url': _upload_url_fast(d.file_path) if d.file_path else '',
            'is_image': fname.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')),
            'is_pdf': fname.lower().endswith('.pdf'),
            'uploaded_at': d.uploaded_at.strftime('%Y-%m-%d') if d.uploaded_at else '',
        })
    districts = []
    raw_dist = getattr(t, 'districts_json', None) or ''
    if raw_dist:
        try:
            parsed = _json.loads(raw_dist)
            if isinstance(parsed, list):
                districts = [str(x) for x in parsed if x]
            elif isinstance(parsed, str) and parsed.strip():
                districts = [parsed.strip()]
        except (_json.JSONDecodeError, TypeError):
            districts = [x.strip() for x in str(raw_dist).split(',') if x.strip()]
    meta = meta or {}
    return {
        'id': t.id,
        'code': t.code,
        'name': t.name,
        'name_en': t.name_en or '',
        'phone': t.phone or '',
        'phone2': t.phone2 or '',
        'job_title': t.job_title or '',
        'specialization': t.specialization or '',
        'team': t.team or 'عام',
        'city': t.city or '',
        'nationality': getattr(t, 'nationality', None) or '',
        'experience_years': getattr(t, 'experience_years', None),
        'email': getattr(t, 'email', None) or '',
        'national_id': t.national_id or '',
        'national_id_expiry': (
            t.national_id_expiry.isoformat()
            if getattr(t, 'national_id_expiry', None) else ''
        ),
        'license_number': getattr(t, 'license_number', None) or '',
        'license_expiry': (
            t.license_expiry.isoformat()
            if getattr(t, 'license_expiry', None) else ''
        ),
        'districts': districts,
        'hire_date': t.hire_date.isoformat() if t.hire_date else '',
        'salary': t.salary if t.salary is not None else '',
        'emergency': bool(t.emergency),
        'status': t.status or 'متاح',
        'display_status': meta.get('display_status') or technician_display_status(t),
        'visits': int(meta['visits']) if meta and 'visits' in meta else 0,
        'faults': int(meta['faults']) if meta and 'faults' in meta else 0,
        'notes': t.notes or '',
        'photo_url': _upload_url_fast(t.photo_path) if t.photo_path else '',
        'signature_url': _upload_url_fast(t.signature_path) if t.signature_path else '',
        'has_sign_pin': bool(t.sign_pin_hash),
        'documents': len(list(t.documents or [])),
        'docs': docs,
    }


from technician_assignments import fault_technicians_label as _fault_technicians_label_jinja
from technician_assignments import visit_technicians_label as _visit_technicians_label_jinja
app.jinja_env.globals['fault_technicians_label'] = _fault_technicians_label_jinja
app.jinja_env.globals['visit_technicians_label'] = _visit_technicians_label_jinja


TECH_TEAMS_ALLOWED = frozenset({'عام', 'صيانة', 'أعطال'})
TECH_STATUS_ALLOWED = frozenset({'متاح', 'مشغول', 'إجازة', 'غير نشط'})


def _apply_technician_form(t, form):
    import json as _json

    name = (form.get('name') or '').strip()
    if not name:
        raise ValueError('اسم الفني مطلوب')
    t.name = name
    t.name_en = (form.get('name_en') or '').strip()
    t.phone = (form.get('phone') or '').strip()
    t.phone2 = (form.get('phone2') or '').strip()
    t.job_title = (form.get('job_title') or '').strip()
    t.specialization = (form.get('specialization') or '').strip()
    t.city = (form.get('city') or '').strip()
    t.nationality = (form.get('nationality') or '').strip()
    t.email = (form.get('email') or '').strip()
    nid = (form.get('national_id') or '').strip()
    if nid:
        q = tenant_query(Technician).filter(Technician.national_id == nid)
        if getattr(t, 'id', None):
            q = q.filter(Technician.id != t.id)
        if q.first():
            raise ValueError('رقم الإقامة مسجّل لفني آخر')
    t.national_id = nid
    t.national_id_expiry = _parse_date(form.get('national_id_expiry') or form.get('iqama_expiry'))
    t.license_number = (form.get('license_number') or form.get('license') or '').strip()
    t.license_expiry = _parse_date(form.get('license_expiry'))
    exp_raw = form.get('experience_years')
    if exp_raw in (None, ''):
        t.experience_years = None
    else:
        try:
            t.experience_years = max(0, int(float(exp_raw)))
        except (TypeError, ValueError) as exc:
            raise ValueError('سنوات الخبرة غير صالحة') from exc
    districts = []
    if hasattr(form, 'getlist'):
        districts = [str(x).strip() for x in form.getlist('districts') if str(x).strip()]
    if not districts:
        raw = (form.get('districts_json') or form.get('districts') or '').strip()
        if raw.startswith('['):
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, list):
                    districts = [str(x).strip() for x in parsed if str(x).strip()]
            except _json.JSONDecodeError:
                districts = []
        elif raw:
            districts = [x.strip() for x in raw.split(',') if x.strip()]
    t.districts_json = _json.dumps(districts, ensure_ascii=False) if districts else ''
    t.hire_date = _parse_date(form.get('hire_date'))
    salary = form.get('salary')
    try:
        t.salary = float(salary) if salary not in (None, '') else None
    except (TypeError, ValueError) as exc:
        raise ValueError('الراتب غير صالح') from exc
    t.emergency = form.get('emergency') == 'on'
    status = (form.get('status') or 'متاح').strip()
    if status == 'نشط':
        status = 'متاح'
    t.status = status if status in TECH_STATUS_ALLOWED else 'متاح'
    team = (form.get('team') or 'عام').strip()
    t.team = team if team in TECH_TEAMS_ALLOWED else 'عام'
    t.notes = (form.get('notes') or '').strip()


def _tech_dir(tech_id, sub=''):
    path = os.path.join(TECH_UPLOAD_ROOT, str(tech_id), sub) if sub else os.path.join(TECH_UPLOAD_ROOT, str(tech_id))
    os.makedirs(path, exist_ok=True)
    return path


def upload_url(relative_path):
    """رابط ملف مرفوع تحت static/uploads مع cache-buster."""
    if not relative_path:
        return ''
    rel = relative_path.replace('\\', '/').lstrip('/')
    url = '/static/' + rel
    full = os.path.join(app.root_path, 'static', rel.replace('/', os.sep))
    if os.path.isfile(full):
        url += '?v=' + str(int(os.path.getmtime(full)))
    return url


def _static_upload_url(relative_path):
    if not relative_path:
        return None
    return upload_url(relative_path)


@app.route('/static/uploads/<path:subpath>')
def serve_upload_file(subpath):
    """تأكيد تقديم الملفات المرفوعة (صور المباني، مستندات الفنيين...)."""
    from field_auth import field_session_technician_id
    from urllib.parse import quote

    if not current_user() and not field_session_technician_id():
        if request.path.startswith('/api/') or (
            request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html
        ):
            abort(401)
        ref = request.referrer or ''
        base = request.url_root.rstrip('/')
        if ref.startswith(base + '/field') or '/field/' in ref:
            return redirect(url_for('field_login', next=request.path))
        return redirect(url_for('login', next=request.path))

    directory = os.path.join(app.root_path, 'static', 'uploads')
    full = os.path.normpath(os.path.join(directory, subpath))
    if not full.startswith(os.path.normpath(directory)) or not os.path.isfile(full):
        abort(404)

    mime = _guess_upload_mimetype(full)
    download_name = _upload_download_name(os.path.basename(full))
    # عرض PDF/الصور داخل المتصفح بدل تنزيل إجباري باسم خاطئ
    inline = mime.startswith('image/') or mime == 'application/pdf'
    resp = send_from_directory(
        directory,
        subpath,
        mimetype=mime,
        as_attachment=not inline,
        download_name=download_name,
    )
    if inline:
        # filename* لدعم الأسماء غير ASCII إن لزم
        ascii_name = download_name.encode('ascii', 'ignore').decode('ascii') or 'document.pdf'
        resp.headers['Content-Disposition'] = (
            f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(download_name)}"
        )
        resp.headers['X-Content-Type-Options'] = 'nosniff'
    # شعار الشركة يتغيّر كثيراً — امنع الكاش القوي
    if subpath.replace('\\', '/').startswith('company/'):
        resp.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
    return resp


app.jinja_env.globals['upload_url'] = upload_url
app.jinja_env.globals['contract_file_display_name'] = contract_file_display_name


def _ext_ok(filename, allowed):
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in allowed


def _original_upload_ext(filename, allowed, default='pdf'):
    """استخراج الامتداد من الاسم الأصلي قبل secure_filename (يدعم الأسماء العربية)."""
    name = (filename or '').replace('\\', '/').split('/')[-1].strip()
    if '.' in name:
        ext = name.rsplit('.', 1)[-1].lower().strip()
        if ext in allowed:
            return ext
    return default if default in allowed else next(iter(allowed), 'pdf')


def _safe_stored_upload_name(filename, *, allowed, default_stem='file'):
    """
    اسم تخزين آمن مع امتداد صحيح.
    secure_filename يحذف العربية فيحوّل «مرفق.pdf» → «pdf» ثم يُحفظ كـ xxx_pdf بدون نقطة.
    """
    ext = _original_upload_ext(filename, allowed, default='pdf')
    raw = (filename or '').replace('\\', '/').split('/')[-1]
    stem = raw.rsplit('.', 1)[0] if '.' in raw else raw
    safe_stem = secure_filename(stem) or default_stem
    # أزل أي امتداد زائف لصقه secure_filename
    if '.' in safe_stem:
        maybe_ext = safe_stem.rsplit('.', 1)[-1].lower()
        if maybe_ext in allowed or len(maybe_ext) <= 5:
            safe_stem = safe_stem.rsplit('.', 1)[0] or default_stem
    safe_stem = (safe_stem or default_stem).replace('.', '_')
    return f'{uuid.uuid4().hex[:10]}_{safe_stem}.{ext}'


def _upload_download_name(stored_basename):
    """اسم ظاهر للمتصفح — يصلح xxx_pdf → xxx.pdf للملفات القديمة."""
    name = (stored_basename or 'file').split('/')[-1]
    lower = name.lower()
    for ext in ('pdf', 'png', 'jpg', 'jpeg', 'webp', 'gif'):
        suffix = '_' + ext
        if lower.endswith(suffix) and not lower.endswith('.' + ext):
            return name[: -len(suffix)] + '.' + ext
    return name


def _guess_upload_mimetype(path):
    import mimetypes

    base = os.path.basename(path).lower()
    # ملفات قديمة بلا نقطة: xxx_pdf
    for ext, mime in (
        ('_pdf', 'application/pdf'),
        ('.pdf', 'application/pdf'),
        ('_png', 'image/png'),
        ('.png', 'image/png'),
        ('_jpg', 'image/jpeg'),
        ('.jpg', 'image/jpeg'),
        ('_jpeg', 'image/jpeg'),
        ('.jpeg', 'image/jpeg'),
        ('_webp', 'image/webp'),
        ('.webp', 'image/webp'),
    ):
        if base.endswith(ext):
            return mime
    mime, _ = mimetypes.guess_type(path)
    return mime or 'application/octet-stream'


def _upload_ok(file_storage, allowed_ext):
    """امتداد + حجم + MIME — يرجع (ok, error_ar)."""
    from liftcore_security import validate_upload_file
    if not file_storage or not file_storage.filename:
        return True, ''
    if not _ext_ok(file_storage.filename, allowed_ext):
        return False, 'نوع الملف غير مسموح'
    return validate_upload_file(file_storage, allowed_ext=allowed_ext)


def _save_technician_signature(tech, file_storage, pin_plain=''):
    from signatory_service import upsert_signatory
    from signature_auth import normalize_national_id, validate_sign_pin

    pin = str(pin_plain or '').strip()
    has_file = bool(file_storage and file_storage.filename)
    if has_file:
        ok, err = _upload_ok(file_storage, ALLOWED_TECH_PHOTO_EXT)
        if not ok:
            raise ValueError('صورة التوقيع: ' + (err or 'غير صالحة'))
        has_file = _ext_ok(file_storage.filename, ALLOWED_TECH_PHOTO_EXT)
    existing = tenant_query(Signatory).filter_by(technician_id=tech.id, is_active=True).first()
    if not has_file and not pin and not existing:
        return
    # رمز دخول الجوال — يُحفظ على الفني (وموقّعه إن وُجد)
    if pin and not has_file:
        if not validate_sign_pin(pin):
            raise ValueError('رمز دخول الجوال يجب أن يكون 6 أرقام')
        tech.sign_pin_hash = hash_password(pin)
        if existing:
            existing.sign_pin_hash = tech.sign_pin_hash
        return
    if has_file and not pin and not tech.sign_pin_hash and not existing:
        raise ValueError('كلمة مرور التوقيع (6 أرقام) مطلوبة مع صورة التوقيع')
    if not tech.national_id:
        raise ValueError('أدخل رقم الإقامة في الوثائق الرسمية قبل حفظ التوقيع')
    raw = file_storage.read() if has_file else None
    if has_file and not pin and tech.sign_pin_hash and not existing:
        # إنشاء موقّع من الهاش الحالي بدون طلب PIN جديد
        from models import Signatory as _Signatory
        from signature_crypto import save_encrypted_signature
        nid = normalize_national_id(tech.national_id)
        row = _Signatory(
            name=(tech.name or '').strip(),
            national_id=nid,
            role='technician',
            technician_id=tech.id,
            sign_pin_hash=tech.sign_pin_hash,
            is_active=True,
        )
        assign_organization(row)
        db.session.add(row)
        db.session.flush()
        if raw:
            row.signature_path = save_encrypted_signature(
                app.root_path, app.config['SECRET_KEY'], row.id, raw
            )
        tech.signature_path = row.signature_path
        return
    row = upsert_signatory(
        name=tech.name,
        national_id=tech.national_id,
        role='technician',
        pin_plain=pin,
        pin_hash_fn=hash_password,
        image_bytes=raw,
        app_root=app.root_path,
        secret=app.config['SECRET_KEY'],
        technician_id=tech.id,
        signatory_id=existing.id if existing else None,
    )
    tech.signature_path = row.signature_path
    tech.sign_pin_hash = row.sign_pin_hash


def _save_technician_photo(tech, file_storage):
    if not file_storage or not file_storage.filename:
        return
    ok, err = _upload_ok(file_storage, ALLOWED_TECH_PHOTO_EXT)
    if not ok:
        raise ValueError('صورة الفني: ' + (err or 'نوع الملف غير مسموح'))
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    folder = _tech_dir(tech.id)
    for old in os.listdir(folder):
        if old.startswith('photo.'):
            try:
                os.remove(os.path.join(folder, old))
            except OSError:
                pass
    filename = f'photo.{ext}'
    abs_path = os.path.join(folder, filename)
    file_storage.save(abs_path)
    tech.photo_path = f'uploads/technicians/{tech.id}/{filename}'


def _save_technician_documents(tech, files, types, titles):
    if not files:
        return
    docs_folder = _tech_dir(tech.id, 'docs')
    errors = []
    for i, file_storage in enumerate(files):
        if not file_storage or not file_storage.filename:
            continue
        ok, err = _upload_ok(file_storage, ALLOWED_TECH_DOC_EXT)
        if not ok:
            errors.append(f'{file_storage.filename}: {err or "نوع غير مسموح"}')
            continue
        original = secure_filename(file_storage.filename) or 'document'
        stored = _safe_stored_upload_name(
            file_storage.filename,
            allowed=ALLOWED_TECH_DOC_EXT,
            default_stem='document',
        )
        # اسم العرض يحافظ على الامتداد الصحيح
        display_name = _upload_download_name(stored.split('_', 1)[-1] if '_' in stored else stored)
        if original and '.' not in original:
            original = display_name
        abs_path = os.path.join(docs_folder, stored)
        file_storage.save(abs_path)
        doc_type = types[i] if i < len(types) and types[i] else 'أخرى'
        title = titles[i] if i < len(titles) and titles[i] else (display_name or original)
        doc = TechnicianDocument(
            technician_id=tech.id,
            doc_type=doc_type,
            title=title,
            file_path=f'uploads/technicians/{tech.id}/docs/{stored}',
            file_name=display_name or original,
            mime_type=getattr(file_storage, 'mimetype', None) or '',
        )
        assign_organization(doc)
        db.session.add(doc)
    if errors:
        raise ValueError('مستندات مرفوضة — ' + '؛ '.join(errors[:3]))


def _remove_technician_files(tech):
    folder = os.path.join(TECH_UPLOAD_ROOT, str(tech.id))
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)


def _technician_documents_json(tech):
    return [{
        'id': d.id,
        'doc_type': d.doc_type or '',
        'title': d.title or d.file_name or '',
        'file_name': d.file_name or '',
        'url': _static_upload_url(d.file_path),
        'is_image': (d.mime_type or '').startswith('image/') or (
            d.file_name or ''
        ).lower().endswith(('.png', '.jpg', '.jpeg', '.webp')),
        'is_pdf': (d.file_name or '').lower().endswith('.pdf'),
        'uploaded_at': d.uploaded_at.strftime('%Y-%m-%d') if d.uploaded_at else '',
    } for d in sorted(tech.documents, key=lambda x: x.uploaded_at or datetime.min, reverse=True)]


@app.route('/technicians')
def technicians():
    from sqlalchemy.orm import joinedload

    techs = (
        tenant_query(Technician)
        .options(joinedload(Technician.documents))
        .order_by(Technician.id.desc())
        .all()
    )
    unassigned_faults = tenant_query(Fault).filter(
        Fault.technician_id.is_(None),
        Fault.status.in_(['مفتوح', 'قيد المعالجة']),
    ).count()
    maint_techs = [t for t in techs if (t.team or 'عام') in ('صيانة', 'عام')] or list(techs)
    from maintenance_teams import list_all_teams, team_to_dict
    maint_teams = [team_to_dict(t) for t in list_all_teams() if t.active]
    meta = batch_technician_list_meta(techs)
    return render_template(
        'technicians.html',
        technicians=techs,
        technicians_js=[technician_to_js_dict(t, meta=meta.get(t.id)) for t in techs],
        next_tech_code=next_code(Technician, 'Tech-', digits=3),
        unassigned_faults=unassigned_faults,
        maint_technicians=maint_techs,
        maint_technicians_js=[{'id': t.id, 'name': t.name} for t in maint_techs],
        maint_teams_js=maint_teams,
    )


@app.route('/api/technicians/<int:tech_id>/profile')
def api_technician_profile(tech_id):
    from models import FaultTechnician, VisitTechnician

    tech = tenant_get_or_404(Technician, tech_id)
    today = date.today()
    visit_ids = {
        int(r[0])
        for r in tenant_query(MaintenanceVisit).with_entities(MaintenanceVisit.id)
        .filter_by(technician_id=tech_id).all()
        if r[0]
    }
    visit_ids |= {
        int(r[0])
        for r in tenant_query(VisitTechnician).with_entities(VisitTechnician.visit_id)
        .filter_by(technician_id=tech_id).all()
        if r[0]
    }
    fault_ids = {
        int(r[0])
        for r in tenant_query(Fault).with_entities(Fault.id)
        .filter_by(technician_id=tech_id).all()
        if r[0]
    }
    fault_ids |= {
        int(r[0])
        for r in tenant_query(FaultTechnician).with_entities(FaultTechnician.fault_id)
        .filter_by(technician_id=tech_id).all()
        if r[0]
    }
    visits = []
    if visit_ids:
        visits = (
            tenant_query(MaintenanceVisit).filter(MaintenanceVisit.id.in_(visit_ids))
            .order_by(MaintenanceVisit.visit_date.desc())
            .limit(25)
            .all()
        )
    faults = []
    if fault_ids:
        faults = (
            tenant_query(Fault).filter(Fault.id.in_(fault_ids))
            .order_by(Fault.reported_at.desc())
            .limit(25)
            .all()
        )
    return jsonify({
        'technician': {
            'id': tech.id,
            'code': tech.code,
            'name': tech.name,
            'display_status': technician_display_status(tech, today),
            'photo_url': _static_upload_url(tech.photo_path),
            'job_title': tech.job_title or '',
            'specialization': tech.specialization or '',
            'team': tech.team or 'عام',
            'has_sign_pin': bool(tech.sign_pin_hash),
        },
        'documents': _technician_documents_json(tech),
        'stats': {
            'total_visits': len(visit_ids),
            'total_faults': len(fault_ids),
            'open_faults': sum(1 for f in faults if f.status in ('مفتوح', 'قيد المعالجة')),
            'today_visits': sum(1 for v in visits if v.visit_date == today),
        },
        'visits': [{
            'code': v.code,
            'date': str(v.visit_date or ''),
            'time': v.visit_time or '',
            'type': v.visit_type or '',
            'customer': v.elevator.customer.name if v.elevator else '—',
            'elevator': v.elevator.code if v.elevator else '—',
            'status': v.status or '',
        } for v in visits],
        'faults': [{
            'code': f.code,
            'date': f.reported_at.strftime('%Y-%m-%d') if f.reported_at else '',
            'type': f.fault_type or '',
            'customer': f.elevator.customer.name if f.elevator else '—',
            'elevator': f.elevator.code if f.elevator else '—',
            'priority': f.priority or '',
            'status': f.status or '',
        } for f in faults],
    })


@app.route('/technicians/add', methods=['POST'])
def technician_add():
    from entitlements import assert_capacity

    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.headers.get('Accept') or '')
    )

    def _fail(msg, code=400):
        if wants_json:
            return jsonify({'ok': False, 'message': msg}), code
        flash(msg, 'error')
        return redirect(url_for('technicians'))

    raw_code = (request.form.get('code') or '').strip()
    m_tech = re.match(r'Tech-(\d+)$', raw_code, re.I)
    existing = None
    if m_tech:
        raw_code = f'Tech-{int(m_tech.group(1)):03d}'
        existing = tenant_query(Technician).filter_by(code=raw_code).first()
        if existing and tenant_query(Technician).filter(
            Technician.code == raw_code, Technician.id != existing.id
        ).first():
            raw_code = ''
            existing = None
    else:
        raw_code = ''

    if existing is None:
        cap = assert_capacity('technicians')
        if not cap.get('ok'):
            return _fail(cap.get('error') or 'تجاوزت حد الفنيين في الباقة.')
    phone = request.form.get('phone', '')
    taken, msg = phone_taken(phone, technician_id=existing.id if existing else None)
    if taken:
        return _fail(msg)
    wa = request.form.get('phone2', '')
    if wa and phone_key(wa) != phone_key(phone):
        taken2, msg2 = phone_taken(wa, technician_id=existing.id if existing else None)
        if taken2:
            return _fail(msg2)
    t = existing or Technician(code=raw_code or next_code(Technician, 'Tech-', digits=3))
    try:
        _apply_technician_form(t, request.form)
        if existing is None:
            assign_organization(t)
            db.session.add(t)
            db.session.flush()
        _save_technician_photo(t, request.files.get('photo'))
        _save_technician_signature(t, request.files.get('signature'), request.form.get('sign_pin', ''))
        _save_technician_documents(
            t,
            request.files.getlist('documents'),
            request.form.getlist('doc_types'),
            request.form.getlist('doc_titles'),
        )
        db.session.commit()
    except (ValueError, KeyError) as exc:
        db.session.rollback()
        return _fail(str(exc) or 'تعذّر حفظ الفني')
    if wants_json:
        return jsonify({'ok': True, 'id': t.id, 'code': t.code})
    flash('تم إضافة الفني بنجاح' if existing is None else 'تم تحديث بيانات الفني بنجاح', 'success')
    return redirect(url_for('technicians'))


@app.route('/technicians/<int:id>/phone', methods=['POST'])
def technician_update_phone(id):
    t = tenant_get_or_404(Technician, id)
    data = request.get_json(silent=True) or request.form
    phone = (data.get('phone') or '').strip()
    phone2 = (data.get('phone2') or '').strip()
    if not phone and not phone2:
        return jsonify({'error': 'أدخل رقم الجوال أو واتساب'}), 400
    for p in (phone, phone2):
        if not p:
            continue
        taken, msg = phone_taken(p, technician_id=t.id)
        if taken:
            return jsonify({'error': msg}), 400
    t.phone = phone or phone2
    t.phone2 = phone2 or phone
    db.session.commit()
    return jsonify({'ok': True, 'phone': t.phone, 'phone2': t.phone2})


@app.route('/technicians/edit/<int:id>', methods=['POST'])
def technician_edit(id):
    t = tenant_get_or_404(Technician, id)
    phone = request.form.get('phone', '')
    taken, msg = phone_taken(phone, technician_id=t.id)
    if taken:
        flash(msg, 'error')
        return redirect(url_for('technicians'))
    wa = request.form.get('phone2', '')
    if wa and phone_key(wa) != phone_key(phone):
        taken2, msg2 = phone_taken(wa, technician_id=t.id)
        if taken2:
            flash(msg2, 'error')
            return redirect(url_for('technicians'))
    try:
        _apply_technician_form(t, request.form)
        _save_technician_photo(t, request.files.get('photo'))
        _save_technician_signature(t, request.files.get('signature'), request.form.get('sign_pin', ''))
        _save_technician_documents(
            t,
            request.files.getlist('documents'),
            request.form.getlist('doc_types'),
            request.form.getlist('doc_titles'),
        )
        db.session.commit()
    except (ValueError, KeyError) as exc:
        db.session.rollback()
        flash(str(exc) or 'تعذّر تحديث الفني', 'error')
        return redirect(url_for('technicians'))
    flash('تم تحديث بيانات الفني بنجاح', 'success')
    return redirect(url_for('technicians'))


@app.route('/technicians/documents/delete/<int:doc_id>', methods=['POST'])
def technician_document_delete(doc_id):
    err = enforce_admin_attachment_delete(json_response=True)
    if err:
        return err
    doc = tenant_get_or_404(TechnicianDocument, doc_id)
    abs_path = os.path.join(app.root_path, 'static', doc.file_path.replace('/', os.sep))
    if os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/technicians/delete/<int:id>', methods=['POST'])
def technician_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    from models import FaultTechnician, MaintenanceTeam, VisitTechnician

    t = tenant_get_or_404(Technician, id)
    blockers = []
    n_visits = tenant_query(MaintenanceVisit).filter_by(technician_id=t.id).count()
    n_visits += tenant_query(VisitTechnician).filter_by(technician_id=t.id).count()
    if n_visits:
        blockers.append(f'{n_visits} زيارة')
    n_faults = tenant_query(Fault).filter_by(technician_id=t.id).count()
    n_faults += tenant_query(FaultTechnician).filter_by(technician_id=t.id).count()
    if n_faults:
        blockers.append(f'{n_faults} عطل')
    n_teams = tenant_query(MaintenanceTeam).filter(
        db.or_(MaintenanceTeam.leader_id == t.id, MaintenanceTeam.assistant_id == t.id)
    ).count()
    if n_teams:
        blockers.append(f'{n_teams} فريق صيانة')
    if blockers:
        flash('لا يمكن حذف الفني لارتباطه بـ: ' + '، '.join(blockers), 'error')
        return redirect(url_for('technicians'))
    _remove_technician_files(t)
    db.session.delete(t)
    db.session.commit()
    flash('تم حذف الفني', 'success')
    return redirect(url_for('technicians'))

# =============================================
# زيارات الصيانة
# =============================================
@app.route('/maintenance-visits')
def maintenance_visits():
    from operations import exclude_fault_visits, list_districts, visit_alerts, visit_stats
    from sqlalchemy.orm import joinedload
    from visit_cleanup import find_duplicate_visit_ids_from

    visits = exclude_fault_visits(
        tenant_query(MaintenanceVisit).options(
            joinedload(MaintenanceVisit.elevator).joinedload(Elevator.customer),
            joinedload(MaintenanceVisit.technician),
            joinedload(MaintenanceVisit.linked_fault),
        )
    ).all()
    from entity_links import natural_code_key
    visits = sorted(
        visits,
        key=lambda v: (natural_code_key(v.code), v.visit_date or date.min, v.id or 0),
    )
    elevators = tenant_query(Elevator).options(joinedload(Elevator.customer)).all()
    customers = tenant_query(Customer).order_by(Customer.name).all()
    contracts = tenant_query(Contract).order_by(Contract.start_date.desc()).all()
    technicians = tenant_query(Technician).filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول'])
    ).all()
    today = date.today()
    plan_default = f'{today.year}-{today.month:02d}'
    month_end = today.replace(day=monthrange(today.year, today.month)[1])
    maint_techs = [t for t in technicians if (t.team or 'عام') in ('صيانة', 'عام')] or list(technicians)
    from maintenance_teams import list_all_teams, team_to_dict
    teams_all = list_all_teams()
    maint_teams = [team_to_dict(t) for t in teams_all if t.active]
    all_teams = [team_to_dict(t) for t in teams_all]
    duplicate_visit_ids = find_duplicate_visit_ids_from(visits)
    return render_template(
        'maintenance-visits.html',
        visits=visits,
        elevators=elevators,
        customers=customers,
        contracts=contracts,
        technicians=technicians,
        visits_js=_visits_js_list(visits),
        customers_js=[{'id': c.id, 'code': c.code, 'name': c.name} for c in customers],
        elevators_js=[
            {'id': e.id, 'code': e.code, 'customer_id': e.customer_id,
             'customer': e.customer.name if e.customer else ''}
            for e in elevators
        ],
        contracts_js=[
            {'id': c.id, 'code': c.code, 'customer_id': c.customer_id} for c in contracts
        ],
        technicians_js=[{'id': t.id, 'name': t.name} for t in technicians],
        maint_technicians_js=[{'id': t.id, 'name': t.name} for t in maint_techs],
        maint_teams_js=maint_teams,
        all_teams_js=all_teams,
        visit_map_points=_visit_map_points(visits),
        next_visit_code=next_code(MaintenanceVisit, 'VI-', digits=5),
        visit_stats=visit_stats(),
        visit_alerts=visit_alerts(),
        plan_default_month=plan_default,
        ops_today=str(today),
        ops_tomorrow=str(today + timedelta(days=1)),
        ops_month_start=str(today.replace(day=1)),
        ops_month_end=str(month_end),
        maint_technicians=maint_techs,
        plan_districts=list_districts(),
        duplicate_visit_ids=duplicate_visit_ids,
    )

def build_elevator_profile(elevator_id):
    """ملخص المصعد + سجل مصروفاته (قطع غيار + صرف مخزن)."""
    elev = tenant_get_or_404(Elevator, elevator_id)
    customer = elev.customer

    parts = (
        tenant_query(PartsBilling).filter_by(elevator_id=elevator_id)
        .order_by(PartsBilling.billing_date.desc(), PartsBilling.id.desc())
        .all()
    )
    stock_moves = (
        tenant_query(StockMovement).filter_by(elevator_id=elevator_id, direction='صادر')
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
        .all()
    )

    ledger = []
    for p in parts:
        cost = float(p.cost_price or 0)
        ledger.append({
            'date': str(p.billing_date or ''),
            'code': p.code,
            'type': 'قطع غيار',
            'category': 'parts',
            'description': (p.description or 'تركيب قطع غيار').strip(),
            'amount': cost,
            'detail': (p.technician.name if p.technician else '') or (p.status or ''),
        })
    for m in stock_moves:
        amt = float(m.total_value or 0)
        if amt <= 0:
            amt = float((m.quantity or 0) * (m.unit_price or 0))
        item_name = m.item.name if m.item else ''
        ledger.append({
            'date': str(m.movement_date or ''),
            'code': m.code,
            'type': m.movement_type or 'صرف مخزن',
            'category': 'stock',
            'description': (m.reason or item_name or 'حركة مخزن').strip(),
            'amount': amt,
            'detail': item_name,
        })

    ledger.sort(key=lambda row: row.get('date') or '', reverse=True)

    parts_total = round(sum(r['amount'] for r in ledger if r['category'] == 'parts'), 2)
    stock_total = round(sum(r['amount'] for r in ledger if r['category'] == 'stock'), 2)
    total_cost = round(parts_total + stock_total, 2)

    visits = (
        tenant_query(MaintenanceVisit).filter_by(elevator_id=elevator_id)
        .order_by(MaintenanceVisit.visit_date.desc())
        .limit(8)
        .all()
    )
    faults = (
        tenant_query(Fault).filter_by(elevator_id=elevator_id)
        .order_by(Fault.reported_at.desc())
        .limit(8)
        .all()
    )

    active_contract = None
    from entity_links import active_contract_for_elevator
    ac = active_contract_for_elevator(elevator_id)
    if ac:
        active_contract = {'id': ac.id, 'code': ac.code, 'status': ac.status}

    return {
        'elevator': {
            'id': elev.id,
            'code': elev.code,
            'customer_id': elev.customer_id,
            'customer': customer.name if customer else '',
            'building': elev.building_name or '',
            'city': elev.city or '',
            'district': elev.district or '',
            'elev_type': elev.elev_type or '',
            'brand': elev.brand or '',
            'model': elev.model or '',
            'capacity_kg': elev.capacity_kg,
            'floors': elev.floors,
            'speed': elev.speed or '',
            'serial_number': elev.serial_number or '',
            'machine_type': elev.machine_type or '',
            'control_type': elev.control_type or '',
            'control_drive': elev.control_drive or '',
            'control_operation': elev.control_operation or '',
            'control_detail': elev.control_detail or '',
            'install_date': str(elev.install_date or ''),
            'last_maintenance': str(elev.last_maintenance or ''),
            'next_maintenance': str(elev.next_maintenance or ''),
            'status': elev.status or '',
            'notes': elev.notes or '',
        },
        'contract': active_contract,
        'costs': {
            'total': total_cost,
            'parts_total': parts_total,
            'stock_total': stock_total,
            'count': len(ledger),
            'ledger': ledger,
        },
        'activity': {
            'visits_count': tenant_query(MaintenanceVisit).filter_by(elevator_id=elevator_id).count(),
            'faults_count': tenant_query(Fault).filter_by(elevator_id=elevator_id).count(),
            'recent_visits': [
                {
                    'code': v.code,
                    'date': str(v.visit_date or ''),
                    'type': v.visit_type or '',
                    'status': v.status or '',
                }
                for v in visits
            ],
            'recent_faults': [
                {
                    'code': f.code,
                    'date': str(f.reported_at.date() if f.reported_at else ''),
                    'type': f.fault_type or '',
                    'status': f.status or '',
                }
                for f in faults
            ],
        },
    }


@app.route('/api/elevators/<int:elevator_id>/profile')
def api_elevator_profile(elevator_id):
    return jsonify(build_elevator_profile(elevator_id))


@app.route('/api/elevators/<int:elevator_id>/links')
def api_elevator_links(elevator_id):
    from entity_links import elevator_link_payload
    return jsonify(elevator_link_payload(elevator_id))


def _find_recent_duplicate_visit(payload: dict, tech_ids: list[int]):
    """تجاهل إعادة إرسال نفس نموذج الزيارة خلال دقائق قليلة."""
    from technician_assignments import visit_technician_ids

    window_start = datetime.utcnow() - timedelta(minutes=5)
    candidates = (
        tenant_query(MaintenanceVisit).filter(
            MaintenanceVisit.created_at >= window_start,
            MaintenanceVisit.elevator_id == payload['elevator_id'],
            MaintenanceVisit.contract_id == payload['contract_id'],
            MaintenanceVisit.technician_id == payload['technician_id'],
            MaintenanceVisit.visit_type == payload['visit_type'],
            MaintenanceVisit.visit_date == payload['visit_date'],
            MaintenanceVisit.visit_time == payload['visit_time'],
            MaintenanceVisit.priority == payload['priority'],
            MaintenanceVisit.status == payload['status'],
            MaintenanceVisit.works_done == payload['works_done'],
            MaintenanceVisit.observations == payload['observations'],
            MaintenanceVisit.notes == payload['notes'],
        )
        .order_by(MaintenanceVisit.id.desc())
        .all()
    )
    normalized_ids = list(tech_ids or [])
    for visit in candidates:
        if visit_technician_ids(visit) == normalized_ids:
            return visit
    return None


@app.route('/maintenance-visits/add', methods=['POST'])
def visit_add():
    from entity_links import resolve_visit_links
    from form_validation import visit_form_error
    from technician_assignments import parse_technician_ids, sync_visit_technicians

    err = visit_form_error(request.form, parse_technician_ids=parse_technician_ids)
    if err:
        flash(err, 'error')
        return redirect(url_for('maintenance_visits'))

    links = resolve_visit_links(
        request.form['elevator_id'],
        request.form.get('contract_id'),
        request.form.get('visit_date'),
    )

    visit_type = request.form.get('visit_type', 'صيانة دورية')
    tech_ids = parse_technician_ids(request.form)
    visit_date = datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date()
    from work_calendar import work_day_validation_error
    werr = work_day_validation_error(visit_date)
    if werr:
        flash(werr, 'error')
        return redirect(url_for('maintenance_visits'))

    visit_payload = {
        'elevator_id': links['elevator_id'],
        'technician_id': tech_ids[0] if tech_ids else None,
        'contract_id': links['contract_id'],
        'visit_type': visit_type,
        'visit_date': visit_date,
        'visit_time': request.form.get('visit_time', ''),
        'priority': request.form.get('priority', 'عادية'),
        'status': request.form.get('status', 'مجدولة'),
        'works_done': request.form.get('works_done', ''),
        'observations': request.form.get('observations', ''),
        'notes': request.form.get('notes', ''),
    }
    duplicate = _find_recent_duplicate_visit(visit_payload, tech_ids)
    if duplicate:
        return redirect(url_for('maintenance_visits'))

    v = MaintenanceVisit(
        code          = next_code(MaintenanceVisit, 'VI-', digits=5),
        elevator_id   = visit_payload['elevator_id'],
        technician_id = visit_payload['technician_id'],
        contract_id   = visit_payload['contract_id'],
        visit_type    = visit_payload['visit_type'],
        visit_date    = visit_payload['visit_date'],
        visit_time    = visit_payload['visit_time'],
        priority      = visit_payload['priority'],
        status        = visit_payload['status'],
        works_done    = visit_payload['works_done'],
        observations  = visit_payload['observations'],
        notes         = visit_payload['notes'],
    )
    assign_organization(v)
    db.session.add(v)
    db.session.flush()
    sync_visit_technicians(v, tech_ids)

    db.session.commit()
    return redirect(url_for('maintenance_visits'))
@app.route('/maintenance-visits/edit/<int:id>', methods=['POST'])
def visit_edit(id):
    from entity_links import resolve_visit_links
    from form_validation import visit_form_error
    from technician_assignments import parse_technician_ids, sync_visit_technicians

    err = visit_form_error(request.form, parse_technician_ids=parse_technician_ids)
    if err:
        flash(err, 'error')
        return redirect(url_for('maintenance_visits'))

    v = tenant_get_or_404(MaintenanceVisit, id)
    links = resolve_visit_links(
        request.form['elevator_id'],
        request.form.get('contract_id'),
        request.form.get('visit_date'),
    )
    tech_ids = parse_technician_ids(request.form)
    visit_date = datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date()
    from work_calendar import work_day_validation_error
    werr = work_day_validation_error(visit_date)
    if werr:
        flash(werr, 'error')
        return redirect(url_for('maintenance_visits'))
    v.elevator_id   = links['elevator_id']
    v.contract_id   = links['contract_id']
    v.technician_id = tech_ids[0] if tech_ids else None
    v.visit_type    = request.form.get('visit_type','')
    v.visit_date    = visit_date
    v.visit_time    = request.form.get('visit_time','')
    v.priority      = request.form.get('priority','عادية')
    v.status        = request.form.get('status','مجدولة')
    v.works_done    = request.form.get('works_done','')
    v.observations  = request.form.get('observations','')
    v.notes         = request.form.get('notes','')

    sync_visit_technicians(v, tech_ids)
    db.session.commit()
    return redirect(url_for('maintenance_visits'))


def _purge_visit_dependencies(visit_id: int) -> None:
    """فك الارتباطات التي تمنع حذف الزيارة."""
    v = tenant_query(MaintenanceVisit).filter_by(id=visit_id).first()
    if not v:
        return
    tenant_query(VisitTechnician).filter_by(visit_id=visit_id).delete(synchronize_session=False)
    tenant_query(Fault).filter_by(visit_id=visit_id).update(
        {Fault.visit_id: None}, synchronize_session=False
    )
    tenant_query(PartsBilling).filter_by(visit_id=visit_id).update(
        {PartsBilling.visit_id: None}, synchronize_session=False
    )
    if v.fault_id:
        fault = tenant_query(Fault).filter_by(id=v.fault_id).first()
        if fault and fault.visit_id == visit_id:
            fault.visit_id = None
        v.fault_id = None


@app.route('/maintenance-visits/cleanup-duplicates', methods=['POST'])
def maintenance_cleanup_duplicates():
    err = enforce_admin_delete()
    if err:
        return err
    from visit_cleanup import remove_duplicate_visits
    result = remove_duplicate_visits()
    flash(f'تم حذف {result["deleted"]} زيارة مكررة', 'success')
    return redirect(url_for('maintenance_visits'))


@app.route('/maintenance-visits/delete/<int:id>', methods=['POST'])
def visit_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    v = tenant_get_or_404(MaintenanceVisit, id)
    _purge_visit_dependencies(id)
    db.session.delete(v)
    db.session.commit()
    return redirect(url_for('maintenance_visits'))


@app.route('/api/maintenance/visits', methods=['GET'])
def api_maintenance_visits():
    """قائمة زيارات شهر معيّن — لتحديث الجدول بعد تخطيط الشهر."""
    from operations import exclude_fault_visits

    month = request.args.get('month', '').strip()
    q = exclude_fault_visits(
        tenant_query(MaintenanceVisit).order_by(MaintenanceVisit.visit_date.desc())
    )
    if month and '-' in month:
        try:
            year, m = map(int, month.split('-', 1))
            start = date(year, m, 1)
            end = date(year, m, monthrange(year, m)[1])
            q = q.filter(
                MaintenanceVisit.visit_date >= start,
                MaintenanceVisit.visit_date <= end,
            )
        except (TypeError, ValueError):
            return jsonify({'error': 'صيغة الشهر غير صحيحة (YYYY-MM)'}), 400
    return jsonify({'visits': _visits_js_list(q.all()), 'month': month})


@app.route('/api/maintenance/plan', methods=['GET'])
def api_get_plan():
    from operations import get_plan, list_districts

    plan_month = request.args.get('plan_month', '').strip()
    if not plan_month:
        return jsonify({'error': 'حدد شهر الخطة'}), 400
    try:
        return jsonify(get_plan(plan_month) | {'district_list': list_districts()})
    except Exception as exc:
        app.logger.exception('get_plan failed for %s', plan_month)
        return jsonify({'error': f'تعذّر تحميل الخطة: {exc}'}), 500


@app.route('/api/maintenance/districts', methods=['GET'])
def api_list_districts():
    from operations import list_districts

    return jsonify({'districts': list_districts()})


@app.route('/api/maintenance/district/<path:district>/elevators', methods=['GET'])
def api_district_elevators(district):
    from operations import elevators_for_district

    return jsonify({'elevators': elevators_for_district(district)})


@app.route('/api/maintenance/plan/add-visit', methods=['POST'])
def api_plan_add_visit():
    from operations import add_manual_plan_visit, get_plan

    data = request.get_json(silent=True) or request.form
    plan_month = data.get('plan_month', '').strip()
    elevator_id = data.get('elevator_id')
    visit_date = data.get('visit_date', '').strip()
    if not plan_month or not elevator_id or not visit_date:
        return jsonify({'error': 'المنطقة والمصعد والتاريخ مطلوبة'}), 400
    try:
        row = add_manual_plan_visit(plan_month, int(elevator_id), visit_date)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': f'تعذّر الإضافة: {exc}'}), 500
    return jsonify(get_plan(plan_month) | {'added': row})


@app.route('/api/maintenance/generate-district-plan', methods=['POST'])
def api_generate_district_plan():
    from operations import generate_district_plan

    data = request.get_json(silent=True) or request.form
    ym = (data.get('plan_month') or '').strip()
    district = (data.get('district') or '').strip()
    if not district:
        return jsonify({'error': 'اختر المنطقة'}), 400
    if ym and '-' in ym:
        year, month = map(int, ym.split('-', 1))
    else:
        today = date.today()
        year, month = today.year, today.month
    preview = str(data.get('preview', '')).lower() in ('1', 'true', 'yes')
    confirmed = str(data.get('confirmed', '')).lower() in ('1', 'true', 'yes')
    if preview:
        return jsonify(generate_district_plan(year, month, district, preview_only=True))
    if not confirmed:
        return jsonify({'error': 'يجب عرض المعاينة ثم الضغط على «تأكيد التفعيل»'}), 400
    return jsonify(generate_district_plan(year, month, district, preview_only=False))


@app.route('/api/maintenance/assign-visits', methods=['POST'])
def api_assign_visits():
    from operations import assign_visits_to_technician, get_plan
    from maintenance_teams import assign_visits_to_team

    data = request.get_json(silent=True) or request.form
    visit_ids = data.get('visit_ids') or []
    if isinstance(visit_ids, str):
        visit_ids = [x for x in visit_ids.split(',') if x.strip()]
    team_id = data.get('team_id')
    tech_id = data.get('technician_id')
    plan_month = data.get('plan_month', '').strip()
    if not visit_ids or (not team_id and not tech_id):
        return jsonify({'error': 'اختر الزيارات والفريق'}), 400
    try:
        if team_id:
            n = assign_visits_to_team([int(x) for x in visit_ids], int(team_id), plan_month)
        else:
            n = assign_visits_to_technician([int(x) for x in visit_ids], int(tech_id), plan_month)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if not plan_month and visit_ids:
        first = tenant_query(MaintenanceVisit).filter_by(id=int(visit_ids[0])).first()
        if first and first.plan_month:
            plan_month = first.plan_month
        elif first and first.visit_date:
            plan_month = first.visit_date.strftime('%Y-%m')
    result = {'updated': n}
    if plan_month:
        result.update(get_plan(plan_month))
    return jsonify(result)


@app.route('/api/maintenance/generate-plan', methods=['POST'])
def api_generate_plan():
    from operations import generate_monthly_plan

    data = request.get_json(silent=True) or request.form
    ym = (data.get('plan_month') or '').strip()
    if ym and '-' in ym:
        year, month = map(int, ym.split('-', 1))
    else:
        today = date.today()
        if today.month == 12:
            year, month = today.year + 1, 1
        else:
            year, month = today.year, today.month + 1
    preview = str(data.get('preview', '')).lower() in ('1', 'true', 'yes')
    confirmed = str(data.get('confirmed', '')).lower() in ('1', 'true', 'yes')
    if preview:
        return jsonify(generate_monthly_plan(
            year, month, replace_draft=bool(data.get('replace')), preview_only=True,
        ))
    if not confirmed:
        return jsonify({'error': 'يجب عرض المعاينة ثم الضغط على «تأكيد التفعيل»'}), 400
    plan_month = f'{year}-{month:02d}'
    result = generate_monthly_plan(
        year, month, replace_draft=bool(data.get('replace')), preview_only=False,
    )
    auto_dist = str(data.get('auto_distribute_teams', 'true')).lower() in ('1', 'true', 'yes')
    if auto_dist:
        from maintenance_teams import distribute_plan_to_teams
        dist = distribute_plan_to_teams(plan_month, preview_only=False)
        if dist.get('error'):
            result['team_distribution_error'] = dist['error']
        else:
            result['teams_assigned'] = dist.get('assigned', 0)
            result['teams_skipped'] = dist.get('skipped', 0)
    return jsonify(result)


@app.route('/api/work-calendar')
def api_work_calendar():
    from work_calendar import month_calendar, work_calendar_summary

    if not require_login():
        return jsonify({'error': 'يجب تسجيل الدخول'}), 401
    ym = (request.args.get('month') or '').strip()
    if ym and '-' in ym:
        return jsonify(month_calendar(ym))
    return jsonify({'summary': work_calendar_summary()})


@app.route('/api/work-calendar/check')
def api_work_calendar_check():
    from work_calendar import is_working_day, non_working_reason, next_working_day

    if not require_login():
        return jsonify({'error': 'يجب تسجيل الدخول'}), 401
    raw = (request.args.get('date') or '').strip()[:10]
    if not raw:
        return jsonify({'error': 'حدد التاريخ YYYY-MM-DD'}), 400
    try:
        d = datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'تاريخ غير صالح'}), 400
    working = is_working_day(d)
    payload = {
        'date': raw,
        'working': working,
        'reason': None if working else non_working_reason(d),
    }
    if not working:
        nxt = next_working_day(d)
        if nxt != d:
            payload['next_work_day'] = nxt.isoformat()
    return jsonify(payload)


@app.route('/api/maintenance/plan-readiness')
def api_plan_readiness():
    from plan_pipeline import get_plan_readiness

    plan_month = (request.args.get('plan_month') or '').strip()
    if not plan_month or '-' not in plan_month:
        return jsonify({'error': 'حدد شهر الخطة (YYYY-MM)'}), 400
    return jsonify(get_plan_readiness(plan_month))


@app.route('/api/maintenance/run-plan', methods=['POST'])
def api_run_plan():
    from plan_pipeline import preview_full_plan, run_full_plan

    data = request.get_json(silent=True) or request.form
    ym = (data.get('plan_month') or '').strip()
    if not ym or '-' not in ym:
        return jsonify({'error': 'حدد شهر الخطة (YYYY-MM)'}), 400
    year, month = map(int, ym.split('-', 1))
    preview = str(data.get('preview', '')).lower() in ('1', 'true', 'yes')
    confirmed = str(data.get('confirmed', '')).lower() in ('1', 'true', 'yes')
    replace = bool(data.get('replace'))
    if preview:
        return jsonify(preview_full_plan(year, month, replace_draft=replace))
    if not confirmed:
        return jsonify({'error': 'اعرض معاينة الخطة ثم اضغط «تشغيل الخطة»'}), 400
    result = run_full_plan(year, month, replace_draft=replace)
    if result.get('error'):
        return jsonify(result), 400
    return jsonify(result)


@app.route('/api/maintenance/cancel-plan', methods=['POST'])
def api_cancel_plan():
    from operations import cancel_monthly_plan

    data = request.get_json(silent=True) or request.form
    plan_month = (data.get('plan_month') or '').strip()
    if not plan_month or '-' not in plan_month:
        return jsonify({'error': 'حدد شهر الخطة (YYYY-MM)'}), 400
    try:
        return jsonify(cancel_monthly_plan(plan_month))
    except Exception as exc:
        app.logger.exception('cancel_plan failed for %s', plan_month)
        return jsonify({'error': f'تعذّر إلغاء الخطة: {exc}'}), 500


@app.route('/api/maintenance/assign-district', methods=['POST'])
def api_assign_district():
    from operations import get_plan
    from maintenance_teams import assign_district_team

    data = request.get_json(silent=True) or request.form
    plan_month = (data.get('plan_month') or '').strip()
    district = (data.get('district') or '').strip()
    team_id = data.get('team_id')
    if not team_id:
        return jsonify({'error': 'اختر الفريق'}), 400
    try:
        n = assign_district_team(
            plan_month,
            district,
            int(team_id),
            only_unassigned=bool(data.get('only_unassigned', True)),
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    result = {'updated': n}
    if plan_month:
        result.update(get_plan(plan_month))
    return jsonify(result)


@app.route('/api/maintenance/teams', methods=['GET'])
def api_list_maintenance_teams():
    from maintenance_teams import list_all_teams, team_to_dict
    return jsonify({'teams': [team_to_dict(t) for t in list_all_teams()]})


@app.route('/api/maintenance/teams', methods=['POST'])
def api_save_maintenance_team():
    from operations import next_code
    from maintenance_teams import team_to_dict

    data = request.get_json(silent=True) or request.form
    team_id = data.get('id')
    name = (data.get('name') or '').strip()
    leader_id = data.get('leader_id')
    assistant_id = data.get('assistant_id') or None
    if assistant_id in ('', '0', 0):
        assistant_id = None
    if not name or not leader_id:
        return jsonify({'error': 'اسم الفريق ورئيس الفريق مطلوبان'}), 400
    if assistant_id and int(assistant_id) == int(leader_id):
        return jsonify({'error': 'المساعد يجب أن يختلف عن رئيس الفريق'}), 400
    if team_id:
        team = tenant_get_or_404(MaintenanceTeam, int(team_id))
    else:
        team = MaintenanceTeam(code=next_code(MaintenanceTeam, 'MT-', digits=3))
        assign_organization(team)
        db.session.add(team)
    team.name = name
    team.leader_id = int(leader_id)
    team.assistant_id = int(assistant_id) if assistant_id else None
    team.active = str(data.get('active', '1')).lower() not in ('0', 'false', 'no')
    team.sort_order = int(data.get('sort_order') or team.sort_order or 0)
    team.notes = (data.get('notes') or '').strip() or None
    db.session.commit()
    return jsonify({'team': team_to_dict(team)})


@app.route('/api/maintenance/teams/<int:team_id>/delete', methods=['POST'])
def api_delete_maintenance_team(team_id):
    err = enforce_admin_delete(json_response=True)
    if err:
        return err
    team = tenant_get_or_404(MaintenanceTeam, team_id)
    assigned = tenant_query(MaintenanceVisit).filter_by(maintenance_team_id=team.id).count()
    if assigned:
        return jsonify({'error': f'لا يمكن الحذف — {assigned} زيارة مرتبطة بهذا الفريق'}), 400
    db.session.delete(team)
    db.session.commit()
    return jsonify({'deleted': team_id})


@app.route('/api/maintenance/distribute-teams', methods=['POST'])
def api_distribute_teams():
    from maintenance_teams import distribute_plan_to_teams

    data = request.get_json(silent=True) or request.form
    plan_month = (data.get('plan_month') or '').strip()
    if not plan_month or '-' not in plan_month:
        return jsonify({'error': 'حدد شهر الخطة (YYYY-MM)'}), 400
    preview = str(data.get('preview', '')).lower() in ('1', 'true', 'yes')
    confirmed = str(data.get('confirmed', '')).lower() in ('1', 'true', 'yes')
    if preview:
        return jsonify(distribute_plan_to_teams(plan_month, preview_only=True))
    if not confirmed:
        return jsonify({'error': 'اعرض معاينة التوزيع ثم اضغط «تأكيد التوزيع»'}), 400
    result = distribute_plan_to_teams(plan_month, preview_only=False)
    if result.get('error'):
        return jsonify(result), 400
    return jsonify(result)


@app.route('/api/maintenance/dispatch/<int:tech_id>', methods=['POST'])
def api_dispatch_route(tech_id):
    from operations import dispatch_technician_route

    data = request.get_json(silent=True) or request.form
    dispatch_day = (data.get('dispatch_day') or 'today').strip()
    result = dispatch_technician_route(
        tech_id,
        base_url=request.url_root,
        dispatch_day=dispatch_day,
    )
    result['whatsapp_url'] = result.get('whatsapp_url') or ''
    if not result['whatsapp_url'] and not result.get('error'):
        result['error'] = 'لا يوجد رقم واتساب للفني أو لا توجد زيارات'
    return jsonify(result)


@app.route('/api/faults/<int:fault_id>/dispatch', methods=['POST'])
def api_dispatch_fault(fault_id):
    from operations import dispatch_fault
    from whatsapp_support import notify_customer_stage

    result = dispatch_fault(fault_id, request.url_root)
    fault = tenant_query(Fault).filter_by(id=fault_id).first()
    if fault and not result.get('error'):
        cust = notify_customer_stage(fault, 'assigned', next_code_fn=next_code)
        if cust.get('ok') and cust.get('url'):
            result['customer_whatsapp_url'] = cust['url']
            db.session.commit()
    return jsonify(result)


@app.route('/api/faults/<int:fault_id>/customer-notify', methods=['POST'])
def api_fault_customer_notify(fault_id):
    """المرحلة 2 — إرسال/تجهيز رسالة حالة واتساب للعميل."""
    from whatsapp_support import JOURNEY_STAGES, notify_customer_stage

    fault = tenant_get_or_404(Fault, fault_id)
    data = request.get_json(silent=True) or request.form or {}
    stage = (data.get('stage') or '').strip()
    force = str(data.get('force') or '').lower() in ('1', 'true', 'yes')
    if stage not in JOURNEY_STAGES:
        return jsonify({'ok': False, 'error': 'مرحلة غير صالحة'}), 400
    report_url = ''
    if stage == 'resolved':
        report_url = request.url_root.rstrip('/') + f'/faults/{fault.id}/report?print=1'
    result = notify_customer_stage(
        fault, stage, next_code_fn=next_code, force=force, report_url=report_url,
    )
    if result.get('ok') and not result.get('skipped'):
        db.session.commit()
    elif result.get('ok'):
        db.session.rollback()
    else:
        db.session.rollback()
        return jsonify(result), 400
    return jsonify(result)


# =============================================
# واجهة الفني — بوابة الجوال (تسجيل دخول + فريق صيانة/أعطال)
# =============================================
@app.route('/field/manifest.webmanifest')
def field_manifest():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'field-manifest.webmanifest',
        mimetype='application/manifest+json',
    )


@app.route('/field/sw.js')
def field_service_worker():
    resp = send_from_directory(
        os.path.join(app.root_path, 'static'),
        'field-sw.js',
        mimetype='application/javascript',
    )
    resp.headers['Service-Worker-Allowed'] = '/field/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/field/login', methods=['GET', 'POST'])
def field_login():
    from field_auth import (
        field_login_technician,
        find_technician_by_login,
        verify_technician_pin,
    )

    if _resolve_field_technician_id() and not request.args.get('tech_id'):
        return redirect(url_for('field_home'))

    error = None
    login_id = ''
    next_url = request.args.get('next') or request.form.get('next') or ''

    if request.method == 'POST':
        login_id = (request.form.get('login_id') or '').strip()
        pin = (request.form.get('pin') or '').strip()
        from field_auth import sync_technician_field_pin, technician_has_field_pin
        from liftcore_security import (
            check_field_pin_rate_limit,
            clear_field_pin_attempts,
            record_field_pin_failure,
        )

        allowed, retry_sec = check_field_pin_rate_limit(login_id)
        if not allowed:
            error = f'محاولات كثيرة — انتظر {retry_sec} ثانية ثم حاول مجدداً.'
        else:
            tech = find_technician_by_login(login_id)
            if not tech:
                raw = login_id.lower()
                inactive = tenant_query(Technician).filter(Technician.code.ilike(raw)).first()
                if inactive and (inactive.status or 'متاح') not in ('نشط', 'متاح', 'مشغول'):
                    error = f'حساب الفني غير مفعّل للجوال (الحالة: {inactive.status}) — راجع المشرف'
                else:
                    error = 'لم يُعثر على فني بهذا الكود أو الجوال'
                record_field_pin_failure(login_id)
            elif not technician_has_field_pin(tech):
                error = 'لم يُضبط رمز دخول لهذا الفني — راجع المشرف (التوقيع الرقمي في ملف الفني)'
            elif not verify_technician_pin(tech, pin):
                error = 'رمز الدخول غير صحيح — تأكد من 6 أرقام بدون مسافات'
                record_field_pin_failure(login_id)
            else:
                sync_technician_field_pin(tech)
                db.session.commit()
                clear_field_pin_attempts(login_id)
                field_login_technician(tech)
                dest = next_url if next_url.startswith('/field') else url_for('field_home')
                return redirect(dest)

    return render_template(
        'field-login.html',
        error=error,
        login_id=login_id,
        next_url=next_url,
    )


@app.route('/field/logout')
def field_logout():
    from field_auth import field_logout_technician

    field_logout_technician()
    return redirect(url_for('field_login'))


@app.route('/field')
def field_home():
    tech_id = getattr(g, 'field_tech_id', None) or _resolve_field_technician_id()
    if not tech_id:
        return redirect(url_for('field_login'))

    from field_auth import technician_portal_kind
    from operations import field_technician_payload

    ctx = _field_portal_context(tech_id)
    kind = technician_portal_kind(ctx['field_tech'])
    payload = field_technician_payload(tech_id, request.url_root, portal_kind=kind)
    return render_template('field.html', payload=payload, error=None, **ctx)


@app.route('/api/field/me')
def api_field_me():
    tech_id = getattr(g, 'field_tech_id', None)
    from field_auth import technician_portal_kind
    from operations import field_technician_payload

    tech = tenant_get_or_404(Technician, tech_id)
    kind = technician_portal_kind(tech)
    payload = field_technician_payload(tech_id, request.url_root, portal_kind=kind)
    return jsonify({'ok': True, **payload})


@app.route('/field/visit/<int:visit_id>')
def field_visit(visit_id):
    from operations import field_visit_detail

    tech_id = getattr(g, 'field_tech_id', None) or _resolve_field_technician_id()
    try:
        detail = field_visit_detail(visit_id, tech_id)
    except PermissionError as e:
        ctx = _field_portal_context(tech_id) if tech_id else {}
        return render_template('field.html', error=str(e), payload=None, **ctx), 403
    detail['report_url'] = url_for('field_visit_report', visit_id=visit_id)
    ctx = _field_portal_context(tech_id)
    return render_template('field-visit.html', visit=detail, **ctx)


@app.route('/field/visit/<int:visit_id>/report')
def field_visit_report(visit_id):
    from operations import stamp_field_visit_report_start, visit_report_payload

    tech_id = getattr(g, 'field_tech_id', None) or _resolve_field_technician_id()
    read_only = request.args.get('print') == '1' or request.args.get('readonly') == '1'
    from_field = bool(getattr(g, 'field_tech_id', None))
    try:
        if from_field and not read_only:
            stamp_field_visit_report_start(visit_id, tech_id=tech_id)
        payload = visit_report_payload(
            visit_id,
            editable=not read_only,
            tech_id=tech_id,
            base_url=request.url_root,
            field_times_locked=from_field and not read_only,
        )
    except PermissionError as e:
        ctx = _field_portal_context(tech_id) if tech_id else {}
        return render_template('field.html', error=str(e), payload=None, **ctx), 403
    payload['back_url'] = url_for('field_visit', visit_id=visit_id)
    payload['read_only_mode'] = read_only
    return render_template('visit-report.html', **payload)


@app.route('/maintenance-visits/<int:visit_id>/report')
def maintenance_visit_report(visit_id):
    from operations import visit_report_payload

    read_only = request.args.get('print') == '1' or request.args.get('readonly') == '1'
    payload = visit_report_payload(
        visit_id, editable=not read_only, base_url=request.url_root
    )
    payload['back_url'] = url_for('maintenance_visits')
    payload['read_only_mode'] = read_only
    if not read_only and payload.get('tech_id'):
        payload['field_edit_url'] = url_for(
            'field_visit_report', visit_id=visit_id, tech_id=payload['tech_id']
        )
    else:
        payload['field_edit_url'] = None
    return render_template('visit-report.html', **payload)


@app.route('/field/fault/<int:fault_id>')
def field_fault(fault_id):
    from operations import field_fault_detail

    tech_id = getattr(g, 'field_tech_id', None) or _resolve_field_technician_id()
    try:
        detail = field_fault_detail(fault_id, tech_id)
    except PermissionError as e:
        ctx = _field_portal_context(tech_id) if tech_id else {}
        return render_template('field.html', error=str(e), payload=None, **ctx), 403
    ctx = _field_portal_context(tech_id)
    return render_template('field-fault.html', fault=detail, **ctx)


@app.route('/field/fault/<int:fault_id>/report')
def field_fault_report(fault_id):
    from operations import fault_report_payload, stamp_field_fault_report_start

    tech_id = getattr(g, 'field_tech_id', None) or _resolve_field_technician_id()
    from_field = bool(getattr(g, 'field_tech_id', None))
    try:
        if from_field:
            stamp_field_fault_report_start(fault_id, tech_id=tech_id)
        payload = fault_report_payload(
            fault_id,
            editable=True,
            tech_id=tech_id,
            base_url=request.url_root,
            field_times_locked=from_field,
        )
    except PermissionError as e:
        ctx = _field_portal_context(tech_id) if tech_id else {}
        return render_template('field.html', error=str(e), payload=None, **ctx), 403
    payload['back_url'] = url_for('field_fault', fault_id=fault_id)
    return render_template('fault-report.html', **payload)


@app.route('/faults/<int:fault_id>/report')
def office_fault_report(fault_id):
    from operations import fault_report_payload

    read_only = request.args.get('print') == '1' or request.args.get('readonly') == '1'
    payload = fault_report_payload(
        fault_id, editable=not read_only, base_url=request.url_root
    )
    payload['back_url'] = url_for('faults')
    if not read_only and payload.get('tech_id'):
        payload['field_edit_url'] = url_for(
            'field_fault_report', fault_id=fault_id, tech_id=payload['tech_id']
        )
    else:
        payload['field_edit_url'] = None
    return render_template('fault-report.html', **payload)


@app.route('/api/faults/<int:fault_id>/report', methods=['POST'])
def api_save_fault_report(fault_id):
    from operations import save_fault_report
    from technician_assignments import technician_assigned_to_fault
    from whatsapp_support import notify_customer_stage

    tech_id = getattr(g, 'field_tech_id', None)
    if tech_id:
        f = tenant_get_or_404(Fault, fault_id)
        if not technician_assigned_to_fault(f, tech_id):
            return jsonify({'ok': False, 'error': 'العطل غير مخصص لهذا الفني'}), 403

    data = request.get_json(silent=True) or {}
    mark_resolved = bool(data.pop('mark_resolved', False))
    try:
        save_fault_report(fault_id, data, mark_resolved=mark_resolved)
        result = {'ok': True, 'fault_id': fault_id}
        if mark_resolved:
            fault = tenant_query(Fault).filter_by(id=fault_id).first()
            if fault:
                cust = notify_customer_stage(
                    fault, 'resolved', next_code_fn=next_code, force=True,
                )
                db.session.commit()
                if cust.get('ok') and cust.get('url'):
                    result['customer_whatsapp_url'] = cust['url']
                    result['customer_wa'] = {
                        'thread_code': cust.get('thread_code'),
                        'fault_code': cust.get('fault_code'),
                        'label': cust.get('label'),
                        'pending_send': cust.get('pending_send', True),
                        'log_id': cust.get('log_id'),
                    }
        return jsonify(result)
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400


@app.route('/api/signatures/verify', methods=['POST'])
def api_verify_signature():
    from signature_auth import verify_signature_credentials
    from technician_assignments import technician_assigned_to_fault, technician_assigned_to_visit

    data = request.get_json(silent=True) or {}
    national_id = (data.get('national_id') or '').strip()
    pin = (data.get('pin') or '').strip()
    role = (data.get('role') or 'technician').strip()
    visit_id = data.get('visit_id')
    fault_id = data.get('fault_id')
    visit_technician_id = None
    if visit_id:
        v = tenant_query(MaintenanceVisit).filter_by(id=visit_id).first()
        if v:
            field_tid = getattr(g, 'field_tech_id', None) or _resolve_field_technician_id()
            if field_tid and technician_assigned_to_visit(v, field_tid):
                visit_technician_id = field_tid
            else:
                visit_technician_id = v.technician_id
    elif fault_id:
        f = tenant_query(Fault).filter_by(id=fault_id).first()
        if f:
            field_tid = getattr(g, 'field_tech_id', None) or _resolve_field_technician_id()
            if field_tid and technician_assigned_to_fault(f, field_tid):
                visit_technician_id = field_tid
            elif current_user():
                visit_technician_id = None
            else:
                visit_technician_id = f.technician_id

    result = verify_signature_credentials(
        national_id=national_id,
        pin=pin,
        role=role,
        verify_password_fn=verify_password,
        settings_row=get_app_settings(),
        visit_technician_id=visit_technician_id,
    )
    if not result.get('ok'):
        return jsonify(result), 401

    sig_path = result.pop('signature_path', '')
    result['signature_data'] = _signature_data_url(sig_path)
    if not result['signature_data'] and sig_path and not str(sig_path).endswith('.enc'):
        result['signature_url'] = upload_url(sig_path)
    if not result['signature_data'] and not result.get('signature_url'):
        app.logger.warning('signature image missing for path=%r', sig_path)
        return jsonify({
            'ok': False,
            'error': 'لا توجد صورة توقيع مسجّلة — ارسم التوقيع يدوياً أو أضفه من الإعدادات → التوقيعات',
        }), 400
    result['signed_at'] = datetime.utcnow().isoformat() + 'Z'
    return jsonify(result)


def _signature_rel_paths(relative_path: str) -> list[str]:
    """Normalize a stored signature path and return relative candidates."""
    rel = relative_path.replace('\\', '/').lstrip('/')
    if rel.startswith('static/'):
        rel = rel[len('static/') :]
    candidates = [rel]
    if not rel.startswith('uploads/'):
        candidates.append(f'uploads/{rel}')
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def _signature_abs_paths(relative_path: str) -> list[str]:
    """Absolute file paths to probe for a stored signature image."""
    rel_paths = _signature_rel_paths(relative_path)
    abs_paths: list[str] = []
    seen: set[str] = set()
    for rel in rel_paths:
        for base in (app.root_path, os.path.join(app.root_path, 'static')):
            abs_path = os.path.join(base, rel.replace('/', os.sep))
            if abs_path not in seen:
                seen.add(abs_path)
                abs_paths.append(abs_path)
    return abs_paths


def _signature_data_url(relative_path: str) -> str:
    from signature_crypto import decrypt_bytes, image_data_url, load_encrypted_signature

    if not relative_path:
        return ''
    rel_paths = _signature_rel_paths(relative_path)

    if rel_paths[0].endswith('.enc'):
        for rel in rel_paths:
            try:
                raw = load_encrypted_signature(app.root_path, app.config['SECRET_KEY'], rel)
                return image_data_url(raw)
            except (FileNotFoundError, ValueError):
                pass
        for abs_path in _signature_abs_paths(relative_path):
            if not abs_path.endswith('.enc') or not os.path.isfile(abs_path):
                continue
            try:
                with open(abs_path, 'rb') as fh:
                    raw = decrypt_bytes(fh.read(), app.config['SECRET_KEY'])
                return image_data_url(raw)
            except (ValueError, OSError):
                continue
        return ''

    for abs_path in _signature_abs_paths(relative_path):
        if os.path.isfile(abs_path):
            with open(abs_path, 'rb') as fh:
                return image_data_url(fh.read())
    return ''


@app.route('/api/maintenance-visits/<int:visit_id>/report', methods=['POST'])
def api_save_visit_report(visit_id):
    from operations import save_visit_report

    tech_id = getattr(g, 'field_tech_id', None)
    if tech_id:
        v = tenant_get_or_404(MaintenanceVisit, visit_id)
        if v.technician_id and v.technician_id != tech_id:
            return jsonify({'ok': False, 'error': 'الزيارة غير مخصصة لهذا الفني'}), 403

    data = request.get_json(silent=True) or {}
    mark_complete = bool(data.pop('mark_complete', False))
    status = data.pop('status', 'مكتملة')
    try:
        save_visit_report(
            visit_id,
            data,
            mark_complete=mark_complete,
            status=status,
            preserve_field_times=bool(tech_id),
        )
        return jsonify({'ok': True, 'visit_id': visit_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


@app.route('/field/visit/<int:visit_id>/complete', methods=['POST'])
def field_visit_complete(visit_id):
    from operations import complete_field_visit

    tech_id = getattr(g, 'field_tech_id', None)
    if tech_id:
        v = tenant_get_or_404(MaintenanceVisit, visit_id)
        if v.technician_id and v.technician_id != tech_id:
            abort(403)

    complete_field_visit(
        visit_id,
        works_done=request.form.get('works_done', ''),
        observations=request.form.get('observations', ''),
        status=request.form.get('status', 'مكتملة'),
    )
    return redirect(url_for('field_home'))


@app.route('/field/fault/<int:fault_id>/complete', methods=['POST'])
def field_fault_complete(fault_id):
    from operations import complete_field_fault
    from whatsapp_support import notify_customer_stage

    tech_id = getattr(g, 'field_tech_id', None)
    if tech_id:
        f = tenant_get_or_404(Fault, fault_id)
        if f.technician_id and f.technician_id != tech_id:
            abort(403)

    try:
        complete_field_fault(
            fault_id,
            tech_notes=request.form.get('tech_notes', ''),
            resolution=request.form.get('resolution', ''),
            status=request.form.get('status', 'تم الاصلاح'),
        )
        fault = tenant_query(Fault).filter_by(id=fault_id).first()
        status = (request.form.get('status') or 'تم الاصلاح').strip()
        if fault and status in ('تم الاصلاح', 'تم الإصلاح', 'مغلق', 'محلول'):
            notify_customer_stage(fault, 'resolved', next_code_fn=next_code, force=True)
            db.session.commit()
            flash(
                f'تم إغلاق {fault.code}. رسالة انتهاء العميل جاهزة للمكتب من شاشة الأعطال أو وارد واتساب.',
                'success',
            )
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('field_fault_report', fault_id=fault_id))
    return redirect(url_for('field_home'))


@app.route('/field/fault/<int:fault_id>/request-parts', methods=['POST'])
def field_fault_request_parts(fault_id):
    from operations import request_fault_parts

    tech_id = getattr(g, 'field_tech_id', None)
    if tech_id:
        f = tenant_get_or_404(Fault, fault_id)
        if f.technician_id and f.technician_id != tech_id:
            abort(403)

    sell = float(request.form.get('sell_price') or 0)
    request_fault_parts(
        fault_id,
        description=request.form.get('parts_description', ''),
        sell_price=sell,
    )
    return redirect(url_for('field_home'))


# =============================================
# الأعطال
# =============================================
# =============================================
# وارد واتساب — المرحلة 1 (المكتب ثم التوزيع)
# =============================================
@app.route('/support/whatsapp')
def whatsapp_inbox():
    from whatsapp_support import (
        ensure_whatsapp_settings,
        inbox_stats,
        parse_journey_for_template,
        pending_customer_sends,
        thread_query,
    )

    s = ensure_whatsapp_settings(get_app_settings())
    db.session.commit()
    items = (
        thread_query()
        .order_by(WhatsAppInbox.received_at.desc(), WhatsAppInbox.id.desc())
        .limit(200)
        .all()
    )
    journeys = {item.id: parse_journey_for_template(item) for item in items}
    customers = tenant_query(Customer).order_by(Customer.name).all()
    elevators = (
        tenant_query(Elevator)
        .order_by(Elevator.code)
        .all()
    )
    pending_wa = session.pop('pending_whatsapp', '')
    pending_customer_wa = pending_customer_sends(limit=20)
    return render_template(
        'whatsapp_inbox.html',
        items=items,
        journeys=journeys,
        pending_customer_wa=pending_customer_wa,
        customers=customers,
        elevators=elevators,
        customers_js=[
            {
                'id': c.id,
                'code': c.code or '',
                'name': c.name or '',
                'phone': c.phone or '',
                'phone2': c.phone2 or '',
                'city': c.city or '',
            }
            for c in customers
        ],
        elevators_js=[
            {
                'id': e.id,
                'code': e.code or '',
                'customer_id': e.customer_id,
                'building': e.building_name or '',
                'city': e.city or '',
            }
            for e in elevators
        ],
        stats=inbox_stats(),
        whatsapp_phone=s.whatsapp_phone or '0555076078',
        pending_whatsapp=pending_wa,
        flash_ok=session.pop('wa_flash_ok', ''),
        flash_err=session.pop('wa_flash_err', ''),
    )


@app.route('/support/whatsapp/intake', methods=['POST'])
def whatsapp_inbox_intake():
    from whatsapp_support import ensure_whatsapp_settings, intake_inbound

    ensure_whatsapp_settings(get_app_settings())
    try:
        item = intake_inbound(
            from_phone=request.form.get('from_phone', ''),
            from_name=request.form.get('from_name', ''),
            body=request.form.get('body', ''),
            next_code_fn=next_code,
        )
        db.session.commit()
        if item.customer_id and item.elevator_id:
            session['wa_flash_ok'] = f'تم استلام {item.code} وربطه تلقائياً بالعميل/المصعد — بانتظار إنشاء العطل والتوزيع.'
        elif item.customer_id:
            session['wa_flash_ok'] = f'تم استلام {item.code} وربطه بالعميل — اختر المصعد ثم أنشئ العطل.'
        else:
            session['wa_flash_ok'] = f'تم استلام {item.code} في صندوق المكتب — اربط العميل/المصعد.'
    except ValueError as exc:
        db.session.rollback()
        session['wa_flash_err'] = str(exc)
    except Exception as exc:
        db.session.rollback()
        session['wa_flash_err'] = f'تعذّر الاستلام: {exc}'
    return redirect(url_for('whatsapp_inbox'))


@app.route('/support/whatsapp/<int:item_id>/link', methods=['POST'])
def whatsapp_inbox_link(item_id):
    from whatsapp_support import link_inbox_item

    item = tenant_get_or_404(WhatsAppInbox, item_id)
    try:
        cid = request.form.get('customer_id') or None
        eid = request.form.get('elevator_id') or None
        link_inbox_item(
            item,
            customer_id=int(cid) if cid else None,
            elevator_id=int(eid) if eid else None,
        )
        db.session.commit()
        session['wa_flash_ok'] = f'تم ربط {item.code}'
    except ValueError as exc:
        db.session.rollback()
        session['wa_flash_err'] = str(exc)
    except Exception as exc:
        db.session.rollback()
        session['wa_flash_err'] = f'تعذّر الربط: {exc}'
    return redirect(url_for('whatsapp_inbox'))


    return redirect(url_for('whatsapp_inbox'))


@app.route('/support/whatsapp/<int:item_id>/ack-send', methods=['POST'])
def whatsapp_ack_send(item_id):
    """بعد فتح wa.me — إزالة من قائمة «جاهز للإرسال»."""
    from whatsapp_support import ack_pending_send

    data = request.get_json(silent=True) or {}
    stage = (data.get('stage') or request.form.get('stage') or '').strip() or None
    item = ack_pending_send(item_id, stage=stage)
    if not item:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'غير موجود'}), 404
        session['wa_flash_err'] = 'البلاغ غير موجود'
        return redirect(url_for('whatsapp_inbox'))
    db.session.commit()
    if request.is_json or request.headers.get('Accept', '').find('application/json') >= 0:
        return jsonify({'ok': True, 'thread_id': item.id, 'status': item.status})
    session['wa_flash_ok'] = f'تم تأكيد إرسال {item.code}'
    return redirect(url_for('whatsapp_inbox'))


@app.route('/support/whatsapp/<int:item_id>/create-fault', methods=['POST'])
def whatsapp_inbox_create_fault(item_id):
    from whatsapp_support import create_fault_from_inbox, notify_customer_stage

    item = tenant_get_or_404(WhatsAppInbox, item_id)
    try:
        fault = create_fault_from_inbox(item, next_code_fn=next_code, priority='عاجلة')
        cust = notify_customer_stage(fault, 'received', next_code_fn=next_code)
        db.session.commit()
        if cust.get('url'):
            session['pending_whatsapp'] = cust['url']
        session['wa_flash_ok'] = (
            f'تم إنشاء العطل {fault.code} على نفس كود الوارد {item.code}. '
            f'أكد الاستلام للعميل ثم وزّع الفني من شاشة الأعطال.'
        )
    except ValueError as exc:
        db.session.rollback()
        session['wa_flash_err'] = str(exc)
    except Exception as exc:
        db.session.rollback()
        session['wa_flash_err'] = f'تعذّر إنشاء العطل: {exc}'
    return redirect(url_for('whatsapp_inbox'))


@app.route('/api/webhooks/whatsapp', methods=['GET', 'POST'])
def whatsapp_webhook():
    """Webhook جاهز لـ Meta WhatsApp Cloud API (المرحلة التالية للربط الآلي)."""
    # Meta verification challenge
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        expected = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')
        if mode == 'subscribe' and expected and token == expected and challenge:
            return challenge, 200
        return jsonify({'ok': False, 'error': 'verify_failed'}), 403

    payload = request.get_json(silent=True) or {}
    # حالياً نسجّل الاستلام فقط — الربط الكامل بعد تفعيل WABA لكل مستأجر
    return jsonify({'ok': True, 'received': True, 'phase': 1, 'note': 'office_intake_ui_active'}), 200


@app.route('/faults')
def faults():
    from operations import fault_alerts, fault_stats
    from sqlalchemy.orm import joinedload

    faults_list = (
        tenant_query(Fault)
        .options(
            joinedload(Fault.elevator).joinedload(Elevator.customer),
            joinedload(Fault.technician),
            joinedload(Fault.linked_visit),
        )
        .order_by(Fault.reported_at.desc())
        .all()
    )
    elevators = tenant_query(Elevator).options(joinedload(Elevator.customer)).all()
    customers = tenant_query(Customer).order_by(Customer.name).all()
    inventory_items = tenant_query(InventoryItem).order_by(InventoryItem.name).all()
    technicians = tenant_query(Technician).filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول'])
    ).all()
    pending_wa = session.pop('pending_whatsapp', '')
    pending_wa_fault_id = session.pop('pending_whatsapp_fault_id', None)
    fault_techs = [t for t in technicians if (t.team or 'عام') in ('أعطال', 'عام', 'صيانة')] or list(technicians)
    return render_template(
        'faults.html',
        faults=faults_list,
        elevators=elevators,
        customers=customers,
        technicians=technicians,
        faults_js=_faults_js_list(faults_list),
        customers_js=[
            {'id': c.id, 'code': c.code, 'name': c.name,
             'city': c.city or '', 'district': c.district or '',
             'contact_person': c.contact_person or '', 'phone': c.phone or '',
             'building_photo_url': _static_upload_url(c.building_photo_path) or ''}
            for c in customers
        ],
        elevators_js=[
            {'id': e.id, 'code': e.code, 'customer_id': e.customer_id,
             'customer': e.customer.name if e.customer else '',
             'building_name': e.building_name or '',
             'city': e.city or '', 'district': e.district or ''}
            for e in elevators
        ],
        technicians_js=[{'id': t.id, 'name': t.name} for t in technicians],
        fault_technicians_js=[{'id': t.id, 'name': t.name} for t in fault_techs],
        inventory_items_js=[
            {'id': i.id, 'code': i.code, 'name': i.name,
             'unit': i.unit or 'قطعة', 'buy_price': i.buy_price or 0,
             'sell_price': i.sell_price or 0}
            for i in inventory_items
        ],
        next_fault_code=next_code(Fault, 'FA-', digits=5),
        fault_stats=fault_stats(),
        fault_alerts=fault_alerts(),
        fault_technicians=fault_techs,
        pending_whatsapp=pending_wa,
        pending_whatsapp_fault_id=pending_wa_fault_id,
        pending_customer_wa=[],
    )


def _wants_json_fault_response() -> bool:
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.headers.get('Accept') or '')
    )


def _fault_dispatch_feedback(dispatch_result: dict | None, tech_ids: list[int]) -> str | None:
    """رسالة تحذير عند الإرسال لبوابة الفني بدون رابط واتساب."""
    if not tech_ids or not dispatch_result:
        return None
    if dispatch_result.get('whatsapp_url'):
        return None
    if dispatch_result.get('error'):
        return f'تم الحفظ — {dispatch_result["error"]}'
    tech = tenant_query(Technician).filter_by(id=tech_ids[0]).first()
    name = tech.name if tech else 'الفني'
    if tech and not ((tech.phone or '').strip() or (tech.phone2 or '').strip()):
        return (
            f'تم إرسال العطل لبوابة الفني ({name}) — لا يوجد جوال مسجّل لرسالة واتساب. '
            'أضف الجوال من صفحة الفنيين.'
        )
    return f'تم إرسال العطل لبوابة الفني ({name}) — تعذّر تجهيز رابط واتساب (تحقق من جوال الفني).'


def _finish_fault_save(
    fault,
    *,
    dispatch_result: dict | None,
    flash_ok: str,
    flash_warn: str | None = None,
):
    if dispatch_result and dispatch_result.get('whatsapp_url'):
        session['pending_whatsapp'] = dispatch_result['whatsapp_url']
        session['pending_whatsapp_fault_id'] = fault.id
    if flash_warn:
        flash(flash_warn, 'warning')
    flash(flash_ok, 'success')
    if _wants_json_fault_response():
        return jsonify({
            'ok': True,
            'fault_id': fault.id,
            'code': fault.code,
            'whatsapp_url': (dispatch_result or {}).get('whatsapp_url', ''),
            'dispatched': bool(dispatch_result and not dispatch_result.get('error')),
            'warning': flash_warn or '',
        })
    return redirect(url_for('faults'))


def _parse_reported_at(raw: str | None):
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip().replace('Z', '')
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(text[:19] if 'T' in fmt else text[:10], fmt)
        except ValueError:
            continue
    return None


def _apply_fault_billing_from_form(fault, form, *, is_new: bool = False):
    from operations import (
        apply_fault_parts_billing,
        clear_fault_parts_billing,
        parse_fault_parts_lines,
    )

    billable = form.get('billable', 'no')
    if billable == 'yes':
        lines = parse_fault_parts_lines(form.get('parts_lines'))
        fault.needs_parts = True
        fault.billed = False
        if lines:
            apply_fault_parts_billing(
                fault, lines, technician_id=fault.technician_id,
            )
        elif not is_new:
            clear_fault_parts_billing(fault.id)
    else:
        fault.needs_parts = False
        fault.billed = False
        # عطل جديد بدون قطع: لا تلمس parts_billing/stock (كانت تسبب فشل الحفظ)
        if not is_new:
            clear_fault_parts_billing(fault.id)


@app.route('/faults/edit/<int:id>', methods=['POST'])
def fault_edit(id):
    from entity_links import link_fault_to_visit, lookup_visit
    from form_validation import fault_close_error
    from operations import dispatch_fault
    from technician_assignments import fault_technician_ids, parse_technician_ids, sync_fault_technicians
    from whatsapp_support import auto_stage_for_fault_status, notify_customer_stage

    close_err = fault_close_error(
        request.form.get('status'),
        request.form.get('resolution'),
    )
    if close_err:
        flash(close_err, 'error')
        return redirect(url_for('faults'))

    f = tenant_get_or_404(Fault, id)
    old_status = f.status
    had_tech = bool(f.technician_id)
    old_tech_ids = fault_technician_ids(f) or ([f.technician_id] if f.technician_id else [])
    tech_ids = parse_technician_ids(request.form)
    f.elevator_id   = request.form['elevator_id']
    f.technician_id = tech_ids[0] if tech_ids else None
    f.fault_type    = request.form.get('fault_type','')
    f.description   = request.form.get('description','')
    f.client_report = request.form.get('client_report') or f.description or ''
    f.reporter_name = request.form.get('reporter_name', f.reporter_name or '')
    f.reporter_phone = request.form.get('reporter_phone', f.reporter_phone or '')
    f.priority      = request.form.get('priority','عادية')
    f.status        = request.form.get('status','مفتوح')
    f.resolution    = request.form.get('resolution','')
    f.response_time = request.form.get('response_time','')
    reported = _parse_reported_at(request.form.get('reported_at'))
    if reported:
        f.reported_at = reported
    f.notes = request.form.get('notes', '')
    visit_code = request.form.get('visit_code', '').strip()
    if visit_code:
        visit = lookup_visit(visit_code)
        if visit:
            link_fault_to_visit(f, visit)
    try:
        _apply_fault_billing_from_form(f, request.form)
        sync_fault_technicians(f, tech_ids)
        stage = auto_stage_for_fault_status(
            old_status,
            f.status,
            had_tech=had_tech,
            has_tech=bool(f.technician_id),
        )
        cust_wa = None
        if stage:
            cust_wa = notify_customer_stage(f, stage, next_code_fn=next_code)
        db.session.commit()
        dispatch_result = None
        if tech_ids and (set(tech_ids) != set(old_tech_ids) or not f.dispatched_at):
            try:
                dispatch_result = dispatch_fault(f.id, request.url_root)
            except Exception:
                app.logger.exception('fault dispatch after edit failed')
                flash('تم حفظ العطل لكن تعذّر إرساله للفني.', 'error')
                return redirect(url_for('faults'))
        warn = _fault_dispatch_feedback(dispatch_result, tech_ids)
        # رسائل العميل تظهر بجانب صف العطل (journey) — لا تُكدَّس فوق الجدول
        return _finish_fault_save(
            f,
            dispatch_result=dispatch_result,
            flash_ok=f'تم تحديث العطل {f.code}',
            flash_warn=warn,
        )
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('faults'))

@app.route('/faults/add', methods=['POST'])
def fault_add():
    from entity_links import link_fault_to_visit, lookup_visit
    from operations import dispatch_fault
    from technician_assignments import parse_technician_ids, sync_fault_technicians

    tech_ids = parse_technician_ids(request.form)
    if not tech_ids:
        flash('اختر فني واحد على الأقل', 'error')
        return redirect(url_for('faults'))
    if not (request.form.get('elevator_id') or '').strip():
        flash('اختر المصعد', 'error')
        return redirect(url_for('faults'))

    client_report = request.form.get('client_report') or request.form.get('description', '')
    reported = _parse_reported_at(request.form.get('reported_at'))
    tech_ids = parse_technician_ids(request.form)
    try:
        f = Fault(
            code          = next_code(Fault, 'FA-', digits=5),
            elevator_id   = int(request.form['elevator_id']),
            technician_id = tech_ids[0] if tech_ids else None,
            fault_type    = request.form.get('fault_type',''),
            description   = client_report,
            client_report = client_report,
            reporter_name = request.form.get('reporter_name', ''),
            reporter_phone= request.form.get('reporter_phone', ''),
            priority      = request.form.get('priority','عادية'),
            status        = request.form.get('status','مفتوح'),
            notes         = request.form.get('notes',''),
            reported_at   = reported or datetime.utcnow(),
        )
        assign_organization(f)
        db.session.add(f)
        db.session.flush()
        sync_fault_technicians(f, tech_ids)

        visit_code = request.form.get('visit_code', '').strip()
        if visit_code:
            visit = lookup_visit(visit_code)
            if visit:
                link_fault_to_visit(f, visit)

        _apply_fault_billing_from_form(f, request.form, is_new=True)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('faults'))
    except Exception as e:
        db.session.rollback()
        app.logger.exception('fault_add failed')
        flash(f'تعذّر حفظ العطل: {e}', 'error')
        return redirect(url_for('faults'))

    dispatch_result = None
    if f.technician_id:
        try:
            dispatch_result = dispatch_fault(f.id, request.url_root)
        except Exception:
            app.logger.exception('fault dispatch after add failed')
            flash('تم حفظ العطل لكن تعذّر إرساله للفني.', 'error')
            return redirect(url_for('faults'))
    warn = _fault_dispatch_feedback(dispatch_result, tech_ids)
    return _finish_fault_save(
        f,
        dispatch_result=dispatch_result,
        flash_ok=f'تم تسجيل العطل {f.code}',
        flash_warn=warn,
    )

@app.route('/faults/delete/<int:id>', methods=['POST'])
def fault_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    f = tenant_get_or_404(Fault, id)
    tenant_query(FaultTechnician).filter_by(fault_id=id).delete(synchronize_session=False)
    tenant_query(MaintenanceVisit).filter_by(fault_id=id).update(
        {MaintenanceVisit.fault_id: None}, synchronize_session=False
    )
    tenant_query(PartsBilling).filter_by(fault_id=id).update(
        {PartsBilling.fault_id: None}, synchronize_session=False
    )
    db.session.delete(f)
    db.session.commit()
    return redirect(url_for('faults'))

# =============================================
# الإيرادات
# =============================================
@app.route('/revenues')
def revenues():
    from sqlalchemy.orm import joinedload
    from customer_billing import tenant_outstanding_collectible

    _ensure_tenant_chart()
    revs = (
        tenant_query(Revenue)
        .options(joinedload(Revenue.customer), joinedload(Revenue.contract))
        .order_by(Revenue.revenue_date.desc())
        .all()
    )
    customers = tenant_query(Customer).order_by(Customer.name).all()
    outstanding = tenant_outstanding_collectible()
    return render_template(
        'revenues.html',
        revenues=revs,
        customers=customers,
        revenues_js=[revenue_to_js_dict(r) for r in revs],
        customers_js=[{'id': c.id, 'name': c.name, 'code': c.code} for c in customers],
        outstanding_total=outstanding.get('total') or 0,
        outstanding_count=outstanding.get('items_count') or 0,
        outstanding_contracts=outstanding.get('contracts_count') or 0,
    )

def _revenue_from_form(form, existing: Revenue | None = None):
    from customer_billing import apply_payment_to_source, split_vat_amounts

    amount, tax, total = split_vat_amounts(
        amount_ex_vat=form.get('amount'),
        total_incl_vat=form.get('total'),
        tax_pct=form.get('tax_pct', 15),
    )
    source_type = (form.get('source_type') or '').strip()
    source_id = (form.get('source_id') or '').strip()
    notes = form.get('notes', '')
    contract_id = form.get('contract_id') or None
    invoice_id = None
    parts_billing_id = None
    revenue_type = form.get('revenue_type', '')
    customer_id = form.get('customer_id') or None

    if source_type and source_id and not existing:
        link = apply_payment_to_source(source_type, int(source_id), total)
        customer_id = link['customer_id']
        contract_id = link['contract_id']
        invoice_id = link['invoice_id']
        parts_billing_id = link['parts_billing_id']
        revenue_type = link['revenue_type']
        ref_note = link.get('reference_note') or ''
        if ref_note and ref_note not in (notes or ''):
            notes = (ref_note + (' — ' + notes if notes else '')).strip()

    if not contract_id and customer_id:
        from customer_billing import resolve_contract_id
        contract_id = resolve_contract_id(
            int(customer_id),
            form.get('reference', ''),
            notes,
            '',
            revenue_type or form.get('revenue_type', ''),
        )

    data = {
        'customer_id': int(customer_id) if customer_id else None,
        'contract_id': int(contract_id) if contract_id else None,
        'invoice_id': invoice_id,
        'parts_billing_id': parts_billing_id,
        'revenue_date': datetime.strptime(form['revenue_date'], '%Y-%m-%d').date(),
        'revenue_type': revenue_type,
        'payment_method': form.get('payment_method', ''),
        'amount': amount,
        'tax_amount': tax,
        'total': total,
        'status': form.get('status', 'محصّل'),
        'reference': form.get('reference', ''),
        'notes': notes,
    }
    try:
        from chart_of_accounts import resolve_revenue_account_id
        _ensure_tenant_chart()
        data['account_id'] = resolve_revenue_account_id(revenue_type, notes)
    except Exception:
        pass
    if existing:
        for key, val in data.items():
            setattr(existing, key, val)
        return existing
    r = Revenue(code=next_code(Revenue, 'REV-', digits=3), **data)
    assign_organization(r)
    stamp_created_by(r)
    db.session.add(r)
    return r


@app.route('/revenues/edit/<int:id>', methods=['POST'])
def revenue_edit(id):
    from customer_billing import COLLECTED_REVENUE_STATUSES, create_receipt_voucher_for_revenue

    r = tenant_get_or_404(Revenue, id)
    old_contract_id = r.contract_id
    try:
        _revenue_from_form(request.form, existing=r)
        _save_fin_proof(r, request.files.get('proof_file'), kind='revenues', required=False)
    except (ValueError, KeyError) as exc:
        db.session.rollback()
        flash(str(exc) or 'تعذّر تحديث الإيراد', 'error')
        return redirect(url_for('revenues'))
    receipt = None
    if (r.status or '') in COLLECTED_REVENUE_STATUSES:
        receipt = create_receipt_voucher_for_revenue(r)
    sync_contract_invoice_status(r.contract_id)
    if old_contract_id and old_contract_id != r.contract_id:
        sync_contract_invoice_status(old_contract_id)
    try:
        from accounting_journals import post_revenue_journal
        post_revenue_journal(r)
    except Exception:
        app.logger.exception('post_revenue_journal on edit failed')
    db.session.commit()
    if receipt:
        flash(f'تم إنشاء سند قبض {receipt.code} تلقائياً', 'success')
    return redirect(url_for('revenues'))

@app.route('/revenues/add', methods=['POST'])
def revenue_add():
    from customer_billing import COLLECTED_REVENUE_STATUSES, create_receipt_voucher_for_revenue

    try:
        r = _revenue_from_form(request.form)
        db.session.flush()
        _save_fin_proof(r, request.files.get('proof_file'), kind='revenues', required=False)
    except (ValueError, KeyError) as exc:
        db.session.rollback()
        flash(str(exc) or 'تعذّر حفظ الإيراد', 'error')
        return redirect(url_for('revenues'))
    receipt = None
    if (r.status or '') in COLLECTED_REVENUE_STATUSES:
        receipt = create_receipt_voucher_for_revenue(r)
    sync_contract_invoice_status(r.contract_id)
    try:
        from accounting_journals import post_revenue_journal
        post_revenue_journal(r)
    except Exception:
        app.logger.exception('post_revenue_journal on add failed')
    db.session.commit()
    if receipt:
        flash(f'تم إنشاء سند قبض {receipt.code} تلقائياً', 'success')
    return redirect(url_for('revenues'))

@app.route('/revenues/delete/<int:id>', methods=['POST'])
def revenue_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    r = tenant_get_or_404(Revenue, id)
    contract_id = r.contract_id
    try:
        from accounting_journals import void_revenue_journal
        void_revenue_journal(r.id)
    except Exception:
        app.logger.exception('void_revenue_journal failed')
    # سند القبض يشير للإيراد (FK) — احذفه أولاً وإلا يفشل الحذف
    for inv in tenant_query(Invoice).filter_by(revenue_id=r.id).all():
        db.session.delete(inv)
    _remove_fin_proof(r)
    db.session.delete(r)
    sync_contract_invoice_status(contract_id)
    db.session.commit()
    return redirect(url_for('revenues'))


@app.route('/revenues/<int:id>/remove-proof', methods=['POST'])
def revenue_remove_proof(id):
    """حذف إثبات دفع الإيراد — مدير النظام فقط."""
    err = enforce_admin_attachment_delete(json_response=True)
    if err:
        return err
    r = tenant_get_or_404(Revenue, id)
    if not r.proof_path:
        return jsonify({'ok': True, 'removed': False, 'message': 'لا يوجد مرفق'})
    _remove_fin_proof(r)
    db.session.commit()
    return jsonify({'ok': True, 'removed': True, 'id': r.id})


# =============================================
# شجرة الحسابات (مرحلة 1)
# =============================================
def _ensure_tenant_chart():
    from chart_of_accounts import ensure_chart_schema

    try:
        ensure_chart_schema()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('ensure_chart_schema: %s', exc)


@app.route('/accounts')
def accounts():
    from chart_of_accounts import ACCOUNT_TYPE_LABELS, accounts_tree_rows

    _ensure_tenant_chart()
    rows = accounts_tree_rows()
    counts = {k: 0 for k in ACCOUNT_TYPE_LABELS}
    for r in rows:
        counts[r['account_type']] = counts.get(r['account_type'], 0) + 1
    return render_template('accounts.html', accounts=rows, counts=counts)


@app.route('/accounts/seed', methods=['POST'])
def accounts_seed():
    from chart_of_accounts import ensure_chart_for_org
    from tenant_scope import effective_organization_id

    _ensure_tenant_chart()
    oid = getattr(g, 'organization_id', None) or effective_organization_id()
    added = ensure_chart_for_org(oid) if oid else 0
    flash(f'تم تحديث شجرة الحسابات ({added} حساب جديد)' if added else 'الشجرة محدّثة مسبقاً', 'success')
    return redirect(url_for('accounts'))


@app.route('/accounts/seed-roots', methods=['POST'])
def accounts_seed_roots():
    from chart_of_accounts import seed_root_groups_for_org
    from tenant_scope import effective_organization_id

    _ensure_tenant_chart()
    oid = getattr(g, 'organization_id', None) or effective_organization_id()
    added = seed_root_groups_for_org(oid) if oid else 0
    flash(
        f'تم إنشاء المجموعات الأساسية ({added} مجموعة). أكمل الشجرة بحساباتك.'
        if added else
        'المجموعات الأساسية موجودة مسبقاً',
        'success',
    )
    return redirect(url_for('accounts'))


@app.route('/accounts/backfill', methods=['POST'])
def accounts_backfill():
    from chart_of_accounts import backfill_missing_account_links

    _ensure_tenant_chart()
    try:
        stats = backfill_missing_account_links()
        flash(
            f"تم الربط: {stats.get('revenues', 0)} إيراد · {stats.get('expenses', 0)} مصروف",
            'success',
        )
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('accounts_backfill failed')
        flash(f'تعذّر الربط: {exc}', 'danger')
    return redirect(url_for('accounts'))


@app.route('/accounts/add', methods=['POST'])
def accounts_add():
    from chart_of_accounts import create_custom_account

    _ensure_tenant_chart()
    try:
        parent_raw = (request.form.get('parent_id') or '').strip()
        parent_id = int(parent_raw) if parent_raw else None
        acc = create_custom_account(
            code=request.form.get('code', ''),
            name=request.form.get('name', ''),
            account_type=request.form.get('account_type', ''),
            parent_id=parent_id,
            is_postable=request.form.get('is_postable') == '1',
            name_en=request.form.get('name_en', ''),
            notes=request.form.get('notes', ''),
        )
        db.session.commit()
        flash(f'تم إنشاء الحساب {acc.code} — {acc.name}', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('accounts_add failed')
        flash(f'تعذّر إنشاء الحساب: {exc}', 'danger')
    return redirect(url_for('accounts'))


@app.route('/accounts/<int:id>/edit', methods=['POST'])
def accounts_edit(id):
    from chart_of_accounts import update_account

    _ensure_tenant_chart()
    try:
        parent_raw = (request.form.get('parent_id') or '').strip()
        parent_id = int(parent_raw) if parent_raw else None
        acc = update_account(
            id,
            code=request.form.get('code', ''),
            name=request.form.get('name', ''),
            account_type=request.form.get('account_type', ''),
            parent_id=parent_id,
            is_postable=request.form.get('is_postable') == '1',
            is_active=request.form.get('is_active') == '1',
            name_en=request.form.get('name_en', ''),
            notes=request.form.get('notes', ''),
        )
        db.session.commit()
        flash(f'تم تعديل الحساب {acc.code} — {acc.name}', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('accounts_edit failed')
        flash(f'تعذّر تعديل الحساب: {exc}', 'danger')
    return redirect(url_for('accounts'))


@app.route('/accounts/<int:id>/delete', methods=['POST'])
def accounts_delete(id):
    from chart_of_accounts import delete_account

    _ensure_tenant_chart()
    try:
        code, name = delete_account(id)
        db.session.commit()
        flash(f'تم حذف الحساب {code} — {name}', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('accounts_delete failed')
        flash(f'تعذّر حذف الحساب: {exc}', 'danger')
    return redirect(url_for('accounts'))


@app.route('/accounts/wipe', methods=['POST'])
def accounts_wipe():
    from chart_of_accounts import wipe_chart_for_org
    from tenant_scope import effective_organization_id

    _ensure_tenant_chart()
    oid = getattr(g, 'organization_id', None) or effective_organization_id()
    try:
        stats = wipe_chart_for_org(oid) if oid else {'accounts': 0, 'journals': 0}
        flash(
            f"تم مسح الشجرة: {stats.get('accounts', 0)} حساب"
            f" و{stats.get('journals', 0)} قيد. يمكنك إنشاء شجرتك الآن.",
            'success',
        )
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('accounts_wipe failed')
        flash(f'تعذّر مسح الشجرة: {exc}', 'danger')
    return redirect(url_for('accounts'))


# =============================================
# القيود / دفتر الأستاذ / التقارير المحاسبية (مرحلة 2–3)
# =============================================
def _parse_iso_date(raw, default=None):
    raw = (raw or '').strip()
    if not raw:
        return default
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return default


@app.route('/journals')
def journals():
    from accounting_journals import ensure_journal_schema
    from sqlalchemy.orm import joinedload

    _ensure_tenant_chart()
    ensure_journal_schema()
    rows = (
        tenant_query(JournalEntry)
        .options(joinedload(JournalEntry.lines))
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
        .limit(500)
        .all()
    )
    journals_view = []
    posted_count = void_count = 0
    for j in rows:
        td = sum(float(l.debit or 0) for l in j.lines)
        tc = sum(float(l.credit or 0) for l in j.lines)
        if j.status == 'posted':
            posted_count += 1
        else:
            void_count += 1
        journals_view.append({
            'id': j.id,
            'code': j.code,
            'entry_date': j.entry_date,
            'memo': j.memo,
            'source_type': j.source_type,
            'source_id': j.source_id,
            'status': j.status,
            'total_debit': round(td, 2),
            'total_credit': round(tc, 2),
        })
    return render_template(
        'journals.html',
        journals=journals_view,
        posted_count=posted_count,
        void_count=void_count,
    )


@app.route('/journals/backfill', methods=['POST'])
def journals_backfill():
    from accounting_journals import backfill_journals

    _ensure_tenant_chart()
    try:
        stats = backfill_journals()
        flash(
            f"تم الترحيل: {stats.get('revenues', 0)} إيراد · {stats.get('expenses', 0)} مصروف"
            + (f" · تخطي {stats.get('skipped', 0)}" if stats.get('skipped') else ''),
            'success',
        )
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('journals_backfill failed')
        flash(f'تعذّر الترحيل: {exc}', 'danger')
    return redirect(url_for('journals'))


def _postable_accounts():
    return (
        tenant_query(Account)
        .filter_by(is_postable=True, is_active=True)
        .order_by(Account.code.asc())
        .all()
    )


def _parse_manual_journal_lines(accounts):
    allowed = {a.id for a in accounts}

    def _fnum(values, idx):
        try:
            return float((values[idx] if idx < len(values) else '') or 0)
        except (TypeError, ValueError):
            return 0.0

    account_ids = request.form.getlist('account_id')
    debits = request.form.getlist('debit')
    credits = request.form.getlist('credit')
    memos = request.form.getlist('line_memo')
    n = max(len(account_ids), len(debits), len(credits), len(memos))
    lines = []
    for i in range(n):
        raw = account_ids[i] if i < len(account_ids) else ''
        try:
            acc_id = int(raw) if raw else 0
        except ValueError:
            acc_id = 0
        if not acc_id or acc_id not in allowed:
            continue
        memo = (memos[i] if i < len(memos) else '') or None
        if memo:
            memo = memo.strip()[:300] or None
        lines.append((acc_id, _fnum(debits, i), _fnum(credits, i), memo))
    return lines


@app.route('/journals/new', methods=['GET', 'POST'])
def journal_new():
    from accounting_journals import create_manual_journal, ensure_journal_schema

    _ensure_tenant_chart()
    ensure_journal_schema()
    accounts = _postable_accounts()
    if request.method == 'POST':
        kind = (request.form.get('kind') or 'manual').strip()
        if kind not in ('manual', 'opening'):
            kind = 'manual'
        entry_date = _parse_iso_date(request.form.get('entry_date'), default=date.today())
        memo = (request.form.get('memo') or '').strip()[:400]
        lines = _parse_manual_journal_lines(accounts)
        je = create_manual_journal(
            entry_date=entry_date,
            memo=memo,
            lines=lines,
            kind=kind,
        )
        if not je:
            flash('القيد غير متوازن أو ناقص — أدخل سطرين على الأقل بتساوي المدين والدائن.', 'danger')
            return render_template(
                'journal_form.html',
                accounts=accounts,
                form=request.form,
            )
        db.session.commit()
        flash(f'تم ترحيل القيد {je.code}', 'success')
        return redirect(url_for('journal_detail', id=je.id))
    return render_template('journal_form.html', accounts=accounts, form=None)


@app.route('/journals/<int:id>/void', methods=['POST'])
def journal_void(id):
    from accounting_journals import ensure_journal_schema, void_manual_journal

    _ensure_tenant_chart()
    ensure_journal_schema()
    ok = void_manual_journal(id)
    if ok:
        db.session.commit()
        flash('تم إلغاء القيد', 'success')
    else:
        flash('لا يمكن إلغاء هذا القيد — يُلغى القيد اليدوي/الافتتاحي المرحّل فقط.', 'danger')
    return redirect(url_for('journal_detail', id=id))


@app.route('/journals/<int:id>')
def journal_detail(id):
    from accounting_journals import ensure_journal_schema
    from sqlalchemy.orm import joinedload

    _ensure_tenant_chart()
    ensure_journal_schema()
    j = (
        tenant_query(JournalEntry)
        .options(joinedload(JournalEntry.lines).joinedload(JournalLine.account))
        .filter_by(id=id)
        .first_or_404()
    )
    lines = []
    total_debit = total_credit = 0.0
    for line in j.lines:
        d = float(line.debit or 0)
        c = float(line.credit or 0)
        total_debit += d
        total_credit += c
        acc = line.account
        lines.append({
            'account_code': acc.code if acc else '—',
            'account_name': acc.name if acc else '—',
            'line_memo': line.line_memo,
            'debit': round(d, 2),
            'credit': round(c, 2),
        })
    return render_template(
        'journal_detail.html',
        journal=j,
        lines=lines,
        total_debit=round(total_debit, 2),
        total_credit=round(total_credit, 2),
        can_void=(j.status == 'posted' and (j.source_type or '') in ('manual', 'opening')),
    )


@app.route('/ledger')
def ledger():
    from accounting_journals import ensure_journal_schema, ledger_lines

    _ensure_tenant_chart()
    ensure_journal_schema()
    accounts = (
        tenant_query(Account)
        .filter_by(is_postable=True, is_active=True)
        .order_by(Account.code.asc())
        .all()
    )
    account_id = request.args.get('account_id', type=int)
    date_from = _parse_iso_date(request.args.get('from'))
    date_to = _parse_iso_date(request.args.get('to'))
    account = None
    lines = []
    running = 0.0
    if account_id:
        account, lines, running = ledger_lines(account_id, date_from, date_to)
    return render_template(
        'ledger.html',
        accounts=accounts,
        account=account,
        lines=lines,
        running=running,
        date_from=date_from.isoformat() if date_from else '',
        date_to=date_to.isoformat() if date_to else '',
    )


@app.route('/trial-balance')
def trial_balance():
    from accounting_journals import ensure_journal_schema, trial_balance_rows

    _ensure_tenant_chart()
    ensure_journal_schema()
    date_to = _parse_iso_date(request.args.get('to'))
    rows, total_debit, total_credit = trial_balance_rows(date_to=date_to)
    return render_template(
        'trial_balance.html',
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        date_to=date_to.isoformat() if date_to else '',
    )


@app.route('/pnl')
def pnl():
    from accounting_journals import ensure_journal_schema, income_statement

    _ensure_tenant_chart()
    ensure_journal_schema()
    date_from = _parse_iso_date(request.args.get('from'))
    date_to = _parse_iso_date(request.args.get('to'))
    report = income_statement(date_from=date_from, date_to=date_to)
    return render_template(
        'pnl.html',
        report=report,
        date_from=date_from.isoformat() if date_from else '',
        date_to=date_to.isoformat() if date_to else '',
    )


@app.route('/balance-sheet')
def balance_sheet():
    from accounting_journals import balance_sheet as build_bs, ensure_journal_schema

    _ensure_tenant_chart()
    ensure_journal_schema()
    date_to = _parse_iso_date(request.args.get('to'))
    report = build_bs(as_of=date_to)
    return render_template(
        'balance_sheet.html',
        report=report,
        date_to=date_to.isoformat() if date_to else '',
    )


# =============================================
# المصروفات
# =============================================
@app.route('/expenses')
def expenses():
    _ensure_tenant_chart()
    exps = tenant_query(Expense).order_by(Expense.expense_date.desc()).all()
    return render_template(
        'expenses.html',
        expenses=exps,
        expenses_js=[expense_to_js_dict(e) for e in exps],
    )
@app.route('/expenses/edit/<int:id>', methods=['POST'])
def expense_edit(id):
    e = tenant_get_or_404(Expense, id)
    try:
        e.expense_date   = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
        e.expense_type   = request.form.get('expense_type','')
        e.description    = request.form.get('description','')
        e.responsible    = request.form.get('responsible','')
        e.payment_method = request.form.get('payment_method','')
        e.amount         = float(request.form.get('amount', 0))
        e.reference      = request.form.get('reference','')
        e.notes          = request.form.get('notes','')
        try:
            from chart_of_accounts import resolve_expense_account_id
            _ensure_tenant_chart()
            e.account_id = resolve_expense_account_id(e.expense_type)
        except Exception:
            pass
        _save_fin_proof(e, request.files.get('proof_file'), kind='expenses', required=False)
        try:
            from accounting_journals import post_expense_journal
            post_expense_journal(e)
        except Exception:
            app.logger.exception('post_expense_journal on edit failed')
        db.session.commit()
    except (ValueError, KeyError) as exc:
        db.session.rollback()
        flash(str(exc) or 'تعذّر تحديث المصروف', 'error')
        return redirect(url_for('expenses'))
    return redirect(url_for('expenses'))

@app.route('/expenses/add', methods=['POST'])
def expense_add():
    try:
        e = Expense(
            code           = next_code(Expense, 'EXP-', digits=3),
            expense_date   = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date(),
            expense_type   = request.form.get('expense_type',''),
            description    = request.form.get('description',''),
            responsible    = request.form.get('responsible',''),
            payment_method = request.form.get('payment_method',''),
            amount         = float(request.form.get('amount', 0)),
            reference      = request.form.get('reference',''),
            notes          = request.form.get('notes',''),
        )
        try:
            from chart_of_accounts import resolve_expense_account_id
            _ensure_tenant_chart()
            e.account_id = resolve_expense_account_id(e.expense_type)
        except Exception:
            pass
        assign_organization(e)
        stamp_created_by(e)
        db.session.add(e)
        db.session.flush()
        _save_fin_proof(e, request.files.get('proof_file'), kind='expenses', required=False)
        try:
            from accounting_journals import post_expense_journal
            post_expense_journal(e)
        except Exception:
            app.logger.exception('post_expense_journal on add failed')
        db.session.commit()
    except (ValueError, KeyError) as exc:
        db.session.rollback()
        flash(str(exc) or 'تعذّر حفظ المصروف', 'error')
        return redirect(url_for('expenses'))
    return redirect(url_for('expenses'))

@app.route('/expenses/delete/<int:id>', methods=['POST'])
def expense_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    e = tenant_get_or_404(Expense, id)
    try:
        from accounting_journals import void_expense_journal
        void_expense_journal(e.id)
    except Exception:
        app.logger.exception('void_expense_journal failed')
    _remove_fin_proof(e)
    db.session.delete(e)
    db.session.commit()
    return redirect(url_for('expenses'))


@app.route('/expenses/<int:id>/remove-proof', methods=['POST'])
def expense_remove_proof(id):
    """حذف إثبات صرف المصروف — مدير النظام فقط."""
    err = enforce_admin_attachment_delete(json_response=True)
    if err:
        return err
    e = tenant_get_or_404(Expense, id)
    if not e.proof_path:
        return jsonify({'ok': True, 'removed': False, 'message': 'لا يوجد مرفق'})
    _remove_fin_proof(e)
    db.session.commit()
    return jsonify({'ok': True, 'removed': True, 'id': e.id})


# =============================================
# الفواتير
# =============================================
@app.route('/invoices')
def invoices():
    from sqlalchemy.orm import joinedload

    invs = (
        tenant_query(Invoice)
        .options(joinedload(Invoice.customer), joinedload(Invoice.contract))
        .order_by(Invoice.invoice_date.desc())
        .all()
    )
    customers = tenant_query(Customer).order_by(Customer.name).all()
    return render_template(
        'invoices.html',
        invoices=invs,
        customers=customers,
        invoices_js=[invoice_to_js_dict(i) for i in invs],
        customers_js=[{'id': c.id, 'name': c.name, 'code': c.code} for c in customers],
    )

@app.route('/invoices/edit/<int:id>', methods=['POST'])
def invoice_edit(id):
    from form_validation import invoice_amount_error
    from customer_billing import split_vat_amounts

    i = tenant_get_or_404(Invoice, id)
    amount_raw = request.form.get('amount', 0)
    total_raw = request.form.get('total')
    amount, tax, total = split_vat_amounts(
        amount_ex_vat=amount_raw,
        total_incl_vat=total_raw if total_raw not in (None, '') else None,
        tax_pct=15,
    )
    amt_err = invoice_amount_error(amount)
    if amt_err:
        flash(amt_err, 'error')
        return redirect(url_for('invoices'))
    i.invoice_type   = request.form.get('invoice_type', 'فاتورة ضريبية')
    i.customer_id    = request.form.get('customer_id') or None
    i.invoice_date   = datetime.strptime(request.form['invoice_date'], '%Y-%m-%d').date()
    i.due_date       = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date() if request.form.get('due_date') else None
    i.description    = request.form.get('description','')
    i.amount         = amount
    i.tax_amount     = tax
    i.total          = total
    i.payment_method = request.form.get('payment_method','')
    status = request.form.get('status', 'غير مدفوعة')
    i.status = status
    from customer_billing import PAID_INVOICE_STATUSES, _round_money
    if status in PAID_INVOICE_STATUSES:
        i.paid_amount = _round_money(i.total or 0)
    i.notes = request.form.get('notes', '')
    sync_contract_invoice_status(i.contract_id)
    db.session.commit()
    return redirect(url_for('invoices'))

@app.route('/invoices/add', methods=['POST'])
def invoice_add():
    from form_validation import invoice_amount_error
    from customer_billing import (
        contract_paid_amount,
        split_vat_amounts,
        validate_tax_invoice_full_amount,
    )

    amount_raw = request.form.get('amount', 0)
    total_raw = request.form.get('total')
    amount, tax, total = split_vat_amounts(
        amount_ex_vat=amount_raw,
        total_incl_vat=total_raw if total_raw not in (None, '') else None,
        tax_pct=15,
    )
    invoice_type = request.form.get('invoice_type', 'فاتورة ضريبية')
    amt_err = invoice_amount_error(amount)
    if amt_err:
        flash(amt_err, 'error')
        return redirect(url_for('invoices'))
    source_type = (request.form.get('source_type') or '').strip()
    source_id = (request.form.get('source_id') or '').strip()
    source_id_int = int(source_id) if source_id.isdigit() else None

    tax_err = validate_tax_invoice_full_amount(
        invoice_type, total, source_type or None, source_id_int,
    )
    if tax_err:
        flash(tax_err, 'error')
        return redirect(url_for('invoices'))
    from zatca_tenant import tax_invoice_zatca_error
    zatca_err = tax_invoice_zatca_error(invoice_type)
    if zatca_err:
        flash(zatca_err, 'error')
        return redirect(url_for('invoices'))
    customer_id = request.form.get('customer_id') or None
    contract_id = request.form.get('contract_id') or None
    parts_billing_id = None
    notes = request.form.get('notes', '')
    description = (request.form.get('description') or '').strip()

    if source_type == 'parts_billing' and source_id:
        pb = tenant_get_or_404(PartsBilling, int(source_id))
        from customer_billing import _invoice_exists_for_parts
        if _invoice_exists_for_parts(pb.id):
            flash('يوجد فاتورة لهذه العملية مسبقاً', 'error')
            return redirect(url_for('invoices'))
        customer_id = pb.customer_id
        contract_id = pb.contract_id
        parts_billing_id = pb.id
        ref = f'فاتورة عملية {pb.code}'
        if ref not in (notes or ''):
            notes = (ref + (' — ' + notes if notes else '')).strip()
    elif source_type == 'contract' and source_id:
        c = tenant_get_or_404(Contract, int(source_id))
        from customer_billing import _invoice_exists_for_contract, contract_paid_amount
        if _invoice_exists_for_contract(c.id):
            flash('يوجد فاتورة لهذا العقد مسبقاً', 'error')
            return redirect(url_for('invoices'))
        customer_id = c.customer_id
        contract_id = c.id
        ref = f'فاتورة عقد {c.code}'
        if ref not in (notes or ''):
            notes = (ref + (' — ' + notes if notes else '')).strip()

    if not contract_id and customer_id:
        from customer_billing import resolve_contract_id
        contract_id = resolve_contract_id(
            int(customer_id),
            '',
            notes,
            description,
        )

    due_raw = request.form.get('due_date', '').strip()
    invoice_status = request.form.get('status', 'غير مدفوعة')
    invoice_paid = 0.0
    if source_type == 'parts_billing' and source_id:
        pb = tenant_query(PartsBilling).filter_by(id=int(source_id)).first()
        if pb:
            from customer_billing import _round_money
            paid_on_parts = _round_money(getattr(pb, 'paid_amount', 0) or 0)
            invoice_paid = min(paid_on_parts, total)
            if invoice_paid >= total - 0.01:
                invoice_status = 'مدفوعة'
            elif invoice_paid > 0.01:
                invoice_status = 'مدفوع جزئياً'
            else:
                invoice_status = 'غير مدفوعة'
    elif source_type == 'contract' and source_id:
        c = tenant_query(Contract).filter_by(id=int(source_id)).first()
        if c:
            from customer_billing import _round_money
            paid_on_contract = contract_paid_amount(c.id)
            invoice_paid = min(_round_money(paid_on_contract), total)
            if invoice_paid >= total - 0.01:
                invoice_status = 'مدفوعة'
            elif invoice_paid > 0.01:
                invoice_status = 'مدفوع جزئياً'
            else:
                invoice_status = 'غير مدفوعة'

    i = Invoice(
        code=next_code(Invoice, 'INV-', digits=4),
        invoice_type=invoice_type,
        customer_id=int(customer_id) if customer_id else None,
        contract_id=int(contract_id) if contract_id else None,
        parts_billing_id=parts_billing_id,
        invoice_date=datetime.strptime(request.form['invoice_date'], '%Y-%m-%d').date(),
        due_date=datetime.strptime(due_raw, '%Y-%m-%d').date() if due_raw else None,
        description=description,
        amount=amount,
        tax_amount=tax,
        total=total,
        paid_amount=invoice_paid,
        payment_method=request.form.get('payment_method', ''),
        status=invoice_status,
        notes=notes,
    )
    assign_organization(i)
    db.session.add(i)
    db.session.flush()
    if source_type == 'contract' and source_id and contract_id:
        for rev in tenant_query(Revenue).filter_by(
            contract_id=int(contract_id),
            customer_id=i.customer_id,
        ).filter(Revenue.invoice_id.is_(None)):
            rev.invoice_id = i.id
    sync_contract_invoice_status(i.contract_id)
    db.session.commit()
    try:
        from zatca_qr import is_tax_invoice
        from zatca_phase2 import process_tax_invoice
        if is_tax_invoice(i.invoice_type):
            process_tax_invoice(i, get_app_settings())
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('zatca phase2 report failed for %s: %s', i.code, exc)
    return redirect(url_for('invoices'))

@app.route('/invoices/<int:invoice_id>/print')
def invoice_print_page(invoice_id):
    from invoice_print import invoice_print_payload

    invo = tenant_get_or_404(Invoice, invoice_id)
    return render_template('invoice-print.html', **invoice_print_payload(invo, base_url=request.url_root))


@app.route('/api/invoices/<int:invoice_id>/payment-whatsapp')
def api_invoice_payment_whatsapp(invoice_id):
    from operations import financial_whatsapp_url

    url, err = financial_whatsapp_url('invoice', invoice_id, request.url_root)
    if not url:
        return jsonify({'error': err or 'تعذّر تجهيز رسالة واتساب', 'whatsapp_url': ''}), 400
    return jsonify({'whatsapp_url': url})


@app.route('/api/financial/whatsapp/<doc_type>/<int:doc_id>')
def api_financial_whatsapp(doc_type, doc_id):
    from operations import financial_whatsapp_url

    url, err = financial_whatsapp_url(doc_type, doc_id, request.url_root)
    if not url:
        return jsonify({'error': err or 'تعذّر تجهيز رسالة واتساب', 'whatsapp_url': ''}), 400
    return jsonify({'whatsapp_url': url})


@app.route('/invoices/delete/<int:id>', methods=['POST'])
def invoice_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    i = tenant_get_or_404(Invoice, id)
    contract_id = i.contract_id
    db.session.delete(i)
    sync_contract_invoice_status(contract_id)
    db.session.commit()
    return redirect(url_for('invoices'))

# =============================================
# الأصناف
# =============================================
@app.route('/inventory')
def inventory():
    items = tenant_query(InventoryItem).order_by(InventoryItem.id.desc()).all()
    items_json = [
        {
            'id': i.id,
            'code': i.code or '',
            'name': i.name or '',
            'category': i.category or '',
            'unit': i.unit or 'قطعة',
            'current_qty': float(i.current_qty or 0),
            'min_qty': float(i.min_qty or 0),
            'buy_price': float(i.buy_price or 0),
            'sell_price': float(i.sell_price or 0),
            'stock_value': float(i.stock_value or 0),
            'order_status': i.order_status,
            'supplier': i.supplier or '',
            'location': i.location or '',
            'notes': i.notes or '',
        }
        for i in items
    ]
    return render_template(
        'inventory.html',
        items=items,
        items_json=items_json,
        next_item_code=next_code(InventoryItem, '#', digits=3),
    )

@app.route('/inventory/edit/<int:id>', methods=['POST'])
def inventory_edit(id):
    from form_validation import inventory_form_error

    err = inventory_form_error(request.form)
    if err:
        flash(err, 'error')
        return redirect(url_for('inventory'))
    item = tenant_get_or_404(InventoryItem, id)
    name = (request.form.get('name') or '').strip()
    if not name:
        return redirect(url_for('inventory'))
    item.name = name
    item.category = request.form.get('category', '')
    item.unit = request.form.get('unit', 'قطعة')
    item.current_qty = float(request.form.get('current_qty', 0) or 0)
    item.min_qty = float(request.form.get('min_qty', 0) or 0)
    item.buy_price = float(request.form.get('buy_price', 0) or 0)
    item.sell_price = float(request.form.get('sell_price', 0) or 0)
    item.supplier = request.form.get('supplier', '')
    item.location = request.form.get('location', '')
    item.notes = request.form.get('notes', '')
    db.session.commit()
    return redirect(url_for('inventory'))

@app.route('/inventory/add', methods=['POST'])
def inventory_add():
    from form_validation import inventory_form_error

    err = inventory_form_error(request.form)
    if err:
        flash(err, 'error')
        return redirect(url_for('inventory'))
    name = (request.form.get('name') or '').strip()
    if not name:
        return redirect(url_for('inventory'))
    code = (request.form.get('code') or '').strip() or next_code(InventoryItem, '#', digits=3)
    if tenant_query(InventoryItem).filter_by(code=code).first():
        code = next_code(InventoryItem, '#', digits=3)
    item = InventoryItem(
        code=code,
        name=name,
        category=request.form.get('category', ''),
        unit=request.form.get('unit', 'قطعة'),
        current_qty=float(request.form.get('current_qty', 0) or 0),
        min_qty=float(request.form.get('min_qty', 0) or 0),
        buy_price=float(request.form.get('buy_price', 0) or 0),
        sell_price=float(request.form.get('sell_price', 0) or 0),
        supplier=request.form.get('supplier', ''),
        location=request.form.get('location', ''),
        notes=request.form.get('notes', ''),
    )
    assign_organization(item)
    db.session.add(item)
    db.session.commit()
    return redirect(url_for('inventory'))

@app.route('/inventory/delete/<int:id>', methods=['POST'])
def inventory_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    item = tenant_get_or_404(InventoryItem, id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('inventory'))


@app.route('/inventory/template')
def inventory_import_template():
    """تحميل نموذج استيراد الأصناف (عربي أو إنجليزي)."""
    lang = request.args.get('lang')
    if lang not in ('ar', 'en'):
        lang = resolve_user_language(getattr(g, 'auth_user', None))
    basename = 'inventory_template_en.xlsx' if lang == 'en' else 'inventory_template.xlsx'
    download_name = 'inventory_import_template_en.xlsx' if lang == 'en' else 'inventory_import_template.xlsx'
    path = os.path.join(app.root_path, 'static', 'templates', basename)
    if not os.path.isfile(path):
        script = os.path.join(app.root_path, 'scripts', 'build_inventory_template.py')
        if os.path.isfile(script):
            import importlib.util
            spec = importlib.util.spec_from_file_location('build_inventory_template', script)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.build_xlsx(path, lang=lang)
        if not os.path.isfile(path):
            abort(404)
    return send_from_directory(
        os.path.dirname(path),
        os.path.basename(path),
        as_attachment=True,
        download_name=download_name,
    )


PO_STATUSES = ['مسودة', 'مرسل', 'مستلم', 'ملغي']
PO_STATUS_EN = {'مسودة': 'Draft', 'مرسل': 'Sent', 'مستلم': 'Received', 'ملغي': 'Cancelled'}

try:
    from inventory_parts_data import ITEMS as _PO_CATALOG_ITEMS
except ImportError:
    _PO_CATALOG_ITEMS = []
_PO_ITEM_EN_BY_CODE = {
    code: name_en for _cat, code, _name_ar, name_en, _desc, _unit in _PO_CATALOG_ITEMS
}

PO_PRINT_LABELS = {
    'ar': {
        'toolbar_title': 'طباعة وإرسال طلب الشراء',
        'supplier_mobile': 'جوال المورد (واتساب)',
        'supplier_email': 'إيميل المورد',
        'print_pdf': '🖨️ طباعة / PDF',
        'save_sig': '✍️ حفظ التوقيع',
        'wa_supplier': '📄 واتساب PDF للمورد',
        'wa_purchasing': '📄 واتساب PDF للمشتريات',
        'email_pdf': '✉️ إيميل PDF',
        'save_contact': '💾 حفظ الجوال/الإيميل',
        'back': '← رجوع',
        'phone': 'الهاتف:',
        'vat': 'الرقم الضريبي:',
        'cr': 'السجل التجاري:',
        'address': 'العنوان:',
        'doc_title': 'طلب شراء',
        'doc_title_en': 'Purchase Order',
        'order_no': 'رقم الطلب',
        'supplier': 'المورد',
        'supplier_default': 'المورد',
        'order_date': 'تاريخ الطلب',
        'status': 'الحالة',
        'supplier_phone': 'جوال المورد',
        'supplier_email_lbl': 'إيميل المورد',
        'salutation': 'السادة / {name} المحترمين،',
        'letter_p1': 'تحية طيبة وبعد، نأمل منكم التفضل بتوريد البنود المذكورة في الجدول المرفق وفق الكميات والأسعار الموضحة، وذلك في أقرب وقت ممكن.',
        'letter_p2': 'نشكركم على تعاونكم، وتفضلوا بقبول فائق الاحترام والتقدير.',
        'items_title': 'تفاصيل الأصناف المطلوبة',
        'col_code_item': 'الكود / الصنف',
        'col_qty': 'الكمية',
        'col_unit_price': 'سعر الوحدة',
        'col_total': 'الإجمالي',
        'notes': 'ملاحظات:',
        'grand_total': 'إجمالي طلب الشراء',
        'sig_supplier': 'توقيع المورد / الاعتماد',
        'sig_name_line': 'الاسم والتوقيع',
        'sig_auth': 'توقيع المعتمد',
        'sig_alt': 'التوقيع',
        'sig_clear': 'مسح',
        'doc_foot': 'وثيقة صادرة من نظام LiftCore — إدارة المشتريات والمخزون',
        'doc_foot_mid': 'طلب شراء',
        'sig_required': 'يرجى رسم التوقيع أولاً',
        'sig_save_fail': 'تعذّر حفظ التوقيع',
        'sig_saved': '✅ تم حفظ التوقيع',
        'phone_required': 'يرجى إدخال جوال المورد',
        'email_required': 'يرجى إدخال إيميل المورد',
        'purch_phone_required': 'يرجى إضافة هاتف الشركة في الإعدادات (إدارة المشتريات)',
        'phone_invalid': 'رقم الجوال غير صالح',
        'pdf_generating': 'جاري إنشاء PDF...',
        'pdf_upload_fail': 'تعذّر رفع PDF',
        'wa_greeting': 'السلام عليكم',
        'wa_salutation': 'السادة / {name} المحترمين،',
        'wa_body': 'نرفق لكم طلب الشراء رقم {code}',
        'wa_date': ' بتاريخ {date}',
        'wa_link': 'يمكنكم تحميل ملف PDF من الرابط:',
        'wa_closing': 'نأمل منكم التفضل بتوريد البنود المذكورة في الطلب.',
        'wa_regards': 'مع التحية،',
        'email_subject': 'طلب شراء {code} — {company}',
    },
    'en': {
        'toolbar_title': 'Print & Send Purchase Order',
        'supplier_mobile': 'Supplier Mobile (WhatsApp)',
        'supplier_email': 'Supplier Email',
        'print_pdf': '🖨️ Print / PDF',
        'save_sig': '✍️ Save Signature',
        'wa_supplier': '📄 WhatsApp PDF to Supplier',
        'wa_purchasing': '📄 WhatsApp PDF to Purchasing',
        'email_pdf': '✉️ Email PDF',
        'save_contact': '💾 Save Phone/Email',
        'back': '← Back',
        'phone': 'Phone:',
        'vat': 'VAT No.:',
        'cr': 'CR No.:',
        'address': 'Address:',
        'doc_title': 'Purchase Order',
        'doc_title_en': 'طلب شراء',
        'order_no': 'Order No.',
        'supplier': 'Supplier',
        'supplier_default': 'Supplier',
        'order_date': 'Order Date',
        'status': 'Status',
        'supplier_phone': 'Supplier Mobile',
        'supplier_email_lbl': 'Supplier Email',
        'salutation': 'Dear / {name},',
        'letter_p1': 'Greetings. We kindly request you to supply the items listed in the attached table according to the quantities and prices shown, at your earliest convenience.',
        'letter_p2': 'Thank you for your cooperation. Sincerely yours,',
        'items_title': 'Requested Items',
        'col_code_item': 'Code / Item',
        'col_qty': 'Qty',
        'col_unit_price': 'Unit Price',
        'col_total': 'Total',
        'notes': 'Notes:',
        'grand_total': 'Purchase Order Total',
        'sig_supplier': 'Supplier / Approval Signature',
        'sig_name_line': 'Name & Signature',
        'sig_auth': 'Authorized Signature',
        'sig_alt': 'Signature',
        'sig_clear': 'Clear',
        'doc_foot': 'Document issued by LiftCore — Purchasing & Inventory',
        'doc_foot_mid': 'Purchase Order',
        'sig_required': 'Please draw your signature first',
        'sig_save_fail': 'Could not save signature',
        'sig_saved': '✅ Signature saved',
        'phone_required': 'Please enter supplier mobile',
        'email_required': 'Please enter supplier email',
        'purch_phone_required': 'Add company phone in Settings (Purchasing)',
        'phone_invalid': 'Invalid mobile number',
        'pdf_generating': 'Generating PDF...',
        'pdf_upload_fail': 'Could not upload PDF',
        'wa_greeting': 'Hello',
        'wa_salutation': 'Dear / {name},',
        'wa_body': 'Please find purchase order no. {code}',
        'wa_date': ' dated {date}',
        'wa_link': 'You can download the PDF file from:',
        'wa_closing': 'We kindly request you to supply the items listed in the order.',
        'wa_regards': 'Best regards,',
        'email_subject': 'Purchase Order {code} — {company}',
    },
}


def _po_print_labels(lang):
    return PO_PRINT_LABELS['en' if lang == 'en' else 'ar']


def _has_arabic(text):
    return bool(text) and any('\u0600' <= c <= '\u06FF' for c in str(text))


def _po_item_name_en(item):
    if not item:
        return ''
    code = (item.code or '').strip()
    if code and code in _PO_ITEM_EN_BY_CODE:
        return _PO_ITEM_EN_BY_CODE[code]
    notes = (item.notes or '').strip()
    if not notes:
        return ''
    if ' — ' in notes:
        part = notes.split(' — ', 1)[0].strip()
        if part and not _has_arabic(part):
            return part
    if not _has_arabic(notes[:40]):
        return notes
    return ''


def _po_line_label_en(line):
    name_en = _po_item_name_en(line.item)
    if name_en:
        return name_en
    if line.item and line.item.code:
        return line.item.code
    return '—'


def _po_company_display_en(settings):
    if not settings:
        return 'LiftCore'
    en = (getattr(settings, 'company_name_en', None) or '').strip()
    if en:
        return en
    ar = (settings.company_name or '').strip()
    if ar and not _has_arabic(ar):
        return ar
    return 'LiftCore'


def _po_address_display_en(settings):
    if not settings:
        return ''
    en = (getattr(settings, 'address_en', None) or '').strip()
    if en:
        return en
    ar = (settings.address or '').strip()
    if ar and not _has_arabic(ar):
        return ar
    return ''


def _po_status_bilingual(status):
    status = status or ''
    en = PO_STATUS_EN.get(status, '')
    if en and en != status:
        return f'{status} / {en}'
    return status


def _apply_purchase_receipt(order):
    if order.status != 'مستلم' or order.received_at:
        return
    db.session.flush()
    updated = False
    for line in order.lines:
        item = db.session.get(InventoryItem, line.item_id)
        if item:
            item.current_qty = (item.current_qty or 0) + (line.quantity or 0)
            updated = True
    if updated:
        order.received_at = datetime.utcnow()


@app.route('/purchase-orders')
def purchase_orders():
    orders = tenant_query(PurchaseOrder).order_by(PurchaseOrder.order_date.desc().nullslast()).all()
    items = tenant_query(InventoryItem).order_by(InventoryItem.name).all()
    return render_template(
        'purchase-orders.html',
        orders=orders,
        items=items,
        statuses=PO_STATUSES,
        next_po_code=next_code(PurchaseOrder, 'PO-', digits=4),
        today=date.today().isoformat(),
    )


@app.route('/purchase-orders/save', methods=['POST'])
def purchase_orders_save():
    order_id = request.form.get('order_id', '').strip()
    supplier = request.form.get('supplier', '').strip()
    supplier_phone = request.form.get('supplier_phone', '').strip()
    supplier_email = request.form.get('supplier_email', '').strip()
    order_date_raw = request.form.get('order_date', '').strip()
    status = request.form.get('status', 'مسودة').strip()
    notes = request.form.get('notes', '').strip()
    try:
        order_date = datetime.strptime(order_date_raw, '%Y-%m-%d').date() if order_date_raw else date.today()
    except ValueError:
        order_date = date.today()

    item_ids = request.form.getlist('item_id')
    quantities = request.form.getlist('quantity')
    unit_prices = request.form.getlist('unit_price')
    lines_data = []
    for item_id, qty, price in zip(item_ids, quantities, unit_prices):
        if not item_id:
            continue
        quantity = float(qty or 0)
        if quantity <= 0:
            continue
        unit_price = float(price or 0)
        lines_data.append({
            'item_id': int(item_id),
            'quantity': quantity,
            'unit_price': unit_price,
            'line_total': quantity * unit_price,
        })
    if not lines_data:
        return redirect(url_for('purchase_orders'))

    if order_id:
        order = tenant_get_or_404(PurchaseOrder, int(order_id))
    else:
        order = PurchaseOrder(code=next_code(PurchaseOrder, 'PO-', digits=4))
        assign_organization(order)
        db.session.add(order)

    old_status = order.status
    order.supplier = supplier or None
    order.supplier_phone = supplier_phone or None
    order.supplier_email = supplier_email or None
    order.order_date = order_date
    order.notes = notes or None
    order.status = status if status in PO_STATUSES else 'مسودة'
    order.lines.clear()
    total = 0.0
    for row in lines_data:
        line = PurchaseOrderLine(
            item_id=row['item_id'],
            quantity=row['quantity'],
            unit_price=row['unit_price'],
            line_total=row['line_total'],
        )
        assign_organization(line)
        order.lines.append(line)
        total += row['line_total']
    order.total_amount = total
    if order.status == 'مستلم' and old_status != 'مستلم':
        _apply_purchase_receipt(order)
    db.session.commit()
    return redirect(url_for('purchase_order_print', order_id=order.id))


def _purchase_order_print_context(order, *, en_only=False):
    s = tenant_query(Settings).first()
    logo_w = (getattr(s, 'logo_width_report', None) or 150) if s else 150
    uid = session.get('user_id')
    user = db.session.get(User, uid) if uid else None
    lang = 'en' if en_only else resolve_user_language(user)
    po_ar = PO_PRINT_LABELS['ar']
    po_en = PO_PRINT_LABELS['en']
    po_ui = po_en if en_only else _po_print_labels(lang)
    company_name_ar = (s.company_name if s and s.company_name else 'LiftCore')
    company_name_en = (getattr(s, 'company_name_en', None) or '').strip() if s else ''
    company_address_ar = (s.address or '').strip() if s else ''
    company_address_en = (getattr(s, 'address_en', None) or '').strip() if s else ''
    item_names_en = {line.id: _po_item_name_en(line.item) for line in order.lines}
    item_labels_en = {line.id: _po_line_label_en(line) for line in order.lines}
    if en_only:
        company_display = _po_company_display_en(s)
        address_display = _po_address_display_en(s)
    else:
        company_display = company_name_en or company_name_ar
        address_display = company_address_en or company_address_ar
    return dict(
        order=order,
        logo_width=logo_w,
        purchasing_phone=(getattr(s, 'phone', None) or '') if s else '',
        purchasing_email=(getattr(s, 'email', None) or '') if s else '',
        po_ar=po_ar,
        po_en=po_en,
        po_ui=po_ui,
        po_lang=lang,
        en_only=en_only,
        po_status_label=(
            PO_STATUS_EN.get(order.status, order.status)
            if en_only else _po_status_bilingual(order.status)
        ),
        po_company_name_ar=company_name_ar,
        po_company_name_en=company_name_en,
        po_company_address_ar=company_address_ar,
        po_company_address_en=company_address_en,
        po_company_display=company_display,
        po_address_display=address_display,
        item_names_en=item_names_en,
        item_labels_en=item_labels_en,
    )


@app.route('/purchase-orders/<int:order_id>/print')
def purchase_order_print(order_id):
    order = tenant_get_or_404(PurchaseOrder, order_id)
    return render_template(
        'purchase-order-print.html',
        **_purchase_order_print_context(order),
    )


@app.route('/purchase-orders/<int:order_id>/print-en')
def purchase_order_print_en(order_id):
    order = tenant_get_or_404(PurchaseOrder, order_id)
    return render_template(
        'purchase-order-print.html',
        **_purchase_order_print_context(order, en_only=True),
    )


@app.route('/purchase-orders/<int:order_id>/contact', methods=['POST'])
def purchase_order_update_contact(order_id):
    order = tenant_get_or_404(PurchaseOrder, order_id)
    order.supplier_phone = request.form.get('supplier_phone', '').strip() or None
    order.supplier_email = request.form.get('supplier_email', '').strip() or None
    db.session.commit()
    if request.form.get('en_only') == '1':
        return redirect(url_for('purchase_order_print_en', order_id=order.id))
    return redirect(url_for('purchase_order_print', order_id=order.id))


@app.route('/purchase-orders/<int:order_id>/signature', methods=['POST'])
def purchase_order_save_signature(order_id):
    order = tenant_get_or_404(PurchaseOrder, order_id)
    payload = request.get_json(silent=True) or {}
    sig = (payload.get('signature') or '').strip()
    if sig and sig.startswith('data:image/') and len(sig) < 600000:
        order.signature_data = sig
        db.session.commit()
    return jsonify(ok=True)


@app.route('/purchase-orders/<int:order_id>/pdf', methods=['POST'])
def purchase_order_upload_pdf(order_id):
    order = tenant_get_or_404(PurchaseOrder, order_id)
    upload = request.files.get('pdf')
    if not upload:
        return jsonify(ok=False, error='لم يُرفَع ملف PDF'), 400
    folder = os.path.join(PO_UPLOAD_ROOT, str(order_id))
    os.makedirs(folder, exist_ok=True)
    safe_code = re.sub(r'[^\w\-]', '_', order.code or f'PO-{order_id}')
    filename = f'{safe_code}.pdf'
    upload.save(os.path.join(folder, filename))
    order.pdf_path = f'uploads/purchase_orders/{order_id}/{filename}'
    db.session.commit()
    pdf_url = url_for('static', filename=order.pdf_path, _external=True)
    return jsonify(ok=True, url=pdf_url)


@app.route('/purchase-orders/<int:order_id>/remove-pdf', methods=['POST'])
def purchase_order_remove_pdf(order_id):
    """حذف PDF طلب الشراء المرفوع — مدير النظام فقط."""
    err = enforce_admin_attachment_delete(json_response=True)
    if err:
        return err
    order = tenant_get_or_404(PurchaseOrder, order_id)
    path = (order.pdf_path or '').strip()
    if not path:
        return jsonify({'ok': True, 'removed': False, 'message': 'لا يوجد مرفق'})
    full = os.path.join(app.root_path, 'static', path.replace('/', os.sep))
    if os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass
    order.pdf_path = None
    db.session.commit()
    return jsonify({'ok': True, 'removed': True, 'id': order.id})


@app.route('/purchase-orders/delete/<int:order_id>', methods=['POST'])
def purchase_orders_delete(order_id):
    err = enforce_admin_delete()
    if err:
        return err
    order = tenant_get_or_404(PurchaseOrder, order_id)
    if order.status == 'مستلم':
        return redirect(url_for('purchase_orders'))
    db.session.delete(order)
    db.session.commit()
    return redirect(url_for('purchase_orders'))


# =============================================
# تقدير تكلفة إنشاء مصعد
# =============================================
def _parse_estimate_spec(form):
    floors = int(form.get('floors') or 2)
    stops = int(form.get('stops') or floors)
    return {
        'machine_type': form.get('machine_type', 'MR').strip(),
        'elev_type': form.get('elev_type', 'مصعد ركاب').strip(),
        'floors': floors,
        'stops': stops,
        'capacity_kg': form.get('capacity_kg'),
        'doors_count': form.get('doors_count') or stops,
        'include_installation': form.get('include_installation', '1'),
        'include_install_materials': form.get('include_install_materials', '1'),
        'include_shaft_work': form.get('include_shaft_work', '0'),
        'travel_m': form.get('travel_m'),
    }


def _parse_estimate_lines(form):
    categories = form.getlist('line_category')
    descriptions = form.getlist('line_description')
    quantities = form.getlist('line_quantity')
    units = form.getlist('line_unit')
    unit_prices = form.getlist('line_unit_price')
    lines = []
    for cat, desc, qty, unit, price in zip(categories, descriptions, quantities, units, unit_prices):
        desc = (desc or '').strip()
        if not desc:
            continue
        quantity = float(qty or 0)
        unit_price = float(price or 0)
        if quantity <= 0:
            continue
        lines.append({
            'category': (cat or '').strip() or 'أخرى',
            'description': desc,
            'quantity': quantity,
            'unit': (unit or '').strip() or 'وحدة',
            'unit_price': unit_price,
            'line_total': round(quantity * unit_price, 2),
        })
    return lines


@app.route('/elevator-estimates')
def elevator_estimates():
    estimates = tenant_query(ElevatorEstimate).order_by(ElevatorEstimate.created_at.desc()).all()
    customers = tenant_query(Customer).order_by(Customer.name).all()
    edit_raw = request.args.get('edit', '').strip()
    edit_est = None
    if edit_raw.isdigit():
        edit_est = tenant_query(ElevatorEstimate).filter_by(id=int(edit_raw)).first()
    return render_template(
        'elevator-estimates.html',
        estimates=estimates,
        customers=customers,
        edit_est=edit_est,
        machine_types=MACHINE_TYPES,
        elev_types=ELEV_TYPES,
        statuses=ESTIMATE_STATUSES,
        next_es_code=next_code(ElevatorEstimate, 'ES-', digits=4),
        today=date.today().isoformat(),
        default_vat=DEFAULT_VAT_PCT,
        default_margin=DEFAULT_MARGIN_PCT,
    )


@app.route('/api/elevator-estimates/calculate', methods=['POST'])
def api_elevator_estimate_calculate():
    data = request.get_json(silent=True) or request.form
    spec = {
        'machine_type': data.get('machine_type', 'MR'),
        'elev_type': data.get('elev_type', 'مصعد ركاب'),
        'floors': data.get('floors'),
        'stops': data.get('stops'),
        'capacity_kg': data.get('capacity_kg'),
        'doors_count': data.get('doors_count'),
        'include_installation': data.get('include_installation', '1'),
        'include_install_materials': data.get('include_install_materials', '1'),
        'include_shaft_work': data.get('include_shaft_work', '0'),
        'travel_m': data.get('travel_m'),
    }
    lines = calculate_lines(spec)
    totals = summarize_lines(lines, data.get('margin_pct'), data.get('vat_pct'))
    return jsonify(ok=True, lines=lines, totals=totals)


@app.route('/elevator-estimates/save', methods=['POST'])
def elevator_estimates_save():
    estimate_id = request.form.get('estimate_id', '').strip()
    lines_data = _parse_estimate_lines(request.form)
    if not lines_data:
        auto_lines = calculate_lines(_parse_estimate_spec(request.form))
        lines_data = auto_lines
    if not lines_data:
        return redirect(url_for('elevator_estimates'))

    margin_pct = float(request.form.get('margin_pct') or DEFAULT_MARGIN_PCT)
    vat_pct = float(request.form.get('vat_pct') or DEFAULT_VAT_PCT)
    totals = summarize_lines(lines_data, margin_pct, vat_pct)

    if estimate_id:
        est = tenant_get_or_404(ElevatorEstimate, int(estimate_id))
    else:
        est = ElevatorEstimate(code=next_code(ElevatorEstimate, 'ES-', digits=4))
        assign_organization(est)
        db.session.add(est)

    cust_raw = request.form.get('customer_id', '').strip()
    est.customer_id = int(cust_raw) if cust_raw.isdigit() else None
    est.project_name = request.form.get('project_name', '').strip() or None
    est.city = request.form.get('city', '').strip() or None
    est.machine_type = request.form.get('machine_type', 'MR').strip()
    est.elev_type = request.form.get('elev_type', 'مصعد ركاب').strip()
    est.floors = int(request.form.get('floors') or 2)
    est.stops = int(request.form.get('stops') or est.floors)
    est.capacity_kg = int(request.form.get('capacity_kg') or 630)
    est.speed = request.form.get('speed', '').strip() or None
    travel_raw = request.form.get('travel_m', '').strip()
    est.travel_m = float(travel_raw) if travel_raw else None
    est.doors_count = int(request.form.get('doors_count') or est.stops)
    est.include_installation = request.form.get('include_installation') == '1'
    est.include_shaft_work = request.form.get('include_shaft_work') == '1'
    est.margin_pct = margin_pct
    est.vat_pct = vat_pct
    est.cost_subtotal = totals['cost_subtotal']
    est.margin_amount = totals['margin_amount']
    est.subtotal = totals['subtotal']
    est.vat_amount = totals['vat_amount']
    est.total = totals['total']
    status = request.form.get('status', 'مسودة').strip()
    est.status = status if status in ESTIMATE_STATUSES else 'مسودة'
    est.notes = request.form.get('notes', '').strip() or None
    date_raw = request.form.get('estimate_date', '').strip()
    try:
        est.estimate_date = datetime.strptime(date_raw, '%Y-%m-%d').date() if date_raw else date.today()
    except ValueError:
        est.estimate_date = date.today()

    est.lines.clear()
    for row in lines_data:
        line = ElevatorEstimateLine(
            category=row.get('category'),
            description=row.get('description'),
            quantity=row.get('quantity') or 0,
            unit=row.get('unit'),
            unit_price=row.get('unit_price') or 0,
            line_total=row.get('line_total') or 0,
        )
        assign_organization(line)
        est.lines.append(line)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception('elevator_estimates_save failed')
        flash('تعذّر حفظ التقدير — تحقق من البنود وحاول مرة أخرى', 'error')
        return redirect(url_for('elevator_estimates'))
    return redirect(url_for('elevator_estimate_print', estimate_id=est.id))


@app.route('/elevator-estimates/delete/<int:estimate_id>', methods=['POST'])
def elevator_estimates_delete(estimate_id):
    err = enforce_admin_delete()
    if err:
        return err
    est = tenant_get_or_404(ElevatorEstimate, estimate_id)
    db.session.delete(est)
    db.session.commit()
    return redirect(url_for('elevator_estimates'))


@app.route('/elevator-estimates/print/<int:estimate_id>')
def elevator_estimate_print(estimate_id):
    est = tenant_get_or_404(ElevatorEstimate, estimate_id)
    s = tenant_query(Settings).first()
    logo_w = (getattr(s, 'logo_width_report', None) or 150) if s else 150
    return render_template(
        'elevator-estimate-print.html',
        est=est,
        logo_width=logo_w,
        company_settings=s,
    )

# =============================================
# حركة المخزن
# =============================================

def _adjust_inventory_qty(item, direction, qty, *, reverse=False):
    """تطبيق أو عكس تأثير حركة مخزون على رصيد الصنف."""
    from inventory_stock import adjust_inventory_qty

    adjust_inventory_qty(item, direction, qty, reverse=reverse)


@app.route('/stock-movements')
def stock_movements():
    from sqlalchemy.orm import joinedload

    movements = (
        tenant_query(StockMovement)
        .options(joinedload(StockMovement.item))
        .order_by(StockMovement.movement_date.desc())
        .all()
    )
    items = tenant_query(InventoryItem).order_by(InventoryItem.name).all()
    technicians = tenant_query(Technician).filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).all()
    tech_names = {t.id: t.name for t in technicians}
    return render_template(
        'stock-movements.html',
        movements=movements,
        items=items,
        technicians=technicians,
        movements_js=[stock_movement_to_js_dict(m, tech_names) for m in movements],
        items_js=[inventory_item_js_dict(i) for i in items],
        technicians_js=[{'id': t.id, 'name': t.name} for t in technicians],
    )

@app.route('/stock-movements/add', methods=['POST'])
def stock_add():
    item_id   = int(request.form['item_id'])
    qty       = float(request.form.get('quantity', 0))
    direction = request.form.get('direction','صادر')
    unit_price= float(request.form.get('unit_price', 0))

    m = StockMovement(
        code          = next_code(StockMovement, 'MV-', digits=3),
        item_id       = item_id,
        movement_date = datetime.strptime(request.form['movement_date'], '%Y-%m-%d').date(),
        direction     = direction,
        movement_type = request.form.get('movement_type',''),
        quantity      = qty,
        unit_price    = unit_price,
        total_value   = qty * unit_price,
        technician_id = request.form.get('technician_id') or None,
        reason        = request.form.get('reason',''),
        notes         = request.form.get('notes',''),
    )
    assign_organization(m)
    db.session.add(m)

    item = tenant_query(InventoryItem).filter_by(id=item_id).first()
    _adjust_inventory_qty(item, direction, qty)

    db.session.commit()
    return redirect(url_for('stock_movements'))

@app.route('/stock-movements/delete/<int:id>', methods=['POST'])
def stock_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    m = tenant_get_or_404(StockMovement, id)
    item = tenant_query(InventoryItem).filter_by(id=m.item_id).first()
    _adjust_inventory_qty(item, m.direction, m.quantity, reverse=True)
    db.session.delete(m)
    db.session.commit()
    return redirect(url_for('stock_movements'))

# =============================================
# بيان القطع
# =============================================
@app.route('/parts-billing/template')
def parts_billing_import_template():
    """تحميل نموذج استيراد قطع الغيار."""
    path = os.path.join(app.root_path, 'static', 'templates', 'parts_billing_template.xlsx')
    if not os.path.isfile(path):
        script = os.path.join(app.root_path, 'scripts', 'build_parts_billing_template.py')
        if os.path.isfile(script):
            import importlib.util
            spec = importlib.util.spec_from_file_location('build_parts_billing_template', script)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.build_xlsx(path)
        if not os.path.isfile(path):
            abort(404)
    return send_from_directory(
        os.path.dirname(path),
        os.path.basename(path),
        as_attachment=True,
        download_name='parts_billing_template.xlsx',
    )


@app.route('/parts-billing/import', methods=['POST'])
def parts_billing_import():
    """استيراد بيان تركيب قطع الغيار من Excel."""
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'error': 'لم يُرفَع ملف Excel'}), 400
    if not upload.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'الملف يجب أن يكون .xlsx'}), 400

    dry_run = request.form.get('dry_run') == '1'
    force = request.form.get('force') == '1'

    try:
        from parts_billing_import import import_parts_billing_file

        result = import_parts_billing_file(
            upload.read(),
            dry_run=dry_run,
            skip_existing=not force,
            db_session=None if dry_run else db.session,
            next_code_fn=next_code,
        )
        return jsonify(result)
    except ImportError:
        return jsonify({'error': 'مكتبة openpyxl غير مثبتة على السيرفر'}), 500
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error': f'فشل الاستيراد: {exc}'}), 500


@app.route('/parts-billing')
def parts_billing():
    from operations import parts_alerts, parts_stats
    from sqlalchemy.orm import joinedload

    parts = (
        tenant_query(PartsBilling)
        .options(
            joinedload(PartsBilling.customer),
            joinedload(PartsBilling.contract),
            joinedload(PartsBilling.elevator),
            joinedload(PartsBilling.technician),
            joinedload(PartsBilling.visit),
            joinedload(PartsBilling.fault),
        )
        .order_by(PartsBilling.billing_date.desc())
        .all()
    )
    customers = tenant_query(Customer).order_by(Customer.name).all()
    contracts = tenant_query(Contract).order_by(Contract.code).all()
    inventory_items = tenant_query(InventoryItem).order_by(InventoryItem.name).all()
    technicians = tenant_query(Technician).filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول'])
    ).order_by(Technician.name).all()
    pending_faults = tenant_query(Fault).filter_by(status='انتظار قطع').order_by(
        Fault.reported_at.desc()
    ).all()
    return render_template(
        'parts-billing.html',
        parts=parts,
        parts_js=_parts_js_list(parts),
        customers=customers,
        contracts=contracts,
        customers_js=[{'id': c.id, 'code': c.code, 'name': c.name} for c in customers],
        contracts_js=[{'id': c.id, 'code': c.code, 'customer_id': c.customer_id} for c in contracts],
        inventory_items_js=[
            {
                'id': i.id,
                'code': i.code,
                'name': i.name,
                'unit': i.unit or 'قطعة',
                'buy_price': i.buy_price or 0,
                'sell_price': i.sell_price or 0,
            }
            for i in inventory_items
        ],
        technicians_js=[{'id': t.id, 'name': t.name} for t in technicians],
        next_part_code=next_code(PartsBilling, 'PB-', digits=3),
        parts_workflow_stats=parts_stats(),
        parts_alerts=parts_alerts(),
        pending_faults=pending_faults,
    )

@app.route('/parts-billing/edit/<int:id>', methods=['POST'])
def parts_edit(id):
    from entity_links import resolve_parts_links
    from inventory_stock import reverse_stock_by_reference, stock_reference
    from operations import apply_parts_billing_inventory, parse_fault_parts_lines

    p = tenant_get_or_404(PartsBilling, id)
    lines = parse_fault_parts_lines(request.form.get('parts_lines'))
    user_notes = request.form.get('notes', '')
    cost = float(request.form.get('cost_price', 0))
    sell = float(request.form.get('sell_price', 0))
    links = resolve_parts_links(
        customer_id=request.form.get('customer_id'),
        contract_id=request.form.get('contract_id'),
        contract_code=request.form.get('contract_code'),
        customer_name=request.form.get('customer_name'),
        elevator_id=request.form.get('elevator_id'),
        technician_id=request.form.get('technician_id'),
        visit_id=request.form.get('visit_id'),
        fault_id=request.form.get('fault_id'),
        visit_code=request.form.get('visit_code'),
        fault_code=request.form.get('fault_code'),
    )
    p.customer_id    = links['customer_id']
    p.contract_id    = links['contract_id']
    p.elevator_id    = links['elevator_id']
    p.technician_id  = links['technician_id']
    p.visit_id       = links['visit_id']
    p.fault_id       = links['fault_id']
    p.billing_date = datetime.strptime(request.form['billing_date'], '%Y-%m-%d').date()
    p.payment_note = (request.form.get('payment_note') or '').strip() or None
    # الحالة تُحدَّث من تسجيل الإيراد — لا تُغيَّر من نموذج التعديل
    if lines:
        try:
            apply_parts_billing_inventory(p, lines, user_notes=user_notes)
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'error')
            return redirect(url_for('parts_billing'))
    else:
        reverse_stock_by_reference(stock_reference('parts_billing', p.id))
        p.description = request.form.get('description', '')
        p.cost_price = cost
        p.sell_price = sell
        p.profit = sell - cost
        p.notes = user_notes
    if links['fault_id']:
        fault = tenant_query(Fault).filter_by(id=links['fault_id']).first()
        if fault:
            fault.billed = True
    try:
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
    return redirect(url_for('parts_billing'))

@app.route('/parts-billing/add', methods=['POST'])
def parts_add():
    from entity_links import resolve_parts_links
    from operations import apply_parts_billing_inventory, parse_fault_parts_lines

    lines = parse_fault_parts_lines(request.form.get('parts_lines'))
    user_notes = request.form.get('notes', '')
    cost = float(request.form.get('cost_price', 0))
    sell = float(request.form.get('sell_price', 0))
    links = resolve_parts_links(
        customer_id=request.form.get('customer_id'),
        contract_id=request.form.get('contract_id'),
        contract_code=request.form.get('contract_code'),
        customer_name=request.form.get('customer_name'),
        elevator_id=request.form.get('elevator_id'),
        technician_id=request.form.get('technician_id'),
        visit_id=request.form.get('visit_id'),
        fault_id=request.form.get('fault_id'),
        visit_code=request.form.get('visit_code'),
        fault_code=request.form.get('fault_code'),
    )
    p = PartsBilling(
        code          = next_code(PartsBilling, 'PB-', digits=3),
        customer_id   = links['customer_id'],
        contract_id   = links['contract_id'],
        elevator_id   = links['elevator_id'],
        technician_id = links['technician_id'],
        visit_id      = links['visit_id'],
        fault_id      = links['fault_id'],
        billing_date=datetime.strptime(request.form['billing_date'], '%Y-%m-%d').date(),
        description=request.form.get('description', ''),
        cost_price=cost,
        sell_price=sell,
        profit=sell - cost,
        payment_note=None,
        status='غير محصل',
        notes=user_notes,
    )
    assign_organization(p)
    db.session.add(p)
    db.session.flush()
    if lines:
        try:
            apply_parts_billing_inventory(p, lines, user_notes=user_notes)
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'error')
            return redirect(url_for('parts_billing'))
    if links['fault_id']:
        fault = tenant_query(Fault).filter_by(id=links['fault_id']).first()
        if fault:
            fault.billed = True
    try:
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
    return redirect(url_for('parts_billing'))

@app.route('/parts-billing/delete/<int:id>', methods=['POST'])
def parts_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    from inventory_stock import reverse_stock_by_reference, stock_reference

    p = tenant_get_or_404(PartsBilling, id)
    reverse_stock_by_reference(stock_reference('parts_billing', p.id))
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for('parts_billing'))

# =============================================
# التقارير
# =============================================
@app.route('/reports')
def reports():
    return render_template('reports.html')

def _report_ctx():
    return {
        'db': db,
        'Customer': Customer,
        'Elevator': Elevator,
        'Contract': Contract,
        'Technician': Technician,
        'MaintenanceVisit': MaintenanceVisit,
        'Fault': Fault,
        'Revenue': Revenue,
        'Expense': Expense,
        'Invoice': Invoice,
        'InventoryItem': InventoryItem,
        'StockMovement': StockMovement,
        'PartsBilling': PartsBilling,
        'contract_display_status': contract_display_status,
    }


def _render_report_page(report_id, template):
    from report_data import fetch_report_rows
    return render_template(
        template,
        report_rows=fetch_report_rows(report_id, _report_ctx()),
        report_id=report_id,
    )


@app.route('/reports/dashboard')
def report_dashboard():
    return render_template('report-dashboard.html', current_year=date.today().year)

@app.route('/reports/client-annual')
def report_client_annual():
    customers = tenant_query(Customer).order_by(Customer.name).all()
    customers_json = [{'id': c.id, 'name': c.name, 'code': c.code} for c in customers]
    cur_year = date.today().year
    report_years = list(range(cur_year, cur_year - 6, -1))
    return render_template(
        'report-annual.html',
        customers=customers,
        customers_json=customers_json,
        report_years=report_years,
        current_year=cur_year,
    )


@app.route('/reports/customer-statement')
def report_customer_statement():
    """كشف حساب عميل — مدين/دائن/رصيد مستحق."""
    customers = tenant_query(Customer).order_by(Customer.name).all()
    selected_id = request.args.get('customer_id', type=int)
    settings = tenant_query(Settings).first()
    company_json = {
        'name': (settings.company_name if settings and settings.company_name else 'LiftCore'),
        'vat': (getattr(settings, 'vat_number', None) or '') if settings else '',
        'logo': brand_logo_url(settings),
    }
    return render_template(
        'report-customer-statement.html',
        customers=customers,
        selected_id=selected_id,
        company_json=company_json,
        brand_logo_url=brand_logo_url(settings),
    )


@app.route('/reports/clients')
def report_clients():
    return _render_report_page('report-clients', 'report-clients.html')

@app.route('/reports/elevators')
def report_elevators():
    return _render_report_page('report-elevators', 'report-elevators.html')

@app.route('/reports/contracts')
def report_contracts():
    return _render_report_page('report-contracts', 'report-contracts.html')

@app.route('/reports/technicians')
def report_technicians():
    return _render_report_page('report-technicians', 'report-technicians.html')

@app.route('/reports/maintenance-visits')
def report_maintenance():
    return _render_report_page('report-maintenance', 'report-maintenance.html')

@app.route('/reports/faults')
def report_faults():
    return _render_report_page('report-faults', 'report-faults.html')

@app.route('/reports/revenues')
def report_revenues():
    return _render_report_page('report-revenues', 'report-revenues.html')

@app.route('/reports/expenses')
def report_expenses():
    return _render_report_page('report-expenses', 'report-expenses.html')

@app.route('/reports/invoices')
def report_invoices():
    return _render_report_page('report-invoices', 'report-invoices.html')

@app.route('/reports/parts-billing')
def report_parts_billing():
    return _render_report_page('report-parts', 'report-parts.html')

@app.route('/reports/inventory')
def report_inventory():
    return _render_report_page('report-inventory', 'report-inventory.html')

@app.route('/reports/stock-movements')
def report_stock():
    return _render_report_page('report-stock', 'report-stock.html')


@app.route('/reports/financial')
def report_financial():
    today = date.today()
    return render_template(
        'report-financial.html',
        default_date_from=date(today.year, 1, 1).isoformat(),
        default_date_to=today.isoformat(),
    )


@app.route('/reports/contract-forecast')
def report_contract_forecast():
    today = date.today()
    next_month = today.month + 1
    next_year = today.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    return render_template(
        'report-contract-forecast.html',
        default_year=next_year,
        default_month=next_month,
        current_year=today.year,
    )


@app.route('/reports/financial-health')
def report_financial_health():
    return render_template(
        'report-financial-health.html',
        current_year=date.today().year,
    )


def _require_manager_or_admin():
    user = require_login()
    if not user or user.role not in ('admin', 'manager'):
        return None
    return user


@app.route('/reports/billing-discrepancies')
def report_billing_discrepancies():
    if not _require_manager_or_admin():
        return redirect(url_for('login'))
    return render_template('report-billing-discrepancies.html')


@app.route('/api/reports/billing-discrepancies')
def api_report_billing_discrepancies():
    if not _require_manager_or_admin():
        return jsonify({'error': 'صلاحية المدير أو مدير العمليات مطلوبة'}), 403
    from billing_consistency import billing_discrepancies_report

    return jsonify(billing_discrepancies_report())

# =============================================
# المستخدمون — مساعدات
# =============================================
def password_is_hashed(stored):
    return bool(stored) and stored.startswith(('pbkdf2:', 'scrypt:', 'argon2:'))


def hash_password(plain):
    return generate_password_hash(plain or '')


def verify_password(stored, plain):
    if not stored or plain is None:
        return False
    if password_is_hashed(stored):
        return check_password_hash(stored, plain)
    return stored == plain


def _migrate_plain_text_passwords():
    """ترقية كلمات المرور القديمة (نص صريح) إلى تشفير pbkdf2 عند التشغيل."""
    changed = False
    for u in tenant_query(User).all():
        if u.password_hash and not password_is_hashed(u.password_hash):
            u.password_hash = hash_password(u.password_hash)
            changed = True
    if changed:
        db.session.commit()


def _flag_weak_default_passwords():
    """يُعلِم المستخدمين بكلمات مرور افتراضية معروفة."""
    from liftcore_security import BANNED_PASSWORDS
    changed = False
    for u in tenant_query(User).all():
        if getattr(u, 'must_change_password', False):
            continue
        for weak in BANNED_PASSWORDS:
            if verify_password(u.password_hash, weak):
                u.must_change_password = True
                changed = True
                break
    if changed:
        db.session.commit()


if os.environ.get('LIFTCORE_ALEMBIC', '').strip().lower() not in ('1', 'true', 'yes'):
    with app.app_context():
        try:
            _migrate_plain_text_passwords()
            _flag_weak_default_passwords()
        except Exception as exc:
            db.session.rollback()
            app.logger.warning('Password migration error: %s', exc)


def generate_password(length=12):
    alphabet = string.ascii_letters + string.digits + '@#$!&'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# =============================================
# الإعدادات
# =============================================
def _save_company_logo(settings_row, file_storage):
    """يحفظ شعار العميل. يرجع (ok, message_ar|None)."""
    if not file_storage or not file_storage.filename:
        return True, None
    if not _ext_ok(file_storage.filename, ALLOWED_LOGO_EXT):
        return False, 'نوع ملف الشعار غير مدعوم — استخدم PNG أو JPG أو WEBP أو SVG.'
    ok_up, err_up = _upload_ok(file_storage, ALLOWED_LOGO_EXT)
    if not ok_up:
        return False, err_up or 'تعذّر قبول ملف الشعار.'

    org_id = getattr(settings_row, 'organization_id', None) or 0
    dest_dir = os.path.join(COMPANY_UPLOAD_ROOT, str(org_id))
    os.makedirs(dest_dir, exist_ok=True)
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    if ext == 'jpeg':
        ext = 'jpg'
    # اسم فريد يكسر الكاش حتى لو بقي service worker قديماً
    filename = f'logo-{int(time.time())}.{ext}'
    for old in os.listdir(dest_dir):
        if old.startswith('logo'):
            try:
                os.remove(os.path.join(dest_dir, old))
            except OSError:
                pass
    dest = os.path.join(dest_dir, filename)
    file_storage.save(dest)
    if not os.path.isfile(dest):
        return False, 'فشل حفظ ملف الشعار على السيرفر.'
    settings_row.logo_path = f'uploads/company/{org_id}/{filename}'
    return True, 'تم تحديث شعار الشركة.'


def _save_company_image_asset(settings_row, file_storage, *, attr_name: str, prefix: str, label_ar: str):
    """يحفظ ختم/توقيع الشركة للطباعة. يرجع (ok, message_ar|None)."""
    if not file_storage or not file_storage.filename:
        return True, None
    if not _ext_ok(file_storage.filename, ALLOWED_LOGO_EXT):
        return False, f'نوع ملف {label_ar} غير مدعوم — استخدم PNG أو JPG أو WEBP أو SVG.'
    ok_up, err_up = _upload_ok(file_storage, ALLOWED_LOGO_EXT)
    if not ok_up:
        return False, err_up or f'تعذّر قبول ملف {label_ar}.'

    org_id = getattr(settings_row, 'organization_id', None) or 0
    dest_dir = os.path.join(COMPANY_UPLOAD_ROOT, str(org_id))
    os.makedirs(dest_dir, exist_ok=True)
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    if ext == 'jpeg':
        ext = 'jpg'
    filename = f'{prefix}-{int(time.time())}.{ext}'
    for old in os.listdir(dest_dir):
        if old.startswith(prefix):
            try:
                os.remove(os.path.join(dest_dir, old))
            except OSError:
                pass
    dest = os.path.join(dest_dir, filename)
    file_storage.save(dest)
    if not os.path.isfile(dest):
        return False, f'فشل حفظ ملف {label_ar} على السيرفر.'
    setattr(settings_row, attr_name, f'uploads/company/{org_id}/{filename}')
    return True, f'تم تحديث {label_ar}.'


def _clamp_logo_width(value, default=150, min_w=60, max_w=400):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_w, min(max_w, n))


def _clamp_document_asset_value(value, default=0, min_value=-200, max_value=200):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, n))


def _settings_redirect(tab='company', **kwargs):
    params = {'tab': tab, **kwargs}
    return redirect(url_for('settings', **params))


@app.route('/settings')
def settings():
    user = require_login()
    if not user:
        return redirect(url_for('login'))
    try:
        from liftcore_permissions import ensure_permissions_schema
        ensure_permissions_schema(db.session, db.engine)
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('settings permissions schema: %s', exc)
    s = get_app_settings()
    users = tenant_query(User).order_by(User.id).all()
    edit_user = None
    edit_id = request.args.get('edit_user', type=int)
    if edit_id and user.role == 'admin':
        edit_user = tenant_query(User).filter_by(id=edit_id).first()
    try:
        signatories = tenant_query(Signatory).filter_by(is_active=True).order_by(Signatory.name).all()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('signatories load failed: %s', exc)
        signatories = []
    from field_auth import technician_has_field_pin
    from work_calendar import (
        COUNTRY_OPTIONS,
        WEEKDAY_LABELS_AR,
        WEEKDAY_ORDER_AR,
        custom_holidays,
        extra_work_days,
        work_weekdays,
    )

    field_technicians = []
    for t in tenant_query(Technician).order_by(Technician.name).all():
        field_technicians.append({
            'id': t.id,
            'code': t.code,
            'name': t.name,
            'phone': t.phone or t.phone2 or '',
            'team': t.team or 'عام',
            'status': t.status or 'متاح',
            'has_field_pin': technician_has_field_pin(t),
        })
    from liftcore_permissions import parse_permissions_extra
    edit_user_perms = (
        parse_permissions_extra(edit_user.permissions_extra)
        if edit_user else {'grants': [], 'denies': []}
    )
    from models import ZatcaCredentials
    zatca_creds = tenant_query(ZatcaCredentials).first()
    from moyasar_payments import moyasar_enabled
    from platform_billing import effective_amount, refresh_billing_status
    from entitlements import resolve_entitlements
    from models import Organization
    from tenant_scope import effective_organization_id
    oid = effective_organization_id()
    current_org = db.session.get(Organization, oid) if oid else None
    if current_org:
        refresh_billing_status(current_org)
    plan_amount = effective_amount(current_org) if current_org else 0
    entitlements = resolve_entitlements(org=current_org) if current_org else None
    paid_flag = request.args.get('paid')
    if paid_flag == '1':
        session['settings_notice'] = 'تم الدفع بنجاح — سيُحدَّث الاشتراك خلال لحظات.'
    elif paid_flag == '0':
        session['settings_notice'] = 'لم يكتمل الدفع.'
    return render_template(
        'settings.html',
        settings=s,
        users=users,
        signatories=signatories,
        field_technicians=field_technicians,
        current_user=user,
        active_tab=request.args.get('tab', 'company'),
        edit_user=edit_user,
        edit_user_perms=edit_user_perms,
        settings_notice=session.pop('settings_notice', None),
        generated_username=session.pop('settings_generated_username', None),
        generated_password=session.pop('settings_generated_password', None),
        country_options=COUNTRY_OPTIONS,
        weekday_order=WEEKDAY_ORDER_AR,
        weekday_labels=WEEKDAY_LABELS_AR,
        work_days_selected=work_weekdays(s),
        custom_holidays_text='\n'.join(sorted(d.isoformat() for d in custom_holidays(s))),
        extra_work_days_text='\n'.join(sorted(d.isoformat() for d in extra_work_days(s))),
        zatca_creds=zatca_creds,
        current_org=current_org,
        plan_amount=plan_amount,
        entitlements=entitlements,
        moyasar_enabled=moyasar_enabled(),
    )


@app.route('/settings/field-portal/<int:tech_id>/pin', methods=['POST'])
def settings_field_portal_pin(tech_id):
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة.'
        return _settings_redirect('field-portal')
    from signature_auth import validate_sign_pin

    tech = tenant_get_or_404(Technician, tech_id)
    pin = (request.form.get('pin') or '').strip()
    if not validate_sign_pin(pin):
        session['settings_notice'] = 'رمز دخول الجوال يجب أن يكون 6 أرقام.'
        return _settings_redirect('field-portal')
    tech.sign_pin_hash = hash_password(pin)
    sig = tenant_query(Signatory).filter_by(technician_id=tech.id, is_active=True).first()
    if sig:
        sig.sign_pin_hash = tech.sign_pin_hash
    db.session.commit()
    session['settings_notice'] = f'تم تفعيل رمز دخول الجوال للفني {tech.name} ({tech.code}).'
    return _settings_redirect('field-portal')


@app.route('/settings/signatories/add', methods=['POST'])
def settings_signatory_add():
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة.'
        return _settings_redirect('signatures')
    from signatory_service import upsert_signatory

    name = request.form.get('name', '').strip()
    national_id = request.form.get('national_id', '').strip()
    role = request.form.get('role', 'technician')
    pin = request.form.get('sign_pin', '').strip()
    file_storage = request.files.get('signature')
    has_file = file_storage and file_storage.filename and _ext_ok(file_storage.filename, ALLOWED_TECH_PHOTO_EXT)
    try:
        if not has_file:
            raise ValueError('صورة التوقيع مطلوبة')
        row = upsert_signatory(
            name=name,
            national_id=national_id,
            role=role,
            pin_plain=pin,
            pin_hash_fn=hash_password,
            image_bytes=file_storage.read(),
            app_root=app.root_path,
            secret=app.config['SECRET_KEY'],
        )
        nid_norm = normalize_national_id(national_id)
        for candidate in tenant_query(Technician).filter(Technician.national_id.isnot(None)):
            if normalize_national_id(candidate.national_id) == nid_norm:
                row.technician_id = candidate.id
                candidate.signature_path = row.signature_path
                candidate.sign_pin_hash = row.sign_pin_hash
                break
        db.session.commit()
        session['settings_notice'] = 'تم حفظ التوقيع بنجاح.'
    except ValueError as exc:
        db.session.rollback()
        session['settings_notice'] = str(exc)
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('settings_signatory_add failed')
        msg = str(exc) or 'تعذّر حفظ التوقيع'
        session['settings_notice'] = msg
    return _settings_redirect('signatures')


@app.route('/settings/signatories/<int:sig_id>/delete', methods=['POST'])
def settings_signatory_delete(sig_id):
    err = enforce_admin_delete()
    if err:
        return err
    from signatory_service import delete_signatory_files

    row = tenant_get_or_404(Signatory, sig_id)
    delete_signatory_files(app.root_path, row)
    row.is_active = False
    row.signature_path = None
    db.session.commit()
    session['settings_notice'] = 'تم حذف الموقّع.'
    return _settings_redirect('signatures')


@app.route('/settings/signatures/save', methods=['POST'])
def settings_signatures_prefs():
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة.'
        return _settings_redirect('signatures')
    s = get_app_settings()
    sign_method = (request.form.get('default_sign_method') or 'pin').strip()
    if sign_method not in ('draw', 'pin', 'both'):
        sign_method = 'pin'
    s.default_sign_method = sign_method
    db.session.commit()
    session['settings_notice'] = 'تم حفظ إعدادات التوقيع.'
    return _settings_redirect('signatures')


@app.route('/settings/screensaver/save', methods=['POST'])
def settings_screensaver_save():
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة.'
        return _settings_redirect('screensaver')
    s = get_app_settings()
    s.idle_screensaver_enabled = request.form.get('idle_screensaver_enabled') == '1'
    try:
        sec = int(request.form.get('idle_screensaver_seconds') or 60)
    except (TypeError, ValueError):
        sec = 60
    s.idle_screensaver_seconds = max(15, min(sec, 3600))
    db.session.commit()
    session['settings_notice'] = 'تم حفظ إعدادات شاشة الحفظ.'
    return _settings_redirect('screensaver')


@app.route('/settings/azkar/save', methods=['POST'])
def settings_azkar_save():
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة.'
        return _settings_redirect('appearance')
    s = get_app_settings()
    s.azkar_ticker_enabled = request.form.get('azkar_ticker_enabled') == '1'
    db.session.commit()
    session['settings_notice'] = 'تم حفظ إعدادات شريط الأذكار.'
    return _settings_redirect('appearance')


@app.route('/settings/billing/checkout', methods=['POST'])
def settings_billing_checkout():
    """إنشاء فاتورة Moyasar لتجديد اشتراك المؤسسة الحالية."""
    user = require_admin()
    if not user:
        session['settings_notice'] = 'صلاحية المدير مطلوبة لتجديد الاشتراك.'
        return _settings_redirect('plan')
    from moyasar_payments import create_subscription_invoice, moyasar_enabled
    from models import Organization
    from tenant_scope import effective_organization_id

    if not moyasar_enabled():
        session['settings_notice'] = 'بوابة الدفع غير مفعّلة حالياً. تواصل مع دعم LiftCore أو ادفع يدوياً.'
        return _settings_redirect('plan')

    oid = effective_organization_id()
    org = db.session.get(Organization, oid) if oid else None
    if not org:
        session['settings_notice'] = 'المؤسسة غير معروفة.'
        return _settings_redirect('plan')

    # استخدم أصل الطلب كـ success/back حتى يعود للـ subdomain الصحيح
    callback_base = request.url_root.rstrip('/')
    result = create_subscription_invoice(org, callback_base=callback_base)
    if not result.get('ok'):
        session['settings_notice'] = (result.get('errors') or ['تعذّر إنشاء رابط الدفع'])[0]
        return _settings_redirect('plan')
    return redirect(result['url'])


@app.route('/api/webhooks/moyasar', methods=['POST'])
def moyasar_webhook():
    """Webhook عام من Moyasar — بدون CSRF وبدون tenant."""
    from moyasar_payments import apply_moyasar_payment_event

    payload = request.get_json(silent=True)
    if payload is None:
        # بعض الإشعارات تصل كـ form
        raw = request.get_data(as_text=True) or ''
        try:
            import json as _json
            payload = _json.loads(raw) if raw else {}
        except Exception:
            payload = dict(request.form) if request.form else {}
    result = apply_moyasar_payment_event(payload or {})
    code = 200 if result.get('ok') else 400
    return jsonify(result), code


@app.route('/settings/zatca/save', methods=['POST'])
def settings_zatca_save():
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة لإعداد الفوترة الإلكترونية.'
        return _settings_redirect('zatca')
    from zatca_phase2 import save_zatca_credentials_form
    err = save_zatca_credentials_form(request.form)
    if err:
        session['settings_notice'] = err
        return _settings_redirect('zatca')
    session['settings_notice'] = 'تم حفظ إعدادات الفوترة الإلكترونية.'
    return _settings_redirect('zatca', saved=1)


@app.route('/settings/save', methods=['POST'])
def settings_save():
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة لتعديل بيانات الشركة.'
        return _settings_redirect('company')
    s = get_app_settings()
    s.company_name    = request.form.get('company_name', '')
    s.company_name_en = request.form.get('company_name_en', '')
    s.phone           = request.form.get('phone', '')
    s.whatsapp_phone  = request.form.get('whatsapp_phone', '') or '0555076078'
    s.whatsapp_receive_mode = 'office'
    s.email           = request.form.get('email', '')
    s.address         = request.form.get('address', '')
    s.address_en      = request.form.get('address_en', '')
    s.city            = request.form.get('city', '')
    s.rep_name        = request.form.get('rep_name', '')
    s.rep_mobile      = request.form.get('rep_mobile', '')
    s.cr_number       = request.form.get('cr_number', '')
    s.vat_number      = request.form.get('vat_number', '')
    s.company_website = request.form.get('company_website', '')
    s.bank_name       = request.form.get('bank_name', '')
    s.bank_account_name = request.form.get('bank_account_name', '')
    s.bank_iban       = request.form.get('bank_iban', '')
    s.bank_account_no = request.form.get('bank_account_no', '')
    try:
        s.tax_pct = float(request.form.get('tax_pct', 15))
    except ValueError:
        s.tax_pct = 15
    s.currency        = request.form.get('currency', 'SAR')
    s.language        = request.form.get('language', 'ar')
    from work_calendar import COUNTRY_OPTIONS, DEFAULT_WEEKDAYS_BY_COUNTRY
    import json as _json
    import re as _re

    country = (request.form.get('work_country') or 'SA').strip().upper()[:2]
    if country not in dict(COUNTRY_OPTIONS):
        country = 'SA'
    s.work_country = country
    selected_weekdays = []
    for w in range(7):
        if request.form.get(f'work_weekday_{w}'):
            selected_weekdays.append(w)
    if not selected_weekdays:
        selected_weekdays = list(DEFAULT_WEEKDAYS_BY_COUNTRY.get(country, DEFAULT_WEEKDAYS_BY_COUNTRY['SA']))
    s.work_weekdays_json = _json.dumps(sorted(set(selected_weekdays)))
    s.work_hours_start = (request.form.get('work_hours_start') or '08:00')[:5]
    s.work_hours_end = (request.form.get('work_hours_end') or '17:00')[:5]
    s.respect_public_holidays = request.form.get('respect_public_holidays') == '1'

    def _dates_from_textarea(name: str) -> list[str]:
        raw = request.form.get(name, '') or ''
        out: list[str] = []
        for line in raw.replace(',', '\n').splitlines():
            line = line.strip()
            if _re.fullmatch(r'\d{4}-\d{2}-\d{2}', line):
                out.append(line)
        return sorted(set(out))

    s.custom_holidays_json = _json.dumps(_dates_from_textarea('custom_holidays'))
    s.extra_work_days_json = _json.dumps(_dates_from_textarea('extra_work_days'))
    s.logo_width_sidebar = _clamp_logo_width(request.form.get('logo_width_sidebar'), 150)
    s.logo_width_report  = _clamp_logo_width(request.form.get('logo_width_report'), 150)
    s.logo_width_login   = _clamp_logo_width(request.form.get('logo_width_login'), 180, min_w=80, max_w=500)
    s.company_stamp_width = _clamp_document_asset_value(
        request.form.get('company_stamp_width'), 110, 40, 300,
    )
    s.company_stamp_offset_x = _clamp_document_asset_value(
        request.form.get('company_stamp_offset_x'), 0,
    )
    s.company_stamp_offset_y = _clamp_document_asset_value(
        request.form.get('company_stamp_offset_y'), 0,
    )
    s.company_sign_width = _clamp_document_asset_value(
        request.form.get('company_sign_width'), 140, 40, 320,
    )
    s.company_sign_offset_x = _clamp_document_asset_value(
        request.form.get('company_sign_offset_x'), 0,
    )
    s.company_sign_offset_y = _clamp_document_asset_value(
        request.form.get('company_sign_offset_y'), 0,
    )
    logo_ok, logo_msg = _save_company_logo(s, request.files.get('logo'))
    stamp_ok, stamp_msg = _save_company_image_asset(
        s, request.files.get('company_stamp'),
        attr_name='company_stamp_path', prefix='stamp', label_ar='ختم الشركة',
    )
    sign_ok, sign_msg = _save_company_image_asset(
        s, request.files.get('company_sign'),
        attr_name='company_sign_path', prefix='sign', label_ar='توقيع الشركة',
    )
    from zatca_phase2 import sync_zatca_credentials_from_settings
    sync_zatca_credentials_from_settings(s)
    db.session.commit()
    notices = []
    if not logo_ok:
        notices.append(logo_msg or 'تعذّر حفظ الشعار.')
    elif logo_msg:
        notices.append(logo_msg)
    if not stamp_ok:
        notices.append(stamp_msg or 'تعذّر حفظ الختم.')
    elif stamp_msg:
        notices.append(stamp_msg)
    if not sign_ok:
        notices.append(sign_msg or 'تعذّر حفظ التوقيع.')
    elif sign_msg:
        notices.append(sign_msg)
    if not notices:
        session['settings_notice'] = 'تم حفظ بيانات الشركة بنجاح.'
    elif logo_ok and stamp_ok and sign_ok:
        session['settings_notice'] = 'تم حفظ بيانات الشركة. ' + ' '.join(notices)
    else:
        session['settings_notice'] = ' '.join(notices)
    return _settings_redirect('company', saved=1)


def _save_user_photo(user, file_storage):
    if not file_storage or not file_storage.filename:
        return
    if not _ext_ok(file_storage.filename, ALLOWED_TECH_PHOTO_EXT):
        return
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    folder = os.path.join(USER_UPLOAD_ROOT, str(user.id))
    os.makedirs(folder, exist_ok=True)
    for old in os.listdir(folder):
        if old.startswith('avatar.'):
            try:
                os.remove(os.path.join(folder, old))
            except OSError:
                pass
    filename = f'avatar.{ext}'
    file_storage.save(os.path.join(folder, filename))
    user.photo_path = f'uploads/users/{user.id}/{filename}'


def _apply_username_change(user, new_username):
    """تحديث اسم المستخدم مع التحقق من التفرد."""
    new_username = (new_username or '').strip()
    if not new_username:
        return 'اسم المستخدم مطلوب.'
    if new_username == user.username:
        return None
    taken = tenant_query(User).filter(
        User.username == new_username,
        User.id != user.id,
    ).first()
    if taken:
        return f'اسم المستخدم «{new_username}» مستخدم مسبقاً.'
    user.username = new_username
    return None


@app.route('/settings/profile', methods=['POST'])
def settings_profile_save():
    user = require_login()
    if not user:
        return redirect(url_for('login'))
    username_err = _apply_username_change(user, request.form.get('username'))
    if username_err:
        session['settings_notice'] = username_err
        return _settings_redirect('account')
    user.full_name = (request.form.get('full_name') or '').strip() or user.username
    user.email = (request.form.get('email') or '').strip()
    _save_user_photo(user, request.files.get('photo'))
    db.session.commit()
    session['settings_notice'] = 'تم تحديث بيانات حسابك.'
    return _settings_redirect('account')


@app.route('/settings/theme', methods=['POST'])
def settings_theme_save():
    user = require_login()
    if not user:
        return redirect(url_for('login'))
    theme = normalize_user_theme(request.form.get('theme'))
    user.theme = theme
    db.session.commit()
    session['settings_notice'] = 'تم حفظ المظهر.'
    return _settings_redirect('appearance')


@app.route('/api/user/language', methods=['POST'])
def api_user_language():
    user = require_login()
    if not user:
        return jsonify({'ok': False, 'error': 'auth'}), 401
    data = request.get_json(silent=True) or {}
    lang = (data.get('lang') or request.form.get('lang') or 'ar').strip()
    if lang not in ('ar', 'en'):
        lang = 'ar'
    user.language = lang
    session['lang'] = lang
    db.session.commit()
    return jsonify({'ok': True, 'lang': lang})


@app.route('/api/session/lock', methods=['POST'])
def api_session_lock():
    user = require_login()
    if not user:
        return jsonify({'ok': False, 'error': 'auth'}), 401
    set_session_locked(True)
    return jsonify({'ok': True, 'locked': True})


@app.route('/api/session/unlock', methods=['POST'])
def api_session_unlock():
    user = require_login()
    if not user:
        return jsonify({'ok': False, 'error': 'auth'}), 401
    if not user.is_active:
        return jsonify({'ok': False, 'error': 'inactive'}), 403
    data = request.get_json(silent=True) or {}
    password = data.get('password') or request.form.get('password') or ''
    if not verify_password(user.password_hash, password):
        return jsonify({'ok': False, 'error': 'wrong_password'}), 401
    set_session_locked(False)
    return jsonify({'ok': True, 'locked': False})


@app.route('/api/user/theme', methods=['POST'])
def api_user_theme():
    user = require_login()
    if not user:
        return jsonify({'ok': False, 'error': 'auth'}), 401
    data = request.get_json(silent=True) or {}
    theme = normalize_user_theme(data.get('theme') or request.form.get('theme'))
    user.theme = theme
    db.session.commit()
    return jsonify({'ok': True, 'theme': theme})


@app.route('/settings/users/add', methods=['POST'])
def settings_user_add():
    admin = require_admin()
    if not admin:
        return redirect(url_for('login'))

    from entitlements import assert_capacity
    cap = assert_capacity('office_users')
    if not cap.get('ok'):
        session['settings_notice'] = cap.get('error') or 'تجاوزت حد المستخدمين في الباقة.'
        return _settings_redirect('users')

    username = (request.form.get('username') or '').strip()
    full_name = (request.form.get('full_name') or '').strip()
    email = (request.form.get('email') or '').strip()
    role = (request.form.get('role') or 'viewer').strip()
    password = (request.form.get('password') or '').strip()
    auto_generate = request.form.get('auto_generate') == '1'

    if not username:
        session['settings_notice'] = 'اسم المستخدم مطلوب.'
        return _settings_redirect('users')

    if tenant_query(User).filter_by(username=username).first():
        session['settings_notice'] = f'اسم المستخدم «{username}» مستخدم مسبقاً.'
        return _settings_redirect('users')

    if role not in ('admin', 'manager', 'viewer', 'custom'):
        role = 'viewer'

    if auto_generate or not password:
        password = generate_password()
        session['settings_generated_username'] = username
        session['settings_generated_password'] = password

    user = User(
        username=username,
        password_hash=hash_password(password),
        full_name=full_name or username,
        email=email,
        role=role,
        is_active=True,
    )
    from liftcore_permissions import dump_permissions_extra, permissions_grants_from_form

    if role == 'custom':
        user.permissions_extra = dump_permissions_extra(permissions_grants_from_form(request.form))
    else:
        user.permissions_extra = None
    assign_organization(user)
    db.session.add(user)
    db.session.commit()
    session['settings_notice'] = f'تم إنشاء المستخدم «{username}» بنجاح.'
    return _settings_redirect('users')


@app.route('/settings/users/edit/<int:user_id>', methods=['POST'])
def settings_user_edit(user_id):
    admin = require_admin()
    if not admin:
        return redirect(url_for('login'))
    target = tenant_get_or_404(User, user_id)
    username_err = _apply_username_change(target, request.form.get('username'))
    if username_err:
        session['settings_notice'] = username_err
        return _settings_redirect('users', edit_user=target.id)
    full_name = (request.form.get('full_name') or '').strip()
    email = (request.form.get('email') or '').strip()
    role = (request.form.get('role') or target.role).strip()
    if role not in ('admin', 'manager', 'viewer', 'custom'):
        role = target.role
    if target.id == admin.id and role != 'admin':
        session['settings_notice'] = 'لا يمكنك تغيير دورك من مدير النظام.'
        return _settings_redirect('users', edit_user=target.id)
    target.full_name = full_name or target.username
    target.email = email
    target.role = role
    new_pass = (request.form.get('new_password') or '').strip()
    if new_pass:
        if len(new_pass) < 6:
            session['settings_notice'] = 'كلمة المرور يجب أن تكون 6 أحرف على الأقل.'
            return _settings_redirect('users', edit_user=target.id)
        target.password_hash = hash_password(new_pass)
        bump_user_session_version(target)  # يُنهي جلسات ذلك المستخدم فوراً
        session['settings_generated_username'] = target.username
        session['settings_generated_password'] = new_pass
    from liftcore_permissions import dump_permissions_extra, permissions_grants_from_form

    if role == 'custom':
        target.permissions_extra = dump_permissions_extra(permissions_grants_from_form(request.form))
    else:
        target.permissions_extra = None
    db.session.commit()
    session['settings_notice'] = f'تم تحديث المستخدم «{target.username}».'
    return _settings_redirect('users')


@app.route('/settings/users/toggle/<int:user_id>', methods=['POST'])
def settings_user_toggle(user_id):
    admin = require_admin()
    if not admin:
        return redirect(url_for('login'))
    target = tenant_get_or_404(User, user_id)
    if target.id == admin.id:
        session['settings_notice'] = 'لا يمكنك تعطيل حسابك.'
        return _settings_redirect('users')
    target.is_active = not target.is_active
    db.session.commit()
    state = 'تفعيل' if target.is_active else 'تعطيل'
    session['settings_notice'] = f'تم {state} المستخدم «{target.username}».'
    return _settings_redirect('users')


@app.route('/settings/password', methods=['POST'])
def settings_change_password():
    from liftcore_security import password_policy_error

    user = require_login()
    if not user:
        return redirect(url_for('login'))

    current = request.form.get('current_password') or ''
    new_pass = (request.form.get('new_password') or '').strip()
    confirm = (request.form.get('confirm_password') or '').strip()
    lang = resolve_user_language(user)

    if not verify_password(user.password_hash, current):
        session['settings_notice'] = 'كلمة المرور الحالية غير صحيحة.'
        return _settings_redirect('account')

    policy_err = password_policy_error(new_pass, lang=lang)
    if policy_err:
        session['settings_notice'] = policy_err
        return _settings_redirect('account')

    if new_pass != confirm:
        session['settings_notice'] = 'تأكيد كلمة المرور غير متطابق.'
        return _settings_redirect('account')

    user.password_hash = hash_password(new_pass)
    user.must_change_password = False
    bump_user_session_version(user, bind_current_session=True)
    db.session.commit()
    from audit_log import log_audit
    log_audit('password_changed', user=user)
    session['settings_notice'] = 'تم تغيير كلمة المرور بنجاح.'
    return _settings_redirect('account')

# =============================================
# API للداشبورد (بيانات حقيقية)
# =============================================
@app.route('/api/dashboard')
def api_dashboard():
    from sqlalchemy import extract, case, func
    year = int(request.args.get('year', datetime.now().year))
    today = date.today()
    in_60_days = today + timedelta(days=60)

    monthly_rev = _monthly_aggregate(year, Revenue.revenue_date, Revenue.total)
    monthly_exp = _monthly_aggregate(year, Expense.expense_date, Expense.amount)
    monthly_visits = _monthly_aggregate(year, MaintenanceVisit.visit_date)
    monthly_faults = _monthly_aggregate(year, Fault.reported_at)

    stats, alerts = get_dashboard_stats()
    trends = get_dashboard_trends()

    revenue_by_type = {}
    for row in db.session.query(
        Revenue.revenue_type,
        db.func.sum(Revenue.total),
    ).filter(
        extract('year', Revenue.revenue_date) == year,
    ).group_by(Revenue.revenue_type).all():
        label = row[0] or 'أخرى'
        revenue_by_type[label] = round(row[1] or 0, 2)

    expense_by_type = {}
    for row in db.session.query(
        Expense.expense_type,
        db.func.sum(Expense.amount),
    ).filter(
        extract('year', Expense.expense_date) == year,
    ).group_by(Expense.expense_type).all():
        label = row[0] or 'أخرى'
        expense_by_type[label] = round(row[1] or 0, 2)

    top_clients_raw = db.session.query(
        Customer,
        func.coalesce(func.sum(Revenue.total), 0).label('total_rev'),
    ).outerjoin(
        Revenue,
        db.and_(
            Revenue.customer_id == Customer.id,
            extract('year', Revenue.revenue_date) == year,
        ),
    ).group_by(Customer.id).order_by(db.desc('total_rev')).limit(5).all()

    top_clients = []
    for cust, total_rev in top_clients_raw:
        top_clients.append({
            'name': cust.name,
            'city': cust.city or '',
            'elevators': len(cust.elevators),
            'contracts': len(cust.contracts),
            'revenue': round(total_rev or 0, 2),
            'status': cust.status or '',
        })

    expiring_list = tenant_query(Contract).filter(
        Contract.end_date >= today,
        Contract.end_date <= in_60_days,
    ).order_by(Contract.end_date).limit(15).all()

    expiring_contracts_rows = []
    for c in expiring_list:
        days_left = (c.end_date - today).days if c.end_date else 0
        expiring_contracts_rows.append({
            'code': c.code,
            'customer': c.customer.name if c.customer else '—',
            'end_date': str(c.end_date or ''),
            'days_left': days_left,
            'value': c.total or c.value or 0,
            'inv_status': c.invoice_status or '—',
        })

    down_elevators = tenant_query(Elevator).filter(
        Elevator.status.in_(['متوقف', 'خارج الخدمة']),
    ).order_by(Elevator.code).limit(20).all()

    down_elevators_rows = []
    for e in down_elevators:
        last_visit = tenant_query(MaintenanceVisit).filter_by(
            elevator_id=e.id,
        ).order_by(MaintenanceVisit.visit_date.desc()).first()
        tech_name = '—'
        if last_visit and last_visit.technician:
            tech_name = last_visit.technician.name
        elif e.faults:
            last_fault = sorted(e.faults, key=lambda f: f.reported_at or datetime.min, reverse=True)[0]
            if last_fault.technician:
                tech_name = last_fault.technician.name
        down_elevators_rows.append({
            'code': e.code,
            'customer': e.customer.name if e.customer else '—',
            'elev_type': e.elev_type or '—',
            'status': e.status,
            'last_maint': str(e.last_maintenance or '—'),
            'technician': tech_name,
        })

    tech_visit_rows = db.session.query(
        Technician.name,
        db.func.count(MaintenanceVisit.id),
    ).join(
        MaintenanceVisit, MaintenanceVisit.technician_id == Technician.id,
    ).filter(
        extract('year', MaintenanceVisit.visit_date) == year,
    ).group_by(Technician.id).order_by(db.desc(db.func.count(MaintenanceVisit.id))).limit(8).all()

    tech_visits = [{'name': n, 'count': c} for n, c in tech_visit_rows]

    tech_fault_rows = db.session.query(
        Technician.name,
        db.func.count(Fault.id),
        db.func.sum(case(
            (Fault.status.in_(['تم الاصلاح', 'مغلق']), 1),
            else_=0,
        )),
    ).join(
        Fault, Fault.technician_id == Technician.id,
    ).filter(
        extract('year', Fault.reported_at) == year,
    ).group_by(Technician.id).order_by(db.desc(db.func.count(Fault.id))).limit(8).all()

    tech_fault_rates = []
    for name, total, resolved in tech_fault_rows:
        total = total or 0
        resolved = resolved or 0
        tech_fault_rates.append({
            'name': name,
            'rate': round(resolved / total * 100) if total else 0,
            'total': total,
        })

    elev_status = {label: 0 for label in ('نشط', 'تحت الصيانة', 'متوقف', 'خارج الخدمة')}
    for status, cnt in db.session.query(
        Elevator.status, func.count(Elevator.id),
    ).group_by(Elevator.status).all():
        if status in elev_status:
            elev_status[status] = int(cnt or 0)

    contract_status = {
        label: 0
        for label in ('نشط', 'على وشك الانتهاء', 'تم تجديده', 'منتهي', 'ملغي')
    }

    all_c = tenant_query(Contract).all()
    renewed_ids = _annotate_contract_renewals(all_c)
    for c in all_c:
        label = contract_display_status(c, renewed_ids=renewed_ids)
        if label in contract_status:
            contract_status[label] += 1

    return jsonify({
        'customers':          stats['customers'],
        'elevators':          stats['elevators'],
        'contracts':          stats['contracts'],
        'expired_contracts':  stats['expired_contracts'],
        'visits_today':       stats['visits_today'],
        'technicians':        stats['technicians'],
        'revenue':            stats['revenue'],
        'expenses':           round(db.session.query(db.func.sum(Expense.amount)).scalar() or 0, 2),
        'faults_open':        stats['faults_open'],
        'visits_done':        stats['visits_done'],
        'unpaid_invoices':    stats['unpaid_invoices'],
        'outstanding_collectible': stats.get('outstanding_collectible', 0),
        'outstanding_count':  stats.get('outstanding_count', 0),
        'parts_profit':       stats['parts_profit'],
        'trends':             trends,
        'expiring_contracts': alerts['expiring_contracts_count'],
        'low_stock':          alerts['low_stock_count'],
        'monthly_revenue': monthly_rev,
        'monthly_expenses': monthly_exp,
        'monthly_visits': monthly_visits,
        'monthly_faults': monthly_faults,
        'revenue_by_type': revenue_by_type,
        'expense_by_type': expense_by_type,
        'top_clients': top_clients,
        'expiring_contracts_list': expiring_contracts_rows,
        'down_elevators': down_elevators_rows,
        'tech_visits': tech_visits,
        'tech_fault_rates': tech_fault_rates,
        'elev_status': elev_status,
        'contract_status': contract_status,
    })
# =============================================
# أضف هذه الـ routes في app.py
# تحت قسم التقارير الموجود
# =============================================

@app.route('/api/reports/clients')
def api_report_clients():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-clients', _report_ctx()))


@app.route('/api/reports/elevators')
def api_report_elevators():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-elevators', _report_ctx()))


@app.route('/api/reports/contracts')
def api_report_contracts():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-contracts', _report_ctx()))


@app.route('/api/reports/technicians')
def api_report_technicians():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-technicians', _report_ctx()))


@app.route('/api/reports/visits')
def api_report_visits():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-maintenance', _report_ctx()))


@app.route('/api/reports/faults')
def api_report_faults():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-faults', _report_ctx()))


@app.route('/api/reports/revenues')
def api_report_revenues():
    from report_data import get_report_revenues
    year = request.args.get('year', datetime.now().year)
    month = request.args.get('month', '') or None
    return jsonify(get_report_revenues(db, Revenue, year=year, month=month))


@app.route('/api/reports/expenses')
def api_report_expenses():
    from report_data import get_report_expenses
    year = request.args.get('year', datetime.now().year)
    month = request.args.get('month', '') or None
    return jsonify(get_report_expenses(db, Expense, year=year, month=month))


@app.route('/api/reports/invoices')
def api_report_invoices():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-invoices', _report_ctx()))


@app.route('/api/reports/parts-billing')
def api_report_parts_billing():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-parts', _report_ctx()))


@app.route('/api/reports/inventory')
def api_report_inventory():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-inventory', _report_ctx()))


@app.route('/api/reports/stock')
def api_report_stock():
    from report_data import fetch_report_rows
    return jsonify(fetch_report_rows('report-stock', _report_ctx()))



@app.route('/api/reports/financial')
def api_report_financial():
    from report_data import get_financial_report, _parse_report_date
    today = date.today()
    date_from = _parse_report_date(request.args.get('date_from')) or date(today.year, 1, 1)
    date_to = _parse_report_date(request.args.get('date_to')) or today
    return jsonify(get_financial_report(db, Revenue, Expense, date_from=date_from, date_to=date_to))


@app.route('/api/reports/contract-cost-allocation')
def api_report_contract_cost_allocation():
    from report_data import get_contract_cost_allocation_report, _parse_report_date
    today = date.today()
    date_from = _parse_report_date(request.args.get('date_from')) or date(today.year, 1, 1)
    date_to = _parse_report_date(request.args.get('date_to')) or today
    return jsonify(get_contract_cost_allocation_report(
        Contract, MaintenanceVisit,
        date_from=date_from,
        date_to=date_to,
        contract_status_fn=contract_display_status,
    ))


@app.route('/api/reports/contract-forecast')
def api_report_contract_forecast():
    from report_data import get_contract_renewal_forecast, get_contract_renewal_overview
    today = date.today()
    year = int(request.args.get('year', today.year))
    month = int(request.args.get('month', today.month))
    months_ahead = int(request.args.get('months_ahead', 12))
    forecast = get_contract_renewal_forecast(
        Contract, Revenue, year, month, contract_status_fn=contract_display_status,
    )
    forecast['overview'] = get_contract_renewal_overview(
        Contract, Revenue, months_ahead=months_ahead,
        contract_status_fn=contract_display_status,
    )
    return jsonify(forecast)


@app.route('/api/reports/financial-health')
def api_report_financial_health():
    from report_data import get_financial_health_report
    year = int(request.args.get('year', date.today().year))
    return jsonify(get_financial_health_report(
        db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit,
        year=year, contract_status_fn=contract_display_status,
    ))


@app.route('/api/reports/client-annual/<int:customer_id>')
def api_client_annual(customer_id):
    """التقرير الختامي لعقد صيانة — يُفلتر برقم العقد وفترة التعاقد فقط."""
    from sqlalchemy import and_, or_

    c = tenant_get_or_404(Customer, customer_id)
    contract_id = request.args.get('contract_id', type=int)
    year_raw = (request.args.get('year') or '').strip()
    year = None
    if year_raw:
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            return jsonify({'error': 'سنة غير صالحة'}), 400

    all_contracts = (
        tenant_query(Contract)
        .filter_by(customer_id=customer_id)
        .order_by(Contract.start_date.desc(), Contract.id.desc())
        .all()
    )

    def _contract_row(ct):
        return {
            'id': ct.id,
            'code': ct.code,
            'type': ct.contract_type or '',
            'start': str(ct.start_date or ''),
            'end': str(ct.end_date or ''),
            'total': ct.total or 0,
            'status': contract_display_status(ct),
            'visits_planned': int(ct.visits_per_month or 0),
        }

    if year:
        period_start = date(year, 1, 1)
        period_end = date(year, 12, 31)
        contracts_for_year = [
            ct for ct in all_contracts
            if ct.start_date and ct.end_date
            and ct.start_date <= period_end
            and ct.end_date >= period_start
        ]
    else:
        contracts_for_year = all_contracts

    contracts_payload = [_contract_row(ct) for ct in contracts_for_year]

    # بدون عقد محدد: أعد قائمة العقود فقط لاختيار فترة التعاقد
    if not contract_id:
        return jsonify({
            'customer': {
                'code': c.code,
                'name': c.name,
                'city': c.city or '',
                'address': c.address or '',
                'phone': c.phone or '',
            },
            'contracts': contracts_payload,
            'needs_contract': True,
            'stats': None,
            'elevators': [],
            'visits': [],
            'faults': [],
            'parts': [],
        })

    ct = next((x for x in all_contracts if x.id == contract_id), None)
    if not ct:
        return jsonify({'error': 'العقد غير موجود لهذا العميل'}), 404

    start = ct.start_date
    end = ct.end_date
    if not start or not end:
        return jsonify({'error': 'العقد بلا تاريخ بداية/نهاية'}), 400

    elev_ids = [ce.elevator_id for ce in (ct.elevators or [])]
    elevators = (
        tenant_query(Elevator).filter(Elevator.id.in_(elev_ids)).all()
        if elev_ids else []
    )
    if elevators:
        from entity_links import sort_by_natural_code
        elevators = sort_by_natural_code(elevators)


    # الزيارات المرتبطة بالعقد وداخل فترة التعاقد
    visits_q = tenant_query(MaintenanceVisit).filter(
        MaintenanceVisit.visit_date >= start,
        MaintenanceVisit.visit_date <= end,
    )
    if elev_ids:
        visits_q = visits_q.filter(or_(
            MaintenanceVisit.contract_id == ct.id,
            and_(
                MaintenanceVisit.contract_id.is_(None),
                MaintenanceVisit.elevator_id.in_(elev_ids),
            ),
        ))
    else:
        visits_q = visits_q.filter(MaintenanceVisit.contract_id == ct.id)
    visits = visits_q.all()
    if visits:
        from entity_links import natural_code_key
        visits = sorted(
            visits,
            key=lambda v: (
                v.visit_date or date.min,
                natural_code_key(v.elevator.code if v.elevator else ''),
                v.id or 0,
            ),
        )

    # الأعطال على مصاعد العقد داخل فترة التعاقد
    faults = []
    if elev_ids:
        faults = (
            tenant_query(Fault)
            .filter(
                Fault.elevator_id.in_(elev_ids),
                Fault.reported_at.isnot(None),
                Fault.reported_at >= datetime.combine(start, datetime.min.time()),
                Fault.reported_at <= datetime.combine(end, datetime.max.time()),
            )
            .order_by(Fault.reported_at.asc())
            .all()
        )

    revenues = (
        tenant_query(Revenue)
        .filter(
            Revenue.contract_id == ct.id,
            Revenue.revenue_date >= start,
            Revenue.revenue_date <= end,
        )
        .order_by(Revenue.revenue_date.asc())
        .all()
    )

    parts = (
        tenant_query(PartsBilling)
        .filter(
            PartsBilling.contract_id == ct.id,
            PartsBilling.billing_date >= start,
            PartsBilling.billing_date <= end,
        )
        .order_by(PartsBilling.billing_date.asc())
        .all()
    )

    planned_visits = int(ct.visits_per_month or 0)
    if planned_visits <= 0:
        # تقدير من المدة إن لم يُحفظ عدد الزيارات
        months = ct.duration_months or max(
            1,
            (end.year - start.year) * 12 + (end.month - start.month) + 1,
        )
        planned_visits = months
    done_visits = len([v for v in visits if (v.status or '') == 'مكتملة'])
    solved_faults = len([
        f for f in faults
        if (f.status or '') in ('تم الاصلاح', 'محلول', 'مغلق')
    ])

    return jsonify({
        'customer': {
            'code': c.code,
            'name': c.name,
            'city': c.city or '',
            'address': c.address or '',
            'phone': c.phone or '',
        },
        'contracts': contracts_payload,
        'contract': _contract_row(ct),
        'needs_contract': False,
        'elevators': [{
            'code': e.code,
            'type': e.elev_type or '',
            'brand': e.brand or '',
            'model': e.model or '',
            'capacity': (str(e.capacity_kg) + ' كجم') if e.capacity_kg else '',
        } for e in elevators],
        'stats': {
            'planned_visits': planned_visits,
            'done_visits': done_visits,
            'compliance': round(done_visits / planned_visits * 100) if planned_visits else 0,
            'total_faults': len(faults),
            'solved_faults': solved_faults,
            'fault_rate': round(solved_faults / len(faults) * 100) if faults else 100,
            'total_revenue': sum(float(r.total or 0) for r in revenues),
        },
        'visits': [{
            'date': str(v.visit_date or ''),
            'tech': v.technician.name if v.technician else '—',
            'type': v.visit_type or '',
            'works': v.works_done or '',
            'status': v.status,
            'code': v.code,
        } for v in visits],
        'faults': [{
            'type': f.fault_type or '',
            'date': str(f.reported_at.date() if f.reported_at else ''),
            'status': f.status,
        } for f in faults],
        'parts': [{
            'description': p.description or '',
            'quantity': 1,
            'date': str(p.billing_date or ''),
        } for p in parts],
    })
# =============================================
# موديول تركيب المصاعد
# =============================================
from installation import register_install_module
register_install_module(app)

from sales import register_sales_module
register_sales_module(app)


def _ensure_installation_project_routes(flask_app):
    """تسجيل مسارات المشاريع إذا كانت نسخة قديمة من blueprint لم تُحمَّل."""
    endpoints = {rule.endpoint for rule in flask_app.url_map.iter_rules()}
    if 'installation.projects_list' in endpoints:
        return
    from installation.routes import (
        projects_list,
        project_detail,
        project_quote,
        project_quote_save,
        quote_print,
    )

    flask_app.add_url_rule('/installation/projects', view_func=projects_list, endpoint='installation.projects_list')
    flask_app.add_url_rule('/installation/projects/<int:project_id>', view_func=project_detail, endpoint='installation.project_detail')
    flask_app.add_url_rule('/installation/projects/<int:project_id>/quote', view_func=project_quote, endpoint='installation.project_quote')
    flask_app.add_url_rule('/installation/projects/<int:project_id>/quote/save', view_func=project_quote_save, methods=['POST'], endpoint='installation.project_quote_save')
    flask_app.add_url_rule('/installation/quotes/<int:quotation_id>/print', view_func=quote_print, endpoint='installation.quote_print')


_ensure_installation_project_routes(app)

# =============================================
# تشغيل التطبيق
# =============================================
if __name__ == '__main__':
    _port = int(os.environ.get('PORT', '5000'))
    _debug = os.environ.get('FLASK_DEBUG', '').strip().lower() in ('1', 'true', 'yes')
    app.run(debug=_debug, port=_port)
