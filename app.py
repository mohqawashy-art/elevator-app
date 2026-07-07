"""
LiftCore — Flask Application
app.py
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, g, send_from_directory, abort
from models import db, Customer, Elevator, Contract, ContractElevator, Technician, TechnicianDocument
from models import MaintenanceVisit, Fault, Revenue, Expense, Invoice
from models import MaintenanceTeam
from models import VisitTechnician, FaultTechnician
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
import uuid
import shutil
import secrets
import string


def _load_env_file():
    """تحميل إعدادات المنصة — مرة واحدة لكل العملاء (LiftCore + جما + أي subdomain)."""
    paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
        '/etc/liftcore/platform.env',
    ]
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8') as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, val = line.partition('=')
                    key = key.strip().lstrip('\ufeff')
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'liftcore-secret-2025')
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

db.init_app(app)

# موديول تركيب المصاعد (جداول منفصلة)
import installation.models  # noqa: F401, E402
from installation.config import install_module_enabled

from flask_migrate import Migrate  # noqa: E402

migrate = Migrate(app, db)

PUBLIC_ENDPOINTS = frozenset({'login', 'logout', 'static', 'index', 'api_version', 'api_health', 'field_login', 'field_logout', 'field_manifest', 'field_service_worker', 'web_manifest', 'admin_service_worker'})
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
    return user


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


def enforce_admin_delete(*, json_response=False):
    """يتطلب دور admin + كلمة مرور المستخدم الحالي لتأكيد الحذف."""
    as_json = _admin_delete_wants_json(json_response=json_response)
    user = current_user()
    if not user:
        if as_json:
            from liftcore_api_i18n import api_json_error
            return api_json_error('login_required', 401)
        return redirect(url_for('login'))
    if user.role != 'admin':
        msg = 'الحذف متاح للمسؤول فقط.'
        if as_json:
            from liftcore_api_i18n import api_json_error
            return api_json_error('admin_required', 403, message_ar=msg, message_en='Delete is admin-only.')
        flash(msg, 'error')
        abort(403)
    pwd = _admin_delete_password_from_request()
    if not pwd or not verify_password(user.password_hash, pwd):
        msg = 'كلمة المرور غير صحيحة — لم يتم الحذف.'
        if as_json:
            from liftcore_api_i18n import api_json_error
            return api_json_error('invalid_password', 403, message_ar=msg, message_en='Incorrect password — delete cancelled.')
        flash(msg, 'error')
        return redirect(request.referrer or url_for('dashboard'))
    from audit_log import log_audit
    log_audit(
        'admin_delete_confirmed',
        user=user,
        details={'path': request.path, 'endpoint': request.endpoint},
    )
    return None


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

    tech = Technician.query.get_or_404(tech_id)
    kind = technician_portal_kind(tech)
    has_faults = (
        Fault.query.filter(
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
            return None
        if path.startswith('/api/field'):
            return jsonify({'error': 'يجب تسجيل دخول الفني'}), 401
        return redirect(url_for('field_login', next=request.path))

    if field_tid and _field_tech_api_allowed(path, request.method):
        g.field_tech_id = field_tid
        return None

    user = current_user()
    if user:
        g.user = user
        lock_resp = _session_lock_response()
        if lock_resp:
            return lock_resp
        pwd_resp = _must_change_password_response(user)
        if pwd_resp:
            return pwd_resp
        from liftcore_rbac import check_rbac
        lang = resolve_user_language(user)
        s = None
        try:
            s = Settings.query.first()
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
        s = Settings.query.first()
    except Exception:
        db.session.rollback()
        s = None
    if not s:
        s = Settings()
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


def brand_logo_url(settings=None):
    s = settings or get_app_settings()
    if s and s.logo_path:
        rel = s.logo_path.replace('\\', '/')
        full = os.path.join(app.static_folder, rel.replace('/', os.sep))
        if os.path.isfile(full):
            return url_for('static', filename=rel)
    for name in ('logo.png', 'images/liftcore-brand-logo.png'):
        if os.path.isfile(os.path.join(app.static_folder, name.replace('/', os.sep))):
            return url_for('static', filename=name)
    return url_for('static', filename='logo.png')


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
        s = Settings.query.first()
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


@app.context_processor
def inject_global_template_vars():
    try:
        s = Settings.query.first()
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
    from liftcore_permissions import (
        effective_permissions,
        permission_groups_for_ui,
        user_can_write_module,
        user_has_permission,
    )
    user_perms = effective_permissions(user, s) if user else frozenset()
    return {
        'google_maps_api_key': resolve_google_maps_api_key(s),
        'google_maps_key_source': google_maps_key_source(s),
        'brand_logo_url': brand_logo_url(s),
        'liftcore_logo_url': liftcore_header_logo_url(s),
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
        'can_write': user_can_write_module(user, s) if user else False,
        'is_viewer': bool(user and user.role == 'viewer'),
        'user_permissions': user_perms,
        'permission_groups': permission_groups_for_ui(),
        'must_change_password': bool(user and getattr(user, 'must_change_password', False)),
    }


@app.template_global()
def has_perm(perm: str) -> bool:
    user = current_user()
    if not user:
        return False
    try:
        s = Settings.query.first()
    except Exception:
        db.session.rollback()
        s = None
    from liftcore_permissions import user_has_permission
    return user_has_permission(user, perm, s)


@app.template_global()
def csrf_token():
    from liftcore_security import ensure_csrf_token
    return ensure_csrf_token()


def _money_round(n):
    return round(float(n or 0), 2)


def _invoice_status_from_paid(contract, paid, today=None):
    """حالة الفاتورة من المبلغ المحصّل المخزّن (بدون إعادة حساب كامل)."""
    from customer_billing import UNPAID_INVOICE_STATUSES

    today = today or date.today()
    total = _money_round(contract.total or 0)
    paid = _money_round(paid)
    remaining = max(total - paid, 0)
    if total <= 0:
        return 'غير مدفوع'
    if remaining <= 0.01:
        return 'مدفوع'
    status = 'مدفوع جزئياً' if paid > 0 else 'غير مدفوع'
    overdue = Invoice.query.filter(
        Invoice.contract_id == contract.id,
        Invoice.due_date.isnot(None),
        Invoice.due_date < today,
        Invoice.status.in_(UNPAID_INVOICE_STATUSES),
    ).first()
    if overdue and remaining > 0.01:
        return 'متأخر'
    return status


def _refresh_contract_billing_cache(contract):
    """تحديث paid_amount و invoice_status لعقد واحد."""
    from billing_consistency import refresh_contract_cache

    refresh_contract_cache(contract)


def _backfill_contract_billing_cache():
    """ملء كاش الفوترة لجميع العقود (عند إضافة العمود أو الترقية)."""
    contracts = Contract.query.all()
    if not contracts:
        return
    app.logger.info('Backfilling contract billing cache (%d contracts)...', len(contracts))
    for c in contracts:
        _refresh_contract_billing_cache(c)
    db.session.commit()
    app.logger.info('Contract billing cache backfill complete.')


def contract_to_js_dict(c):
    """تسلسل عقد لـ JSON في الصفحة (بدون استعلامات إضافية)."""
    return {
        'id': c.id,
        'code': c.code,
        'customer_id': c.customer_id,
        'customer': c.customer.name if c.customer else '',
        'customer_name_en': (c.customer.name_en or '') if c.customer else '',
        'customer_city': (c.customer.city or '') if c.customer else '',
        'customer_lat': (c.customer.lat or '') if c.customer else '',
        'customer_lng': (c.customer.lng or '') if c.customer else '',
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
        'reminder_date': c.reminder_date.isoformat() if c.reminder_date else '',
        'city': c.city or '',
        'district': c.district or '',
        'address': c.address or '',
        'notes': c.notes or '',
        'file_url': upload_url(c.file_path),
        'file_name': contract_file_display_name(c.file_path),
    }


def contract_customer_js_dict(c):
    return {
        'id': c.id,
        'name': c.name,
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
    }


def client_to_js_dict(c):
    """تسلسل عميل لـ JSON (مع علاقات محمّلة مسبقاً)."""
    first_contract = c.contracts[0] if c.contracts else None
    return {
        'id': c.id,
        'code': c.code,
        'name': c.name,
        'name_en': c.name_en or '',
        'city': c.city or '',
        'district': c.district or '',
        'phone': c.phone or '',
        'phone2': c.phone2 or '',
        'email': c.email or '',
        'contact': c.contact_person or '',
        'role': c.contact_role or '',
        'entity_type': c.entity_type or 'فرد',
        'national_id': c.national_id or '',
        'cr_number': c.cr_number or '',
        'elevators': len(c.elevators),
        'fleet_status': customer_fleet_status(c),
        'contracts': len(c.contracts),
        'contract_status': contract_display_status(first_contract) if first_contract else 'بدون عقد',
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
        'notes': e.notes or '',
    }


def revenue_to_js_dict(r):
    return {
        'id': r.id,
        'code': r.code,
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
        'notes': r.notes or '',
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
                ('logo_width_sidebar', 'INTEGER'),
                ('logo_width_report', 'INTEGER'),
                ('logo_width_login', 'INTEGER'),
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
            ],
            'technicians': [
                ('team', 'VARCHAR(30)'),
                ('name_en', 'VARCHAR(100)'),
                ('signature_path', 'VARCHAR(300)'),
                ('sign_pin_hash', 'VARCHAR(200)'),
            ],
            'customers': [
                ('name_en', 'VARCHAR(200)'),
                ('entity_type', 'VARCHAR(20)'),
                ('cr_number', 'VARCHAR(50)'),
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
            ],
            'installation_leads': [
                ('customer_id', 'INTEGER'),
            ],
            'installation_timeline_steps': [
                ('started_at', 'DATETIME'),
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
    else:
        app.logger.info(
            'LiftCore DB backend=%s — Alembic migrations; skip SQLite legacy ALTER',
            database_backend(app.config.get('SQLALCHEMY_DATABASE_URI')),
        )
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
MAX_CONTRACT_FILE_BYTES = 10 * 1024 * 1024

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
    """تحقق من رقم جوال العميل — بدون 0 في البداية."""
    raw = re.sub(r'\D', '', phone or '')
    if not raw:
        return 'يرجى إدخال رقم الجوال'
    if raw.startswith('9660'):
        return 'لا تبدأ رقم الجوال بـ 0 — أدخل الرقم بدون الصفر (مثال: 512345678)'
    if raw.startswith('0') and not raw.startswith('00'):
        return 'لا تبدأ رقم الجوال بـ 0 — أدخل الرقم بدون الصفر (مثال: 512345678)'
    d = normalize_phone(phone)
    local = d[3:] if d.startswith('966') else d
    if len(local) < 9:
        return 'رقم الجوال غير مكتمل — أدخل 9 أرقام على الأقل'
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
    for c in Customer.query.all():
        if customer_id and c.id == customer_id:
            continue
        for p in (c.phone, c.phone2):
            if p and phone_key(p) == key:
                return True, f'رقم الجوال مستخدم للعميل «{c.name}» ({c.code})'
    for t in Technician.query.all():
        if technician_id and t.id == technician_id:
            continue
        for p in (t.phone, t.phone2):
            if p and phone_key(p) == key:
                return True, f'رقم الجوال مستخدم للفني «{t.name}» ({t.code})'
    return False, None


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
    import re

    max_num = 0
    pattern = re.compile(r'^' + re.escape(prefix) + r'(\d+)$')
    for row in model.query.with_entities(getattr(model, field)).all():
        code = row[0]
        if not code:
            continue
        m = pattern.match(str(code).strip())
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f'{prefix}{str(max_num + 1).zfill(digits)}'

# =============================================
# تسجيل الدخول
# =============================================
@app.route('/api/version')
def api_version():
    """تحقق سريع من إصدار الكود على السيرفر (بدون تسجيل دخول)."""
    root = app.root_path
    db_info = dict(database_info(app))
    try:
        db_info['customers'] = Customer.query.count()
        db_info['elevators'] = Elevator.query.count()
    except Exception:
        pass
    if db_info.get('backend') == 'sqlite':
        db_path = (db_info.get('path') or '').replace('/', os.sep)
        if db_path and os.path.isfile(db_path):
            db_info['file'] = os.path.basename(os.path.dirname(db_path)) + '/' + os.path.basename(db_path)
            db_info['bytes'] = os.path.getsize(db_path)
    return jsonify(
        version=APP_VERSION,
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


@app.route('/')
def index():
    if current_user():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


def _find_login_user(login_id):
    login_id = (login_id or '').strip()
    if not login_id:
        return None
    return User.query.filter(
        User.is_active.is_(True),
        or_(User.username == login_id, db.func.lower(User.email) == login_id.lower()),
    ).first()


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

    error = None
    if current_user():
        return redirect(url_for('dashboard'))
    if request.method == 'GET':
        ensure_csrf_token()
    if request.method == 'POST':
        allowed, retry_sec = check_login_rate_limit()
        if not allowed:
            error = f'محاولات كثيرة — انتظر {retry_sec} ثانية ثم حاول مجدداً.'
        else:
            login_id = request.form.get('email') or request.form.get('username')
            password = request.form.get('password') or ''
            user = _find_login_user(login_id)
            if user and verify_password(user.password_hash, password):
                if not password_is_hashed(user.password_hash):
                    user.password_hash = hash_password(password)
                if is_weak_password(password):
                    user.must_change_password = True
                session.clear()
                session['user_id'] = user.id
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
                clear_login_attempts()
                from audit_log import log_audit
                log_audit('login_success', user=user)
                session['just_logged_in'] = True
                if getattr(user, 'must_change_password', False):
                    session['settings_notice'] = 'يجب تغيير كلمة المرور قبل متابعة العمل.'
                    return redirect(url_for('settings', tab='account', force_password=1))
                return redirect(url_for('welcome'))
            record_login_failure()
            from audit_log import log_audit
            log_audit('login_failed', details={'login_id': (login_id or '')[:80]})
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
    return render_template('login.html', error=error)


@app.route('/welcome')
def welcome():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if not session.pop('just_logged_in', False):
        return redirect(url_for('dashboard'))
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
    q = model.query.filter(col >= start, col < end)
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
        return Contract.query.filter(
            Contract.end_date >= d1,
            Contract.end_date < d2,
        ).count()

    exp_this = expired_between(cur_start.date(), today + timedelta(days=1))
    exp_prev = expired_between(prev_start.date(), cur_start.date())

    def unpaid_created(start, end):
        return Invoice.query.filter(
            Invoice.created_at >= start,
            Invoice.created_at < end,
            Invoice.status.in_(_DASH_UNPAID_STATUSES),
        ).count()

    visits_today = MaintenanceVisit.query.filter_by(visit_date=today).count()
    visits_yesterday = MaintenanceVisit.query.filter_by(visit_date=yesterday).count()

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

    total_invoices = db.session.query(db.func.sum(Invoice.total)).scalar() or 0
    paid_invoices = db.session.query(db.func.sum(Invoice.total)).filter(
        Invoice.status.in_(['مدفوعة', 'مدفوع', 'محصّل'])
    ).scalar() or 0
    unpaid_total = db.session.query(db.func.sum(Invoice.total)).filter(
        Invoice.status.in_(['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً'])
    ).scalar() or 0
    overdue_total = db.session.query(db.func.sum(Invoice.total)).filter(
        Invoice.due_date < today,
        Invoice.status.in_(['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً'])
    ).scalar() or 0
    overdue_count = Invoice.query.filter(
        Invoice.due_date < today,
        Invoice.status.in_(['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً'])
    ).count()

    expiring_contracts = Contract.query.filter(
        Contract.status == 'نشط',
        Contract.end_date >= today,
        Contract.end_date <= in_30_days,
    ).order_by(Contract.end_date).all()

    low_stock_items = InventoryItem.query.filter(
        InventoryItem.min_qty > 0,
        InventoryItem.current_qty < InventoryItem.min_qty,
    ).order_by(InventoryItem.current_qty).all()

    stats = {
        'customers':        Customer.query.count(),
        'elevators':        Elevator.query.count(),
        'contracts':        Contract.query.filter_by(status='نشط').count(),
        'expired_contracts': Contract.query.filter(
            db.or_(Contract.status == 'منتهي', Contract.end_date < today)
        ).count(),
        'visits_today':     MaintenanceVisit.query.filter_by(visit_date=today).count(),
        'visits_done':      MaintenanceVisit.query.filter_by(status='مكتملة').count(),
        'faults_open':      Fault.query.filter(
            Fault.status.in_(['مفتوح', 'قيد المعالجة'])
        ).count(),
        'unpaid_invoices':  Invoice.query.filter(
            Invoice.status.in_(['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً'])
        ).count(),
        'technicians':      Technician.query.filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).count(),
        'revenue':          round(db.session.query(db.func.sum(Revenue.total)).scalar() or 0, 2),
        'parts_profit':     round(db.session.query(db.func.sum(PartsBilling.profit)).scalar() or 0, 2),
        'total_invoices':   round(total_invoices, 2),
        'paid_invoices':    round(paid_invoices, 2),
        'unpaid_total':     round(unpaid_total, 2),
        'overdue_total':    round(overdue_total, 2),
        'overdue_count':    overdue_count,
        'paid_pct':         round(paid_invoices / total_invoices * 100) if total_invoices else 0,
        'unpaid_pct':       round(unpaid_total / total_invoices * 100) if total_invoices else 0,
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
            for c in Customer.query.order_by(Customer.name).all()
        ]
        payload = {
            'title': 'إجمالي العملاء', 'link': '/clients',
            'columns': ['الكود', 'الاسم', 'المدينة', 'الحي', 'الهاتف', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'elevators':
        rows = [
            [e.code, e.customer.name, e.building_name or '—', e.elev_type or '—', e.brand or '—', e.status]
            for e in Elevator.query.join(Customer).order_by(Elevator.code).all()
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
            for c in Contract.query.filter_by(status='نشط').order_by(Contract.end_date).all()
        ]
        payload = {
            'title': 'العقود الفعّالة', 'link': '/contracts',
            'columns': ['الكود', 'العميل', 'النوع', 'البداية', 'النهاية', 'القيمة', 'الحالة'],
            'rows': rows,
        }
    elif card_type == 'expired_contracts':
        rows = [
            [c.code, c.customer.name, c.contract_type or '—',
             str(c.start_date), str(c.end_date), c.status]
            for c in Contract.query.filter(
                db.or_(Contract.status == 'منتهي', Contract.end_date < today)
            ).order_by(Contract.end_date.desc()).all()
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
            for v in MaintenanceVisit.query.filter_by(visit_date=today)
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
            for f in Fault.query.filter(Fault.status.in_(OPEN_FAULT_STATUSES))
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
    elif card_type == 'technicians':
        rows = [
            [t.code, t.name, t.phone or '—', t.job_title or '—',
             t.specialization or '—', t.city or '—', t.status]
            for t in Technician.query.filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).order_by(Technician.name).all()
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
            for c in Contract.query.filter(
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
            for i in InventoryItem.query.filter(
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
            for v in MaintenanceVisit.query.order_by(MaintenanceVisit.visit_date.desc()).limit(50).all()
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
            for f in Fault.query.order_by(Fault.reported_at.desc()).limit(50).all()
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

    customers = (
        Customer.query
        .options(joinedload(Customer.elevators), joinedload(Customer.contracts))
        .order_by(Customer.id.desc())
        .all()
    )
    return render_template(
        'clients.html',
        customers=customers,
        customers_js=[client_to_js_dict(c) for c in customers],
        next_client_code=next_code(Customer, 'C-', digits=4),
    )


@app.route('/clients/template')
def clients_import_template():
    """تحميل نموذج استيراد العملاء."""
    path = os.path.join(app.root_path, 'static', 'templates', 'clients_template.xlsx')
    if not os.path.isfile(path):
        script = os.path.join(app.root_path, 'scripts', 'build_clients_template.py')
        if os.path.isfile(script):
            import importlib.util
            spec = importlib.util.spec_from_file_location('build_clients_template', script)
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
        download_name='clients_template.xlsx',
    )


@app.route('/clients/import-addresses', methods=['POST'])
def clients_import_addresses():
    """تحديث عناوين عملاء موجودين من Excel + إحداثيات للخريطة."""
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'error': 'لم يُرفَع ملف Excel'}), 400
    if not upload.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'الملف يجب أن يكون .xlsx'}), 400

    dry_run = request.form.get('dry_run') == '1'
    no_geocode = request.form.get('no_geocode') == '1'

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
    customer = Customer.query.get_or_404(customer_id)
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

    customer = Customer.query.get_or_404(customer_id)
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

    Customer.query.get_or_404(customer_id)
    return jsonify({
        'customer_id': customer_id,
        'operations': customer_invoicable_revenues(customer_id),
    })


@app.route('/api/customers/<int:customer_id>/uncollected-ops')
def api_customer_uncollected_ops(customer_id):
    from customer_billing import customer_uncollected_ops

    Customer.query.get_or_404(customer_id)
    return jsonify({
        'customer_id': customer_id,
        'operations': customer_uncollected_ops(customer_id),
    })


@app.route('/api/customers/<int:customer_id>/billable-ops')
def api_customer_billable_ops(customer_id):
    from customer_billing import customer_billable_ops

    Customer.query.get_or_404(customer_id)
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
    from technician_assignments import visit_technicians_label, visit_technician_ids, visit_technicians_payload

    rows = []
    for v in visits:
        elev = v.elevator
        cust = elev.customer if elev else None
        linked = getattr(v, 'linked_fault', None)
        saved = parse_report_json(v.checklist_json)
        stats = report_completion_stats(saved, v.checklist_template_key) if saved else {'filled': 0, 'total': 0, 'percent': 0}
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
            'technician': visit_technicians_label(v),
            'tech_id': v.technician_id,
            'tech_ids': visit_technician_ids(v) or ([v.technician_id] if v.technician_id else []),
            'technicians': visit_technicians_payload(v),
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
            'has_report': bool(saved and stats.get('filled', 0) > 0),
            'report_filled': stats.get('filled', 0),
            'report_total': stats.get('total', 0),
            'report_flagged_items': checklist_flagged_items(saved, v.checklist_template_key) if saved else [],
            'report_all_ok': checklist_all_ok(saved, v.checklist_template_key) if saved else False,
        })
    return rows


def _fault_registration_parts_lines(fault_id: int):
    from operations import fault_registration_parts_lines
    return fault_registration_parts_lines(fault_id)


def _faults_js_list(faults):
    from technician_assignments import fault_technicians_label, fault_technician_ids, fault_technicians_payload

    rows = []
    for f in faults:
        elev = f.elevator
        cust = elev.customer if elev else None
        linked = getattr(f, 'linked_visit', None)
        rows.append({
            'id': f.id,
            'code': f.code,
            'elevator_id': f.elevator_id,
            'elevator': elev.code if elev else '',
            'customer': cust.name if cust else '',
            'customer_name_en': (cust.name_en or '') if cust else '',
            'customer_id': cust.id if cust else None,
            'tech_id': f.technician_id,
            'tech_ids': fault_technician_ids(f) or ([f.technician_id] if f.technician_id else []),
            'technician': fault_technicians_label(f),
            'technicians': fault_technicians_payload(f),
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
            'parts_lines': _fault_registration_parts_lines(f.id),
            'has_report': bool(f.report_json),
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
    fault = Fault.query.get(v.fault_id) if v.fault_id else None
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
        e.code for e in Elevator.query.filter(Elevator.id.in_(elev_ids)).all()
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
        'notes': c.notes or '',
    }


@app.route('/api/maintenance-visits/<int:visit_id>')
def api_maintenance_visit(visit_id):
    v = MaintenanceVisit.query.get_or_404(visit_id)
    return jsonify(_visit_json(v))


@app.route('/api/faults/<int:fault_id>')
def api_fault(fault_id):
    f = Fault.query.get_or_404(fault_id)
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

    Customer.query.get_or_404(customer_id)
    faults = (
        Fault.query.join(Elevator, Fault.elevator_id == Elevator.id)
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
            'has_parts': PartsBilling.query.filter_by(fault_id=f.id).count() > 0,
            'needs_parts': bool(f.needs_parts),
        })
    return jsonify({'faults': rows})


@app.route('/api/parts-billing/<int:part_id>')
def api_parts_billing(part_id):
    p = PartsBilling.query.get_or_404(part_id)
    return jsonify(_part_json(p))


@app.route('/api/contracts/<int:contract_id>')
def api_contract_detail(contract_id):
    c = Contract.query.get_or_404(contract_id)
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
    c = Customer(
        code         = next_code(Customer, 'C-', digits=4),
        name         = request.form['name'],
        name_en      = request.form.get('name_en', ''),
        city         = request.form.get('city',''),
        district     = request.form.get('district',''),
        address      = request.form.get('address',''),
        phone        = phone,
        phone2       = wa,
        email        = request.form.get('email',''),
        contact_person = request.form.get('contact_person',''),
        contact_role   = request.form.get('contact_role',''),
        entity_type    = request.form.get('entity_type', 'فرد') or 'فرد',
        national_id    = request.form.get('national_id',''),
        cr_number      = request.form.get('cr_number',''),
        status       = _client_account_status(request.form.get('status', 'نشط')),
        notes        = request.form.get('notes',''),
        lat          = request.form.get('lat',''),
        lng          = request.form.get('lng',''),
        maps_url     = request.form.get('maps_url',''),
    )
    db.session.add(c)
    db.session.flush()
    photo_err = _save_client_building_photo(c, request.files.get('building_photo'))
    db.session.commit()
    if photo_err:
        flash(photo_err, 'error')
    return redirect(url_for('clients'))

@app.route('/clients/edit/<int:id>', methods=['POST'])
def client_edit(id):
    from form_validation import customer_name_error

    c = Customer.query.get_or_404(id)
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
    c.name           = request.form['name']
    c.name_en        = request.form.get('name_en', '')
    c.city           = request.form.get('city','')
    c.district       = request.form.get('district','')
    c.address        = request.form.get('address','')
    c.phone          = phone
    c.phone2         = wa
    c.email          = request.form.get('email','')
    c.contact_person = request.form.get('contact_person','')
    c.status = _client_account_status(request.form.get('status', 'نشط'))
    c.notes          = request.form.get('notes','')
    c.contact_role   = request.form.get('contact_role','')
    c.entity_type    = request.form.get('entity_type', 'فرد') or 'فرد'
    c.national_id    = request.form.get('national_id','')
    c.cr_number      = request.form.get('cr_number','')
    c.lat            = request.form.get('lat','')
    c.lng            = request.form.get('lng','')
    c.maps_url       = request.form.get('maps_url','')
    sync_customer_from_elevators(c)
    upload = request.files.get('building_photo')
    if upload and upload.filename:
        photo_err = _save_client_building_photo(c, upload)
    elif request.form.get('delete_building_photo') == '1':
        _delete_client_building_photo(c)
        photo_err = None
    else:
        photo_err = None
    db.session.commit()
    if photo_err:
        flash(photo_err, 'error')
    return redirect(url_for('clients'))

@app.route('/clients/delete/<int:id>', methods=['POST'])
def client_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    c = Customer.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('clients'))

@app.route('/api/clients')
def api_clients():
    customers = Customer.query.all()
    return jsonify([{'id':c.id,'code':c.code,'name':c.name,'city':c.city} for c in customers])

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
        Elevator.query
        .options(joinedload(Elevator.customer))
        .order_by(Elevator.id.desc())
        .all()
    )
    customers = Customer.query.order_by(Customer.name).all()
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
            }
            for c in customers
        ],
        next_elevator_code=next_code(Elevator, 'EL-', digits=4),
    )


@app.route('/elevators/template')
def elevators_import_template():
    """تحميل نموذج استيراد المصاعد."""
    path = os.path.join(app.root_path, 'static', 'templates', 'elevators_template.xlsx')
    if not os.path.isfile(path):
        script = os.path.join(app.root_path, 'scripts', 'build_elevators_template.py')
        if os.path.isfile(script):
            import importlib.util
            spec = importlib.util.spec_from_file_location('build_elevators_template', script)
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
        download_name='elevators_template.xlsx',
    )


@app.route('/elevators/add', methods=['POST'])
def elevator_add():
    from form_validation import elevator_form_error

    elev_err = elevator_form_error(request.form, parse_int=_parse_int)
    if elev_err:
        flash(elev_err, 'error')
        return redirect(url_for('elevators'))
    e = Elevator(
        code            = next_code(Elevator, 'EL-', digits=4),
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
    e = Elevator.query.get_or_404(id)
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
    e = Elevator.query.get_or_404(id)
    customer = e.customer
    db.session.delete(e)
    db.session.flush()
    sync_customer_from_elevators(customer)
    db.session.commit()
    return redirect(url_for('elevators'))

@app.route('/api/elevators/<int:customer_id>')
def api_elevators_by_customer(customer_id):
    elevs = Elevator.query.filter_by(customer_id=customer_id).all()
    return jsonify([{'id':e.id,'code':e.code,'building':e.building_name} for e in elevs])

def contract_display_status(contract, today=None):
    today = today or date.today()
    raw = contract.status or 'نشط'
    if raw in ('ملغي', 'معلق'):
        return 'ملغي'
    if raw == 'منتهي' or (contract.end_date and contract.end_date < today):
        return 'منتهي'
    if raw == 'على وشك الانتهاء':
        return 'على وشك الانتهاء'
    if contract.end_date and contract.status == 'نشط':
        days_left = (contract.end_date - today).days
        if 0 < days_left <= 30:
            return 'على وشك الانتهاء'
    return 'نشط'


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
    c = Contract.query.get(contract_id)
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
        Contract.query.filter_by(customer_id=customer.id)
        .order_by(Contract.end_date.desc())
        .all()
    )
    if not contracts:
        return None
    for c in contracts:
        if contract_display_status(c) in ('نشط', 'على وشك الانتهاء'):
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

    customer = Customer.query.get_or_404(customer_id)
    if contract_id:
        contract = Contract.query.filter_by(
            id=contract_id, customer_id=customer_id
        ).first_or_404()
    else:
        contract = customer_primary_contract(customer)

    contracts = (
        Contract.query.filter_by(customer_id=customer_id)
        .order_by(Contract.start_date.desc())
        .all()
    )

    rev_q = Revenue.query.filter(
        Revenue.customer_id == customer_id,
        Revenue.status.in_(('محصّل', 'محصل')),
    )
    parts_q = PartsBilling.query.filter(
        PartsBilling.customer_id == customer_id,
        PartsBilling.status.in_(('مكتملة', 'محصل', 'محصّل')),
    )
    inv_q = Invoice.query.filter(
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
    balance = max(contract_value - contract_payments, 0) if contract else 0

    visit_q = MaintenanceVisit.query.join(Elevator).filter(
        Elevator.customer_id == customer_id
    )
    fault_q = Fault.query.join(Elevator).filter(
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
    ContractElevator.query.filter_by(contract_id=contract_id).delete()
    for eid in elevator_ids:
        if eid:
            db.session.add(ContractElevator(contract_id=contract_id, elevator_id=int(eid)))


def _purge_contract_dependencies(contract_id):
    """إزالة الارتباطات التي تمنع حذف العقد."""
    MaintenanceVisit.query.filter_by(contract_id=contract_id).delete(synchronize_session=False)
    ContractElevator.query.filter_by(contract_id=contract_id).delete(synchronize_session=False)
    Invoice.query.filter_by(contract_id=contract_id).update(
        {Invoice.contract_id: None}, synchronize_session=False
    )
    Revenue.query.filter_by(contract_id=contract_id).update(
        {Revenue.contract_id: None}, synchronize_session=False
    )
    PartsBilling.query.filter_by(contract_id=contract_id).update(
        {PartsBilling.contract_id: None}, synchronize_session=False
    )


def _apply_contract_form(c, form):
    value = _money_round(form.get('value', 0))
    tax_pct = _money_round(form.get('tax_pct', 15) or 15)
    total_raw = form.get('total')
    if total_raw not in (None, ''):
        total = _money_round(total_raw)
        tax_amount = _money_round(total - value)
    else:
        tax_amount = _money_round(value * tax_pct / 100)
        total = _money_round(value + tax_amount)
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
    c.city = form.get('city', '')
    c.district = form.get('district', '')
    c.address = form.get('address', '')
    c.notes = form.get('notes', '')
    c.invoice_status = contract_invoice_status(c)


def _contract_upload_dir(contract_id):
    path = os.path.join(app.root_path, 'static', 'uploads', 'contracts', str(contract_id))
    os.makedirs(path, exist_ok=True)
    return path


def contract_file_display_name(relative_path):
    if not relative_path:
        return ''
    base = os.path.basename(relative_path.replace('\\', '/'))
    if '_' in base:
        return base.split('_', 1)[1]
    return base


def _remove_contract_file(c):
    if not c.file_path:
        return
    full = os.path.join(app.root_path, 'static', c.file_path.replace('/', os.sep))
    if os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass


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
    original = secure_filename(file_storage.filename) or 'contract.pdf'
    stored = f'{uuid.uuid4().hex[:10]}_{original}'
    abs_path = os.path.join(_contract_upload_dir(c.id), stored)
    file_storage.save(abs_path)
    c.file_path = f'uploads/contracts/{c.id}/{stored}'


# =============================================
# العقود
# =============================================
@app.route('/contracts')
def contracts():
    from sqlalchemy.orm import joinedload

    contracts_list = (
        Contract.query
        .options(joinedload(Contract.customer), joinedload(Contract.elevators))
        .order_by(Contract.id.desc())
        .all()
    )
    customers = Customer.query.order_by(Customer.name).all()
    elev_lookup = {
        e.id: {'code': e.code, 'building': e.building_name or '', 'customer_id': e.customer_id}
        for e in Elevator.query.all()
    }
    return render_template(
        'contracts.html',
        contracts=contracts_list,
        contracts_js=[contract_to_js_dict(c) for c in contracts_list],
        customers_js=[contract_customer_js_dict(c) for c in customers],
        elev_lookup=elev_lookup,
        next_contract_code=next_code(Contract, 'CN-', digits=5),
    )


@app.route('/contracts/template')
def contracts_import_template():
    """تحميل نموذج استيراد العقود."""
    path = os.path.join(app.root_path, 'static', 'templates', 'contracts_template.xlsx')
    if not os.path.isfile(path):
        script = os.path.join(app.root_path, 'scripts', 'build_contracts_template.py')
        if os.path.isfile(script):
            import importlib.util
            spec = importlib.util.spec_from_file_location('build_contracts_template', script)
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
        download_name='contracts_template.xlsx',
    )


@app.route('/contracts/edit/<int:id>', methods=['POST'])
def contract_edit(id):
    from form_validation import contract_form_error

    err = contract_form_error(request.form, money_round=_money_round)
    if err:
        flash(err, 'error')
        return redirect(url_for('contracts'))
    c = Contract.query.get_or_404(id)
    _apply_contract_form(c, request.form)
    _save_contract_file(c, request.files.get('contract_file'))
    _sync_contract_elevators(c.id, request.form.getlist('elevator_ids'))
    db.session.commit()
    return redirect(url_for('contracts'))


@app.route('/contracts/add', methods=['POST'])
def contract_add():
    from form_validation import contract_form_error

    err = contract_form_error(request.form, money_round=_money_round)
    if err:
        flash(err, 'error')
        return redirect(url_for('contracts'))
    c = Contract(code=next_code(Contract, 'CN-', digits=5))
    _apply_contract_form(c, request.form)
    db.session.add(c)
    db.session.flush()
    _save_contract_file(c, request.files.get('contract_file'))
    _sync_contract_elevators(c.id, request.form.getlist('elevator_ids'))
    db.session.commit()
    return redirect(url_for('contracts'))

@app.route('/contracts/delete/<int:id>', methods=['POST'])
def contract_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    c = Contract.query.get_or_404(id)
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
    busy_visit = MaintenanceVisit.query.filter(
        visits_for_technician_filter(tech.id),
        MaintenanceVisit.visit_date == today,
        MaintenanceVisit.status == 'جارٍ',
    ).count()
    open_fault = Fault.query.filter(
        faults_for_technician_filter(tech.id),
        Fault.status == 'قيد المعالجة',
    ).count()
    if busy_visit or open_fault:
        return 'مشغول'
    return raw if raw in ('متاح', 'مشغول') else 'متاح'


app.jinja_env.globals['technician_display_status'] = technician_display_status


def technician_to_js_dict(t):
  """تسلسل فني لـ JSON (حالة العرض تُحسب مرة واحدة في السيرفر)."""
  docs = []
  for d in sorted(t.documents, key=lambda x: x.uploaded_at or datetime.min, reverse=True):
    fname = d.file_name or ''
    docs.append({
      'id': d.id,
      'doc_type': d.doc_type or '',
      'title': d.title or d.file_name or '',
      'file_name': fname,
      'url': url_for('static', filename=d.file_path) if d.file_path else '',
      'is_image': fname.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')),
      'is_pdf': fname.lower().endswith('.pdf'),
      'uploaded_at': d.uploaded_at.strftime('%Y-%m-%d') if d.uploaded_at else '',
    })
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
    'national_id': t.national_id or '',
    'hire_date': t.hire_date.isoformat() if t.hire_date else '',
    'salary': t.salary or 0,
    'emergency': bool(t.emergency),
    'status': t.status or 'متاح',
    'display_status': technician_display_status(t),
    'visits': len(t.visits),
    'faults': len(t.faults),
    'notes': t.notes or '',
    'photo_url': upload_url(t.photo_path) if t.photo_path else '',
    'signature_url': upload_url(t.signature_path) if t.signature_path else '',
    'has_sign_pin': bool(t.sign_pin_hash),
    'documents': len(t.documents),
    'docs': docs,
  }


from technician_assignments import fault_technicians_label as _fault_technicians_label_jinja
from technician_assignments import visit_technicians_label as _visit_technicians_label_jinja
app.jinja_env.globals['fault_technicians_label'] = _fault_technicians_label_jinja
app.jinja_env.globals['visit_technicians_label'] = _visit_technicians_label_jinja


def _apply_technician_form(t, form):
    t.name = form['name']
    t.name_en = form.get('name_en', '')
    t.phone = form.get('phone', '')
    t.phone2 = form.get('phone2', '')
    t.job_title = form.get('job_title', '')
    t.specialization = form.get('specialization', '')
    t.city = form.get('city', '')
    t.national_id = form.get('national_id', '')
    t.hire_date = _parse_date(form.get('hire_date'))
    salary = form.get('salary')
    t.salary = float(salary) if salary not in (None, '') else None
    t.emergency = form.get('emergency') == 'on'
    t.status = form.get('status', 'متاح')
    t.team = form.get('team', 'عام') or 'عام'
    t.notes = form.get('notes', '')


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
    return send_from_directory(directory, subpath)


app.jinja_env.globals['upload_url'] = upload_url
app.jinja_env.globals['contract_file_display_name'] = contract_file_display_name


def _ext_ok(filename, allowed):
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in allowed


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
    has_file = file_storage and file_storage.filename and _ext_ok(file_storage.filename, ALLOWED_TECH_PHOTO_EXT)
    existing = Signatory.query.filter_by(technician_id=tech.id, is_active=True).first()
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
    if not tech.national_id:
        raise ValueError('أدخل رقم الإقامة في الوثائق الرسمية قبل حفظ التوقيع')
    raw = file_storage.read() if has_file else None
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
    if not _ext_ok(file_storage.filename, ALLOWED_TECH_PHOTO_EXT):
        return
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
    for i, file_storage in enumerate(files):
        if not file_storage or not file_storage.filename:
            continue
        if not _ext_ok(file_storage.filename, ALLOWED_TECH_DOC_EXT):
            continue
        original = secure_filename(file_storage.filename) or 'document'
        ext = original.rsplit('.', 1)[1].lower() if '.' in original else 'pdf'
        stored = f'{uuid.uuid4().hex[:12]}_{original}'
        abs_path = os.path.join(docs_folder, stored)
        file_storage.save(abs_path)
        doc_type = types[i] if i < len(types) and types[i] else 'أخرى'
        title = titles[i] if i < len(titles) and titles[i] else original
        db.session.add(TechnicianDocument(
            technician_id=tech.id,
            doc_type=doc_type,
            title=title,
            file_path=f'uploads/technicians/{tech.id}/docs/{stored}',
            file_name=original,
            mime_type=file_storage.mimetype or '',
        ))


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
        Technician.query
        .options(
            joinedload(Technician.documents),
            joinedload(Technician.visits),
            joinedload(Technician.faults),
        )
        .order_by(Technician.id.desc())
        .all()
    )
    unassigned_faults = Fault.query.filter(
        Fault.technician_id.is_(None),
        Fault.status.in_(['مفتوح', 'قيد المعالجة']),
    ).count()
    maint_techs = [t for t in techs if (t.team or 'عام') in ('صيانة', 'عام')] or list(techs)
    from maintenance_teams import list_all_teams, team_to_dict
    maint_teams = [team_to_dict(t) for t in list_all_teams() if t.active]
    return render_template(
        'technicians.html',
        technicians=techs,
        technicians_js=[technician_to_js_dict(t) for t in techs],
        next_tech_code=next_code(Technician, 'Tech-', digits=3),
        unassigned_faults=unassigned_faults,
        maint_technicians=maint_techs,
        maint_technicians_js=[{'id': t.id, 'name': t.name} for t in maint_techs],
        maint_teams_js=maint_teams,
    )


@app.route('/api/technicians/<int:tech_id>/profile')
def api_technician_profile(tech_id):
    tech = Technician.query.get_or_404(tech_id)
    today = date.today()
    visits = (
        MaintenanceVisit.query.filter_by(technician_id=tech_id)
        .order_by(MaintenanceVisit.visit_date.desc())
        .limit(25)
        .all()
    )
    faults = (
        Fault.query.filter_by(technician_id=tech_id)
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
        },
        'documents': _technician_documents_json(tech),
        'stats': {
            'total_visits': len(tech.visits),
            'total_faults': len(tech.faults),
            'open_faults': sum(1 for f in tech.faults if f.status in ('مفتوح', 'قيد المعالجة')),
            'today_visits': sum(1 for v in tech.visits if v.visit_date == today),
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
    phone = request.form.get('phone', '')
    taken, msg = phone_taken(phone)
    if taken:
        flash(msg, 'error')
        return redirect(url_for('technicians'))
    wa = request.form.get('phone2', '')
    if wa and phone_key(wa) != phone_key(phone):
        taken2, msg2 = phone_taken(wa)
        if taken2:
            flash(msg2, 'error')
            return redirect(url_for('technicians'))
    t = Technician(code=next_code(Technician, 'Tech-', digits=3))
    try:
        _apply_technician_form(t, request.form)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('technicians'))
    db.session.add(t)
    db.session.flush()
    _save_technician_photo(t, request.files.get('photo'))
    try:
        _save_technician_signature(t, request.files.get('signature'), request.form.get('sign_pin', ''))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
        return redirect(url_for('technicians'))
    _save_technician_documents(
        t,
        request.files.getlist('documents'),
        request.form.getlist('doc_types'),
        request.form.getlist('doc_titles'),
    )
    db.session.commit()
    flash('تم إضافة الفني بنجاح', 'success')
    return redirect(url_for('technicians'))


@app.route('/technicians/<int:id>/phone', methods=['POST'])
def technician_update_phone(id):
    t = Technician.query.get_or_404(id)
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
    t = Technician.query.get_or_404(id)
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
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('technicians'))
    _save_technician_photo(t, request.files.get('photo'))
    try:
        _save_technician_signature(t, request.files.get('signature'), request.form.get('sign_pin', ''))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
        return redirect(url_for('technicians'))
    _save_technician_documents(
        t,
        request.files.getlist('documents'),
        request.form.getlist('doc_types'),
        request.form.getlist('doc_titles'),
    )
    db.session.commit()
    flash('تم تحديث بيانات الفني بنجاح', 'success')
    return redirect(url_for('technicians'))


@app.route('/technicians/documents/delete/<int:doc_id>', methods=['POST'])
def technician_document_delete(doc_id):
    err = enforce_admin_delete(json_response=True)
    if err:
        return err
    doc = TechnicianDocument.query.get_or_404(doc_id)
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
    t = Technician.query.get_or_404(id)
    _remove_technician_files(t)
    db.session.delete(t)
    db.session.commit()
    return redirect(url_for('technicians'))

# =============================================
# زيارات الصيانة
# =============================================
@app.route('/maintenance-visits')
def maintenance_visits():
    from operations import exclude_fault_visits, list_districts, visit_alerts, visit_stats
    from sqlalchemy.orm import joinedload

    visits = exclude_fault_visits(
        MaintenanceVisit.query.options(
            joinedload(MaintenanceVisit.elevator).joinedload(Elevator.customer),
        )
    ).order_by(MaintenanceVisit.visit_date.desc()).all()
    elevators = Elevator.query.options(joinedload(Elevator.customer)).all()
    customers = Customer.query.order_by(Customer.name).all()
    contracts = Contract.query.order_by(Contract.start_date.desc()).all()
    technicians = Technician.query.filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول'])
    ).all()
    today = date.today()
    plan_default = f'{today.year}-{today.month:02d}'
    month_end = today.replace(day=monthrange(today.year, today.month)[1])
    maint_techs = [t for t in technicians if (t.team or 'عام') in ('صيانة', 'عام')] or list(technicians)
    from maintenance_teams import list_all_teams, team_to_dict
    maint_teams = [team_to_dict(t) for t in list_all_teams() if t.active]
    all_teams = [team_to_dict(t) for t in list_all_teams()]
    from visit_cleanup import find_duplicate_visit_ids
    duplicate_visit_ids = find_duplicate_visit_ids()
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
    elev = Elevator.query.get_or_404(elevator_id)
    customer = elev.customer

    parts = (
        PartsBilling.query.filter_by(elevator_id=elevator_id)
        .order_by(PartsBilling.billing_date.desc(), PartsBilling.id.desc())
        .all()
    )
    stock_moves = (
        StockMovement.query.filter_by(elevator_id=elevator_id, direction='صادر')
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
        MaintenanceVisit.query.filter_by(elevator_id=elevator_id)
        .order_by(MaintenanceVisit.visit_date.desc())
        .limit(8)
        .all()
    )
    faults = (
        Fault.query.filter_by(elevator_id=elevator_id)
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
            'visits_count': MaintenanceVisit.query.filter_by(elevator_id=elevator_id).count(),
            'faults_count': Fault.query.filter_by(elevator_id=elevator_id).count(),
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
        MaintenanceVisit.query.filter(
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

    v = MaintenanceVisit.query.get_or_404(id)
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
    v = MaintenanceVisit.query.get(visit_id)
    if not v:
        return
    VisitTechnician.query.filter_by(visit_id=visit_id).delete(synchronize_session=False)
    Fault.query.filter_by(visit_id=visit_id).update(
        {Fault.visit_id: None}, synchronize_session=False
    )
    PartsBilling.query.filter_by(visit_id=visit_id).update(
        {PartsBilling.visit_id: None}, synchronize_session=False
    )
    if v.fault_id:
        fault = Fault.query.get(v.fault_id)
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
    v = MaintenanceVisit.query.get_or_404(id)
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
        MaintenanceVisit.query.order_by(MaintenanceVisit.visit_date.desc())
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
        first = MaintenanceVisit.query.get(int(visit_ids[0]))
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
        team = MaintenanceTeam.query.get_or_404(int(team_id))
    else:
        team = MaintenanceTeam(code=next_code(MaintenanceTeam, 'MT-', digits=3))
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
    team = MaintenanceTeam.query.get_or_404(team_id)
    assigned = MaintenanceVisit.query.filter_by(maintenance_team_id=team.id).count()
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

    result = dispatch_fault(fault_id, request.url_root)
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
                inactive = Technician.query.filter(Technician.code.ilike(raw)).first()
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

    tech = Technician.query.get_or_404(tech_id)
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

    tech_id = getattr(g, 'field_tech_id', None)
    if tech_id:
        f = Fault.query.get_or_404(fault_id)
        if not technician_assigned_to_fault(f, tech_id):
            return jsonify({'ok': False, 'error': 'العطل غير مخصص لهذا الفني'}), 403

    data = request.get_json(silent=True) or {}
    mark_resolved = bool(data.pop('mark_resolved', False))
    try:
        save_fault_report(fault_id, data, mark_resolved=mark_resolved)
        return jsonify({'ok': True, 'fault_id': fault_id})
    except Exception as e:
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
        v = MaintenanceVisit.query.get(visit_id)
        if v:
            field_tid = getattr(g, 'field_tech_id', None) or _resolve_field_technician_id()
            if field_tid and technician_assigned_to_visit(v, field_tid):
                visit_technician_id = field_tid
            else:
                visit_technician_id = v.technician_id
    elif fault_id:
        f = Fault.query.get(fault_id)
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
        v = MaintenanceVisit.query.get_or_404(visit_id)
        if v.technician_id and v.technician_id != tech_id:
            return jsonify({'ok': False, 'error': 'الزيارة غير مخصصة لهذا الفني'}), 403

    data = request.get_json(silent=True) or {}
    mark_complete = bool(data.pop('mark_complete', False))
    status = data.pop('status', 'مكتملة')
    try:
        save_visit_report(visit_id, data, mark_complete=mark_complete, status=status)
        return jsonify({'ok': True, 'visit_id': visit_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


@app.route('/field/visit/<int:visit_id>/complete', methods=['POST'])
def field_visit_complete(visit_id):
    from operations import complete_field_visit

    tech_id = getattr(g, 'field_tech_id', None)
    if tech_id:
        v = MaintenanceVisit.query.get_or_404(visit_id)
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

    tech_id = getattr(g, 'field_tech_id', None)
    if tech_id:
        f = Fault.query.get_or_404(fault_id)
        if f.technician_id and f.technician_id != tech_id:
            abort(403)

    try:
        complete_field_fault(
            fault_id,
            tech_notes=request.form.get('tech_notes', ''),
            resolution=request.form.get('resolution', ''),
            status=request.form.get('status', 'تم الاصلاح'),
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
        f = Fault.query.get_or_404(fault_id)
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
@app.route('/faults')
def faults():
    from operations import fault_alerts, fault_stats
    from sqlalchemy.orm import joinedload

    faults_list = (
        Fault.query
        .options(joinedload(Fault.elevator).joinedload(Elevator.customer))
        .order_by(Fault.reported_at.desc())
        .all()
    )
    elevators = Elevator.query.options(joinedload(Elevator.customer)).all()
    customers = Customer.query.order_by(Customer.name).all()
    inventory_items = InventoryItem.query.order_by(InventoryItem.name).all()
    technicians = Technician.query.filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول'])
    ).all()
    pending_wa = session.pop('pending_whatsapp', '')
    fault_techs = [t for t in technicians if (t.team or 'عام') in ('أعطال', 'عام')] or list(technicians)
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
    )


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


def _apply_fault_billing_from_form(fault, form):
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
        else:
            clear_fault_parts_billing(fault.id)
    else:
        fault.needs_parts = False
        fault.billed = False
        clear_fault_parts_billing(fault.id)


@app.route('/faults/edit/<int:id>', methods=['POST'])
def fault_edit(id):
    from entity_links import link_fault_to_visit, lookup_visit
    from form_validation import fault_close_error
    from technician_assignments import parse_technician_ids, sync_fault_technicians

    close_err = fault_close_error(
        request.form.get('status'),
        request.form.get('resolution'),
    )
    if close_err:
        flash(close_err, 'error')
        return redirect(url_for('faults'))

    f = Fault.query.get_or_404(id)
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
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('faults'))
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

    billable = request.form.get('billable', 'no')
    client_report = request.form.get('client_report') or request.form.get('description', '')
    reported = _parse_reported_at(request.form.get('reported_at'))
    tech_ids = parse_technician_ids(request.form)
    f = Fault(
        code          = next_code(Fault, 'FA-', digits=5),
        elevator_id   = request.form['elevator_id'],
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
    db.session.add(f)
    db.session.flush()
    sync_fault_technicians(f, tech_ids)

    visit_code = request.form.get('visit_code', '').strip()
    if visit_code:
        visit = lookup_visit(visit_code)
        if visit:
            link_fault_to_visit(f, visit)

    try:
        _apply_fault_billing_from_form(f, request.form)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('faults'))

    if f.technician_id:
        base = request.url_root
        result = dispatch_fault(f.id, base)
        if result.get('whatsapp_url'):
            session['pending_whatsapp'] = result['whatsapp_url']
    return redirect(url_for('faults'))

@app.route('/faults/delete/<int:id>', methods=['POST'])
def fault_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    f = Fault.query.get_or_404(id)
    FaultTechnician.query.filter_by(fault_id=id).delete(synchronize_session=False)
    MaintenanceVisit.query.filter_by(fault_id=id).update(
        {MaintenanceVisit.fault_id: None}, synchronize_session=False
    )
    PartsBilling.query.filter_by(fault_id=id).update(
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

    revs = (
        Revenue.query
        .options(joinedload(Revenue.customer), joinedload(Revenue.contract))
        .order_by(Revenue.revenue_date.desc())
        .all()
    )
    customers = Customer.query.order_by(Customer.name).all()
    return render_template(
        'revenues.html',
        revenues=revs,
        customers=customers,
        revenues_js=[revenue_to_js_dict(r) for r in revs],
        customers_js=[{'id': c.id, 'name': c.name, 'code': c.code} for c in customers],
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
    if existing:
        for key, val in data.items():
            setattr(existing, key, val)
        return existing
    r = Revenue(code=next_code(Revenue, 'REV-', digits=3), **data)
    db.session.add(r)
    return r


@app.route('/revenues/edit/<int:id>', methods=['POST'])
def revenue_edit(id):
    from customer_billing import COLLECTED_REVENUE_STATUSES, create_receipt_voucher_for_revenue

    r = Revenue.query.get_or_404(id)
    old_contract_id = r.contract_id
    _revenue_from_form(request.form, existing=r)
    receipt = None
    if (r.status or '') in COLLECTED_REVENUE_STATUSES:
        receipt = create_receipt_voucher_for_revenue(r)
    sync_contract_invoice_status(r.contract_id)
    if old_contract_id and old_contract_id != r.contract_id:
        sync_contract_invoice_status(old_contract_id)
    db.session.commit()
    if receipt:
        flash(f'تم إنشاء سند قبض {receipt.code} تلقائياً', 'success')
    return redirect(url_for('revenues'))

@app.route('/revenues/add', methods=['POST'])
def revenue_add():
    from customer_billing import COLLECTED_REVENUE_STATUSES, create_receipt_voucher_for_revenue

    r = _revenue_from_form(request.form)
    db.session.flush()
    receipt = None
    if (r.status or '') in COLLECTED_REVENUE_STATUSES:
        receipt = create_receipt_voucher_for_revenue(r)
    sync_contract_invoice_status(r.contract_id)
    db.session.commit()
    if receipt:
        flash(f'تم إنشاء سند قبض {receipt.code} تلقائياً', 'success')
    return redirect(url_for('revenues'))

@app.route('/revenues/delete/<int:id>', methods=['POST'])
def revenue_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    r = Revenue.query.get_or_404(id)
    contract_id = r.contract_id
    db.session.delete(r)
    sync_contract_invoice_status(contract_id)
    db.session.commit()
    return redirect(url_for('revenues'))

# =============================================
# المصروفات
# =============================================
@app.route('/expenses')
def expenses():
    exps = Expense.query.order_by(Expense.expense_date.desc()).all()
    return render_template(
        'expenses.html',
        expenses=exps,
        expenses_js=[expense_to_js_dict(e) for e in exps],
    )
@app.route('/expenses/edit/<int:id>', methods=['POST'])
def expense_edit(id):
    e = Expense.query.get_or_404(id)
    e.expense_date   = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
    e.expense_type   = request.form.get('expense_type','')
    e.description    = request.form.get('description','')
    e.responsible    = request.form.get('responsible','')
    e.payment_method = request.form.get('payment_method','')
    e.amount         = float(request.form.get('amount', 0))
    e.reference      = request.form.get('reference','')
    e.notes          = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('expenses'))

@app.route('/expenses/add', methods=['POST'])
def expense_add():
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
    db.session.add(e)
    db.session.commit()
    return redirect(url_for('expenses'))

@app.route('/expenses/delete/<int:id>', methods=['POST'])
def expense_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    e = Expense.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    return redirect(url_for('expenses'))

# =============================================
# الفواتير
# =============================================
@app.route('/invoices')
def invoices():
    from sqlalchemy.orm import joinedload

    invs = (
        Invoice.query
        .options(joinedload(Invoice.customer), joinedload(Invoice.contract))
        .order_by(Invoice.invoice_date.desc())
        .all()
    )
    customers = Customer.query.order_by(Customer.name).all()
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

    i = Invoice.query.get_or_404(id)
    amount = float(request.form.get('amount', 0) or 0)
    tax = amount * 0.15
    total = amount + tax
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
    i.total          = amount + tax
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
        validate_tax_invoice_full_amount,
    )

    amount = float(request.form.get('amount', 0) or 0)
    tax = round(amount * 0.15, 2)
    total = round(amount + tax, 2)
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
    customer_id = request.form.get('customer_id') or None
    contract_id = request.form.get('contract_id') or None
    parts_billing_id = None
    notes = request.form.get('notes', '')
    description = (request.form.get('description') or '').strip()

    if source_type == 'parts_billing' and source_id:
        pb = PartsBilling.query.get_or_404(int(source_id))
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
        c = Contract.query.get_or_404(int(source_id))
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
        pb = PartsBilling.query.get(int(source_id))
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
        c = Contract.query.get(int(source_id))
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
    db.session.add(i)
    db.session.flush()
    if source_type == 'contract' and source_id and contract_id:
        for rev in Revenue.query.filter_by(
            contract_id=int(contract_id),
            customer_id=i.customer_id,
        ).filter(Revenue.invoice_id.is_(None)):
            rev.invoice_id = i.id
    sync_contract_invoice_status(i.contract_id)
    db.session.commit()
    return redirect(url_for('invoices'))

@app.route('/invoices/<int:invoice_id>/print')
def invoice_print_page(invoice_id):
    from invoice_print import invoice_print_payload

    invo = Invoice.query.get_or_404(invoice_id)
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
    i = Invoice.query.get_or_404(id)
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
    items = InventoryItem.query.order_by(InventoryItem.id.desc()).all()
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
    item = InventoryItem.query.get_or_404(id)
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
    if InventoryItem.query.filter_by(code=code).first():
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
    db.session.add(item)
    db.session.commit()
    return redirect(url_for('inventory'))

@app.route('/inventory/delete/<int:id>', methods=['POST'])
def inventory_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('inventory'))


@app.route('/inventory/template')
def inventory_import_template():
    """تحميل نموذج استيراد الأصناف."""
    path = os.path.join(app.root_path, 'static', 'templates', 'inventory_template.xlsx')
    if not os.path.isfile(path):
        script = os.path.join(app.root_path, 'scripts', 'build_inventory_template.py')
        if os.path.isfile(script):
            import importlib.util
            spec = importlib.util.spec_from_file_location('build_inventory_template', script)
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
        download_name='inventory_template.xlsx',
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
    orders = PurchaseOrder.query.order_by(PurchaseOrder.order_date.desc().nullslast()).all()
    items = InventoryItem.query.order_by(InventoryItem.name).all()
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
        order = PurchaseOrder.query.get_or_404(int(order_id))
    else:
        order = PurchaseOrder(code=next_code(PurchaseOrder, 'PO-', digits=4))
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
        order.lines.append(PurchaseOrderLine(**row))
        total += row['line_total']
    order.total_amount = total
    if order.status == 'مستلم' and old_status != 'مستلم':
        _apply_purchase_receipt(order)
    db.session.commit()
    return redirect(url_for('purchase_order_print', order_id=order.id))


def _purchase_order_print_context(order, *, en_only=False):
    s = Settings.query.first()
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
    order = PurchaseOrder.query.get_or_404(order_id)
    return render_template(
        'purchase-order-print.html',
        **_purchase_order_print_context(order),
    )


@app.route('/purchase-orders/<int:order_id>/print-en')
def purchase_order_print_en(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    return render_template(
        'purchase-order-print.html',
        **_purchase_order_print_context(order, en_only=True),
    )


@app.route('/purchase-orders/<int:order_id>/contact', methods=['POST'])
def purchase_order_update_contact(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    order.supplier_phone = request.form.get('supplier_phone', '').strip() or None
    order.supplier_email = request.form.get('supplier_email', '').strip() or None
    db.session.commit()
    if request.form.get('en_only') == '1':
        return redirect(url_for('purchase_order_print_en', order_id=order.id))
    return redirect(url_for('purchase_order_print', order_id=order.id))


@app.route('/purchase-orders/<int:order_id>/signature', methods=['POST'])
def purchase_order_save_signature(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    payload = request.get_json(silent=True) or {}
    sig = (payload.get('signature') or '').strip()
    if sig and sig.startswith('data:image/') and len(sig) < 600000:
        order.signature_data = sig
        db.session.commit()
    return jsonify(ok=True)


@app.route('/purchase-orders/<int:order_id>/pdf', methods=['POST'])
def purchase_order_upload_pdf(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
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


@app.route('/purchase-orders/delete/<int:order_id>', methods=['POST'])
def purchase_orders_delete(order_id):
    err = enforce_admin_delete()
    if err:
        return err
    order = PurchaseOrder.query.get_or_404(order_id)
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
    estimates = ElevatorEstimate.query.order_by(ElevatorEstimate.created_at.desc()).all()
    customers = Customer.query.order_by(Customer.name).all()
    edit_raw = request.args.get('edit', '').strip()
    edit_est = None
    if edit_raw.isdigit():
        edit_est = ElevatorEstimate.query.get(int(edit_raw))
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
        est = ElevatorEstimate.query.get_or_404(int(estimate_id))
    else:
        est = ElevatorEstimate(code=next_code(ElevatorEstimate, 'ES-', digits=4))
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
        est.lines.append(ElevatorEstimateLine(**row))
    db.session.commit()
    return redirect(url_for('elevator_estimate_print', estimate_id=est.id))


@app.route('/elevator-estimates/delete/<int:estimate_id>', methods=['POST'])
def elevator_estimates_delete(estimate_id):
    err = enforce_admin_delete()
    if err:
        return err
    est = ElevatorEstimate.query.get_or_404(estimate_id)
    db.session.delete(est)
    db.session.commit()
    return redirect(url_for('elevator_estimates'))


@app.route('/elevator-estimates/print/<int:estimate_id>')
def elevator_estimate_print(estimate_id):
    est = ElevatorEstimate.query.get_or_404(estimate_id)
    s = Settings.query.first()
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
        StockMovement.query
        .options(joinedload(StockMovement.item))
        .order_by(StockMovement.movement_date.desc())
        .all()
    )
    items = InventoryItem.query.order_by(InventoryItem.name).all()
    technicians = Technician.query.filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).all()
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
    db.session.add(m)

    item = InventoryItem.query.get(item_id)
    _adjust_inventory_qty(item, direction, qty)

    db.session.commit()
    return redirect(url_for('stock_movements'))

@app.route('/stock-movements/delete/<int:id>', methods=['POST'])
def stock_delete(id):
    err = enforce_admin_delete()
    if err:
        return err
    m = StockMovement.query.get_or_404(id)
    item = InventoryItem.query.get(m.item_id)
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
        PartsBilling.query
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
    customers = Customer.query.order_by(Customer.name).all()
    contracts = Contract.query.order_by(Contract.code).all()
    inventory_items = InventoryItem.query.order_by(InventoryItem.name).all()
    technicians = Technician.query.filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول'])
    ).order_by(Technician.name).all()
    pending_faults = Fault.query.filter_by(status='انتظار قطع').order_by(
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

    p = PartsBilling.query.get_or_404(id)
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
        fault = Fault.query.get(links['fault_id'])
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
        fault = Fault.query.get(links['fault_id'])
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

    p = PartsBilling.query.get_or_404(id)
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
    customers = Customer.query.order_by(Customer.name).all()
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
    for u in User.query.all():
        if u.password_hash and not password_is_hashed(u.password_hash):
            u.password_hash = hash_password(u.password_hash)
            changed = True
    if changed:
        db.session.commit()


def _flag_weak_default_passwords():
    """يُعلِم المستخدمين بكلمات مرور افتراضية معروفة."""
    from liftcore_security import BANNED_PASSWORDS
    changed = False
    for u in User.query.all():
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
    if not file_storage or not file_storage.filename:
        return
    if not _ext_ok(file_storage.filename, ALLOWED_LOGO_EXT):
        return
    os.makedirs(COMPANY_UPLOAD_ROOT, exist_ok=True)
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    if ext == 'svg':
        filename = 'logo.svg'
    else:
        filename = f'logo.{ext}'
    for old in os.listdir(COMPANY_UPLOAD_ROOT):
        if old.startswith('logo.'):
            try:
                os.remove(os.path.join(COMPANY_UPLOAD_ROOT, old))
            except OSError:
                pass
    file_storage.save(os.path.join(COMPANY_UPLOAD_ROOT, filename))
    settings_row.logo_path = f'uploads/company/{filename}'


def _clamp_logo_width(value, default=150, min_w=60, max_w=400):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_w, min(max_w, n))


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
    users = User.query.order_by(User.id).all()
    edit_user = None
    edit_id = request.args.get('edit_user', type=int)
    if edit_id and user.role == 'admin':
        edit_user = User.query.get(edit_id)
    try:
        signatories = Signatory.query.filter_by(is_active=True).order_by(Signatory.name).all()
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
    for t in Technician.query.order_by(Technician.name).all():
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
    )


@app.route('/settings/field-portal/<int:tech_id>/pin', methods=['POST'])
def settings_field_portal_pin(tech_id):
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة.'
        return _settings_redirect('field-portal')
    from signature_auth import validate_sign_pin

    tech = Technician.query.get_or_404(tech_id)
    pin = (request.form.get('pin') or '').strip()
    if not validate_sign_pin(pin):
        session['settings_notice'] = 'رمز دخول الجوال يجب أن يكون 6 أرقام.'
        return _settings_redirect('field-portal')
    tech.sign_pin_hash = hash_password(pin)
    sig = Signatory.query.filter_by(technician_id=tech.id, is_active=True).first()
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
        for candidate in Technician.query.filter(Technician.national_id.isnot(None)):
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

    row = Signatory.query.get_or_404(sig_id)
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


@app.route('/settings/save', methods=['POST'])
def settings_save():
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة لتعديل بيانات الشركة.'
        return _settings_redirect('company')
    s = get_app_settings()
    s.company_name    = request.form.get('company_name', '')
    s.company_name_en = request.form.get('company_name_en', '')
    s.phone           = request.form.get('phone', '')
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
    _save_company_logo(s, request.files.get('logo'))
    db.session.commit()
    session['settings_notice'] = 'تم حفظ بيانات الشركة بنجاح.'
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
    taken = User.query.filter(
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

    username = (request.form.get('username') or '').strip()
    full_name = (request.form.get('full_name') or '').strip()
    email = (request.form.get('email') or '').strip()
    role = (request.form.get('role') or 'viewer').strip()
    password = (request.form.get('password') or '').strip()
    auto_generate = request.form.get('auto_generate') == '1'

    if not username:
        session['settings_notice'] = 'اسم المستخدم مطلوب.'
        return _settings_redirect('users')

    if User.query.filter_by(username=username).first():
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
    db.session.add(user)
    db.session.commit()
    session['settings_notice'] = f'تم إنشاء المستخدم «{username}» بنجاح.'
    return _settings_redirect('users')


@app.route('/settings/users/edit/<int:user_id>', methods=['POST'])
def settings_user_edit(user_id):
    admin = require_admin()
    if not admin:
        return redirect(url_for('login'))
    target = User.query.get_or_404(user_id)
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
    target = User.query.get_or_404(user_id)
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

    expiring_list = Contract.query.filter(
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

    down_elevators = Elevator.query.filter(
        Elevator.status.in_(['متوقف', 'خارج الخدمة']),
    ).order_by(Elevator.code).limit(20).all()

    down_elevators_rows = []
    for e in down_elevators:
        last_visit = MaintenanceVisit.query.filter_by(
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

    contract_status = {label: 0 for label in ('نشط', 'على وشك الانتهاء', 'منتهي', 'ملغي')}

    class _ContractStatusRow:
        __slots__ = ('status', 'end_date')

        def __init__(self, status, end_date):
            self.status = status
            self.end_date = end_date

    for status, end_date in Contract.query.with_entities(Contract.status, Contract.end_date):
        label = contract_display_status(_ContractStatusRow(status, end_date))
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
    from sqlalchemy import extract
    year = int(request.args.get('year', datetime.now().year))
    c = Customer.query.get_or_404(customer_id)

    # العقود
    contracts = Contract.query.filter_by(customer_id=customer_id).all()

    # الزيارات
    visits = MaintenanceVisit.query.join(Elevator).filter(
        Elevator.customer_id == customer_id,
        extract('year', MaintenanceVisit.visit_date) == year
    ).all()

    # الأعطال
    faults = Fault.query.join(Elevator).filter(
        Elevator.customer_id == customer_id,
        extract('year', Fault.reported_at) == year
    ).all()

    # الإيرادات
    revenues = Revenue.query.filter(
        Revenue.customer_id == customer_id,
        extract('year', Revenue.revenue_date) == year
    ).all()

    # القطع
    parts = PartsBilling.query.filter(
        PartsBilling.customer_id == customer_id,
        extract('year', PartsBilling.billing_date) == year
    ).all()

    planned_visits = len(contracts) * 12  # تقديري
    done_visits    = len([v for v in visits if v.status == 'مكتملة'])
    solved_faults  = len([f for f in faults if f.status in ['تم الاصلاح', 'محلول', 'مغلق']])

    return jsonify({
        'customer': {
            'code':    c.code,
            'name':    c.name,
            'city':    c.city or '',
            'address': c.address or '',
            'phone':   c.phone or '',
        },
        'contracts': [{
            'code':       ct.code,
            'type':       ct.contract_type or '',
            'start':      str(ct.start_date or ''),
            'end':        str(ct.end_date or ''),
            'total':      ct.total or 0,
            'status':     ct.status,
        } for ct in contracts],
        'elevators': [{
            'code':      e.code,
            'type':      e.elev_type or '',
            'brand':     e.brand or '',
            'capacity':  str(e.capacity_kg or '') + ' كجم' if e.capacity_kg else '',
        } for e in c.elevators],
        'stats': {
            'planned_visits': planned_visits,
            'done_visits':    done_visits,
            'compliance':     round(done_visits/planned_visits*100) if planned_visits else 0,
            'total_faults':   len(faults),
            'solved_faults':  solved_faults,
            'fault_rate':     round(solved_faults/len(faults)*100) if faults else 100,
            'total_revenue':  sum(r.total for r in revenues),
        },
        'visits': [{
            'date':       str(v.visit_date or ''),
            'tech':       v.technician.name if v.technician else '—',
            'type':       v.visit_type or '',
            'works':      v.works_done or '',
            'status':     v.status,
        } for v in visits],
        'faults': [{
            'type':   f.fault_type or '',
            'date':   str(f.reported_at.date() if f.reported_at else ''),
            'status': f.status,
        } for f in faults],
        'parts': [{
            'description': p.description or '',
            'quantity':    1,
            'date':        str(p.billing_date or ''),
        } for p in parts],
    })
# =============================================
# موديول تركيب المصاعد
# =============================================
from installation import register_install_module
register_install_module(app)


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
    app.run(debug=True, port=5000)
