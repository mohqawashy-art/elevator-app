"""
LiftCore — Flask Application
app.py
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, g, send_from_directory, abort
from models import db, Customer, Elevator, Contract, ContractElevator, Technician, TechnicianDocument
from models import MaintenanceVisit, Fault, Revenue, Expense, Invoice
from models import InventoryItem, StockMovement, PartsBilling, Settings, User, Signatory
from models import PurchaseOrder, PurchaseOrderLine
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

db.init_app(app)

# موديول تركيب المصاعد (جداول منفصلة)
import installation.models  # noqa: F401, E402
from installation.config import install_module_enabled

PUBLIC_ENDPOINTS = frozenset({'login', 'logout', 'static', 'index', 'api_version'})
PUBLIC_PATH_PREFIXES = ('/field', '/static')


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


@app.before_request
def enforce_auth():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    path = request.path or ''
    for prefix in PUBLIC_PATH_PREFIXES:
        if path.startswith(prefix):
            return None
    user = current_user()
    if user:
        g.user = user
        return None
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


def brand_logo_url(settings=None):
    s = settings or get_app_settings()
    if s.logo_path:
        return url_for('static', filename=s.logo_path.replace('\\', '/'))
    return url_for('static', filename='logo.png')


ROLE_LABELS = {
    'admin': 'مدير النظام',
    'manager': 'مدير عمليات',
    'viewer': 'عرض فقط',
}

ROLE_LABELS_EN = {
    'admin': 'System Admin',
    'manager': 'Operations Manager',
    'viewer': 'View Only',
}


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

LIFTCORE_PRODUCT_LOGO = 'liftcore-header-logo.png'


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
    if user and getattr(user, 'theme', None) in ('dark', 'light'):
        theme = user.theme
    lang = resolve_user_language(user)
    role_label = ''
    if user:
        role_label = ROLE_LABELS.get(user.role, user.role)
        if lang == 'en':
            role_label = ROLE_LABELS_EN.get(user.role, role_label)
    return {
        'google_maps_api_key': os.environ.get('GOOGLE_MAPS_API_KEY', '').strip(),
        'brand_logo_url': brand_logo_url(s),
        'liftcore_logo_url': url_for('static', filename=LIFTCORE_PRODUCT_LOGO),
        'logo_width_sidebar': (getattr(s, 'logo_width_sidebar', None) or 150) if s else 150,
        'logo_width_report': (getattr(s, 'logo_width_report', None) or 150) if s else 150,
        'logo_width_login': (getattr(s, 'logo_width_login', None) or 180) if s else 180,
        'user_theme': theme,
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
    }


# إنشاء الجداول عند التشغيل الأول
with app.app_context():
    db.create_all()
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
            ],
            'settings': [
                ('checklist_template_key', 'VARCHAR(50)'),
                ('rep_name', 'VARCHAR(200)'),
                ('rep_mobile', 'VARCHAR(20)'),
                ('rep_national_id', 'VARCHAR(20)'),
                ('rep_signature_path', 'VARCHAR(300)'),
                ('rep_sign_pin_hash', 'VARCHAR(200)'),
                ('default_sign_method', 'VARCHAR(20)'),
                ('logo_width_sidebar', 'INTEGER'),
                ('logo_width_report', 'INTEGER'),
                ('logo_width_login', 'INTEGER'),
                ('address_en', 'TEXT'),
            ],
            'users': [
                ('theme', 'VARCHAR(10)'),
                ('language', 'VARCHAR(10)'),
                ('photo_path', 'VARCHAR(300)'),
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
                ('control_type', 'VARCHAR(50)'),
                ('control_drive', 'VARCHAR(50)'),
                ('control_operation', 'VARCHAR(50)'),
                ('control_detail', 'VARCHAR(200)'),
            ],
            'parts_billing': [
                ('visit_id', 'INTEGER'), ('fault_id', 'INTEGER'), ('paid_amount', 'FLOAT'),
            ],
            'invoices': [('paid_amount', 'FLOAT'), ('parts_billing_id', 'INTEGER')],
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
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Schema migration error: %s', exc)

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


def sync_customer_from_elevators(customer):
    if not customer:
        return
    n = len(customer.elevators)
    if n > 0:
        customer.status = customer_fleet_status(customer)


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
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = db_uri.replace('sqlite:///', '').replace('/', os.sep) if db_uri.startswith('sqlite:///') else ''
    db_info = {}
    if db_path and os.path.isfile(db_path):
        db_info = {
            'file': os.path.basename(os.path.dirname(db_path)) + '/' + os.path.basename(db_path),
            'bytes': os.path.getsize(db_path),
        }
        try:
            db_info['customers'] = Customer.query.count()
            db_info['elevators'] = Elevator.query.count()
        except Exception:
            pass
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
        },
    )


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


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if current_user():
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        login_id = request.form.get('email') or request.form.get('username')
        password = request.form.get('password') or ''
        user = _find_login_user(login_id)
        if user and verify_password(user.password_hash, password):
            if not password_is_hashed(user.password_hash):
                user.password_hash = hash_password(password)
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
            next_url = request.args.get('next') or ''
            if not next_url.startswith('/') or next_url.startswith('//'):
                next_url = url_for('dashboard')
            return redirect(next_url)
        error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =============================================
# الداشبورد — إحصائيات وتنبيهات ذكية
# =============================================
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
    return render_template(
        'dashboard.html',
        stats=stats,
        alerts=alerts,
    )


UNPAID_INVOICE_STATUSES = ['غير مدفوعة', 'غير مدفوع', 'متأخر', 'متأخرة', 'مدفوع جزئياً']
PAID_INVOICE_STATUSES = ['مدفوعة', 'مدفوع', 'محصّل']
OPEN_FAULT_STATUSES = ['مفتوح', 'قيد المعالجة']


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
        rows = [
            [i.code, (cust.name if cust else '—'),
             str(i.invoice_date), str(i.due_date or '—'),
             f'{i.total:,.0f} \u20c1' if i.total else '—', i.status]
            for i, cust in invs
        ]
        payload = {
            'title': 'الفواتير غير المدفوعة', 'link': '/invoices',
            'columns': ['الكود', 'العميل', 'التاريخ', 'الاستحقاق', 'الإجمالي', 'الحالة'],
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
        rows = [
            [i.code, cust.name if cust else '—', str(i.invoice_date),
             f'{i.total:,.0f} \u20c1' if i.total else '—', i.status]
            for i, cust in invs
        ]
        payload = {
            'title': 'إجمالي الفواتير', 'link': '/invoices',
            'columns': ['الكود', 'العميل', 'التاريخ', 'الإجمالي', 'الحالة'],
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
        rows = [
            [i.code, cust.name if cust else '—', str(i.due_date or '—'),
             f'{i.total:,.0f} \u20c1' if i.total else '—', i.status]
            for i, cust in invs
        ]
        payload = {
            'title': 'الفواتير المتأخرة', 'link': '/invoices',
            'columns': ['الكود', 'العميل', 'تاريخ الاستحقاق', 'الإجمالي', 'الحالة'],
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
    customers = Customer.query.order_by(Customer.id.desc()).all()
    return render_template(
        'clients.html',
        customers=customers,
        next_client_code=next_code(Customer, 'C-', digits=4),
    )


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
            'customer': cust.name if cust else '',
            'customer_name_en': (cust.name_en or '') if cust else '',
            'technician': v.technician.name if v.technician else '—',
            'tech_id': v.technician_id,
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
            'technician': f.technician.name if f.technician else '—',
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
            'pay_method': p.payment_method or '',
            'status': p.status or 'مكتملة',
            'visit_code': p.visit.code if p.visit else '',
            'fault_code': p.fault.code if p.fault else '',
            'notes': parts_billing_notes_display(p.notes),
        })
    return rows


def _visit_json(v):
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
        'technician': v.technician.name if v.technician else '—',
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
    elev = f.elevator
    visit = MaintenanceVisit.query.get(f.visit_id) if f.visit_id else None
    reported = f.reported_at.strftime('%Y-%m-%d') if f.reported_at else ''
    return {
        'id': f.id,
        'code': f.code,
        'visit_id': f.visit_id,
        'visit_code': visit.code if visit else '',
        'elevator_id': f.elevator_id,
        'elevator': elev.code if elev else '',
        'customer': elev.customer.name if elev and elev.customer else '',
        'customer_id': elev.customer_id if elev else None,
        'technician': f.technician.name if f.technician else '—',
        'fault_type': f.fault_type or '',
        'description': f.description or '',
        'priority': f.priority or 'عادية',
        'reported_at': reported,
        'response_time': f.response_time or '—',
        'status': f.status or '',
        'resolution': f.resolution or '',
        'billed': bool(f.billed),
        'notes': f.notes or '',
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
        'pay_method': p.payment_method or '',
        'status': p.status or 'مكتملة',
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
        status       = request.form.get('status','نشط'),
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
    c = Customer.query.get_or_404(id)
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
    if len(c.elevators) == 0:
        c.status = request.form.get('status', 'نشط')
    c.notes          = request.form.get('notes','')
    c.contact_role   = request.form.get('contact_role','')
    c.entity_type    = request.form.get('entity_type', 'فرد') or 'فرد'
    c.national_id    = request.form.get('national_id','')
    c.cr_number      = request.form.get('cr_number','')
    c.lat            = request.form.get('lat','')
    c.lng            = request.form.get('lng','')
    c.maps_url       = request.form.get('maps_url','')
    sync_customer_from_elevators(c)
    photo_err = _save_client_building_photo(c, request.files.get('building_photo'))
    db.session.commit()
    if photo_err:
        flash(photo_err, 'error')
    return redirect(url_for('clients'))

@app.route('/clients/delete/<int:id>', methods=['POST'])
def client_delete(id):
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


@app.route('/elevators')
def elevators():
    elevs = Elevator.query.order_by(Elevator.id.desc()).all()
    customers = Customer.query.order_by(Customer.name).all()
    return render_template(
        'elevators.html',
        elevators=elevs,
        customers=customers,
        next_elevator_code=next_code(Elevator, 'EL-', digits=4),
    )


@app.route('/elevators/add', methods=['POST'])
def elevator_add():
    e = Elevator(
        code            = next_code(Elevator, 'EL-', digits=4),
        customer_id     = request.form['customer_id'],
        building_name   = request.form.get('building_name', ''),
        city            = request.form.get('city', ''),
        district        = request.form.get('district', ''),
        elev_type       = request.form.get('elev_type', ''),
        brand           = request.form.get('brand', ''),
        model           = request.form.get('model', ''),
        capacity_kg     = request.form.get('capacity_kg') or None,
        floors          = request.form.get('floors') or None,
        serial_number   = request.form.get('serial_number', ''),
        machine_type    = request.form.get('machine_type', ''),
        control_type    = request.form.get('control_type', ''),
        control_drive   = request.form.get('control_drive', ''),
        control_operation = request.form.get('control_operation', ''),
        control_detail  = request.form.get('control_detail', ''),
        install_date    = _parse_date(request.form.get('install_date')),
        last_maintenance= _parse_date(request.form.get('last_maintenance')),
        next_maintenance= _parse_date(request.form.get('next_maintenance')),
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
    e = Elevator.query.get_or_404(id)
    e.customer_id      = request.form['customer_id']
    e.building_name    = request.form.get('building_name', '')
    e.city             = request.form.get('city', '')
    e.district         = request.form.get('district', '')
    e.elev_type        = request.form.get('elev_type', '')
    e.brand            = request.form.get('brand', '')
    e.model            = request.form.get('model', '')
    e.capacity_kg      = request.form.get('capacity_kg') or None
    e.floors           = request.form.get('floors') or None
    e.serial_number    = request.form.get('serial_number', '')
    e.machine_type     = request.form.get('machine_type', '')
    e.control_type     = request.form.get('control_type', '')
    e.control_drive      = request.form.get('control_drive', '')
    e.control_operation = request.form.get('control_operation', '')
    e.control_detail   = request.form.get('control_detail', '')
    e.install_date     = _parse_date(request.form.get('install_date'))
    e.last_maintenance = _parse_date(request.form.get('last_maintenance'))
    e.next_maintenance = _parse_date(request.form.get('next_maintenance'))
    e.status           = request.form.get('status', 'نشط')
    e.notes            = request.form.get('notes', '')
    sync_customer_from_elevators(e.customer)
    db.session.commit()
    return redirect(url_for('elevators'))

@app.route('/elevators/delete/<int:id>', methods=['POST'])
def elevator_delete(id):
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


def contract_invoice_status(contract):
    total = contract.total or 0
    paid = contract_paid_total(contract.id)
    if total <= 0:
        return 'غير مدفوع'
    if paid >= total - 0.01:
        return 'مدفوع'
    if paid > 0:
        return 'مدفوع جزئياً'
    return 'غير مدفوع'


def sync_contract_invoice_status(contract_id):
    if not contract_id:
        return
    c = Contract.query.get(contract_id)
    if c:
        c.invoice_status = contract_invoice_status(c)


def _money_round(n):
    return round(float(n or 0), 2)


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
    c.notes = form.get('notes', '')
    c.invoice_status = contract_invoice_status(c)


# =============================================
# العقود
# =============================================
@app.route('/contracts')
def contracts():
    contracts_list = Contract.query.order_by(Contract.id.desc()).all()
    customers = Customer.query.order_by(Customer.name).all()
    elev_lookup = {
        e.id: {'code': e.code, 'building': e.building_name or '', 'customer_id': e.customer_id}
        for e in Elevator.query.all()
    }
    return render_template(
        'contracts.html',
        contracts=contracts_list,
        customers=customers,
        elev_lookup=elev_lookup,
        next_contract_code=next_code(Contract, 'CN-', digits=5),
    )


@app.route('/contracts/edit/<int:id>', methods=['POST'])
def contract_edit(id):
    c = Contract.query.get_or_404(id)
    _apply_contract_form(c, request.form)
    _sync_contract_elevators(c.id, request.form.getlist('elevator_ids'))
    db.session.commit()
    return redirect(url_for('contracts'))


@app.route('/contracts/add', methods=['POST'])
def contract_add():
    c = Contract(code=next_code(Contract, 'CN-', digits=5))
    _apply_contract_form(c, request.form)
    db.session.add(c)
    db.session.flush()
    _sync_contract_elevators(c.id, request.form.getlist('elevator_ids'))
    db.session.commit()
    return redirect(url_for('contracts'))

@app.route('/contracts/delete/<int:id>', methods=['POST'])
def contract_delete(id):
    c = Contract.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('contracts'))


@app.route('/contracts/<int:contract_id>/print')
def contract_print_page(contract_id):
    from contract_print import contract_print_payload

    return render_template('contract-print.html', **contract_print_payload(contract_id))


# =============================================
# الفنيون
# =============================================
def technician_display_status(tech, today=None):
    today = today or date.today()
    raw = tech.status or 'متاح'
    if raw == 'نشط':
        raw = 'متاح'
    if raw in ('إجازة', 'غير نشط'):
        return raw
    busy_visit = MaintenanceVisit.query.filter(
        MaintenanceVisit.technician_id == tech.id,
        MaintenanceVisit.visit_date == today,
        MaintenanceVisit.status == 'جارٍ',
    ).count()
    open_fault = Fault.query.filter(
        Fault.technician_id == tech.id,
        Fault.status == 'قيد المعالجة',
    ).count()
    if busy_visit or open_fault:
        return 'مشغول'
    return raw if raw in ('متاح', 'مشغول') else 'متاح'


app.jinja_env.globals['technician_display_status'] = technician_display_status


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
    directory = os.path.join(app.root_path, 'static', 'uploads')
    full = os.path.normpath(os.path.join(directory, subpath))
    if not full.startswith(os.path.normpath(directory)) or not os.path.isfile(full):
        abort(404)
    return send_from_directory(directory, subpath)


app.jinja_env.globals['upload_url'] = upload_url


def _ext_ok(filename, allowed):
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in allowed


def _save_technician_signature(tech, file_storage, pin_plain=''):
    from signatory_service import upsert_signatory

    pin = str(pin_plain or '').strip()
    has_file = file_storage and file_storage.filename and _ext_ok(file_storage.filename, ALLOWED_TECH_PHOTO_EXT)
    existing = Signatory.query.filter_by(technician_id=tech.id, is_active=True).first()
    if not has_file and not pin and not existing:
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
    techs = Technician.query.order_by(Technician.id.desc()).all()
    unassigned_faults = Fault.query.filter(
        Fault.technician_id.is_(None),
        Fault.status.in_(['مفتوح', 'قيد المعالجة']),
    ).count()
    return render_template(
        'technicians.html',
        technicians=techs,
        next_tech_code=next_code(Technician, 'Tech-', digits=3),
        unassigned_faults=unassigned_faults,
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
        flash(str(exc), 'error')
        return redirect(url_for('technicians'))
    _save_technician_documents(
        t,
        request.files.getlist('documents'),
        request.form.getlist('doc_types'),
        request.form.getlist('doc_titles'),
    )
    db.session.commit()
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
        flash(str(exc), 'error')
        return redirect(url_for('technicians'))
    _save_technician_documents(
        t,
        request.files.getlist('documents'),
        request.form.getlist('doc_types'),
        request.form.getlist('doc_titles'),
    )
    db.session.commit()
    return redirect(url_for('technicians'))


@app.route('/technicians/documents/delete/<int:doc_id>', methods=['POST'])
def technician_document_delete(doc_id):
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
    from operations import list_districts, visit_alerts, visit_stats

    visits = MaintenanceVisit.query.order_by(MaintenanceVisit.visit_date.desc()).all()
    elevators = Elevator.query.all()
    customers = Customer.query.order_by(Customer.name).all()
    contracts = Contract.query.order_by(Contract.start_date.desc()).all()
    technicians = Technician.query.filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول'])
    ).all()
    today = date.today()
    plan_default = f'{today.year}-{today.month:02d}'
    month_end = today.replace(day=monthrange(today.year, today.month)[1])
    maint_techs = [t for t in technicians if (t.team or 'عام') in ('صيانة', 'عام')] or list(technicians)
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


@app.route('/maintenance-visits/add', methods=['POST'])
def visit_add():
    from entity_links import resolve_visit_links
    links = resolve_visit_links(
        request.form['elevator_id'],
        request.form.get('contract_id'),
        request.form.get('visit_date'),
    )
    from entity_links import link_fault_to_visit, lookup_fault

    fault_id = request.form.get('fault_id') or None
    fault_code = request.form.get('fault_code', '').strip()
    visit_type = request.form.get('visit_type', 'دورية')

    v = MaintenanceVisit(
        code          = next_code(MaintenanceVisit, 'VI-', digits=5),
        elevator_id   = links['elevator_id'],
        technician_id = request.form.get('technician_id') or None,
        contract_id   = links['contract_id'],
        visit_type    = visit_type,
        visit_date    = datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date(),
        visit_time    = request.form.get('visit_time',''),
        priority      = request.form.get('priority','عادية'),
        status        = request.form.get('status','مجدولة'),
        works_done    = request.form.get('works_done',''),
        observations  = request.form.get('observations',''),
        notes         = request.form.get('notes',''),
    )
    db.session.add(v)
    db.session.flush()

    fault = None
    if fault_id:
        fault = Fault.query.get(int(fault_id))
    elif fault_code:
        fault = lookup_fault(fault_code)
    elif 'عطل' in (visit_type or ''):
        fault = Fault(
            code=next_code(Fault, 'FA-', digits=5),
            elevator_id=v.elevator_id,
            technician_id=v.technician_id,
            fault_type=visit_type,
            description=v.works_done or v.observations or 'عطل سُجّل أثناء الزيارة',
            priority=v.priority or 'عادية',
            reported_at=datetime.combine(v.visit_date, datetime.min.time()),
            status='تم الاصلاح' if v.status == 'مكتملة' else 'قيد المعالجة',
            resolution=v.works_done or '',
        )
        db.session.add(fault)
        db.session.flush()

    if fault:
        link_fault_to_visit(fault, v)

    db.session.commit()
    return redirect(url_for('maintenance_visits'))
@app.route('/maintenance-visits/edit/<int:id>', methods=['POST'])
def visit_edit(id):
    from entity_links import resolve_visit_links
    v = MaintenanceVisit.query.get_or_404(id)
    links = resolve_visit_links(
        request.form['elevator_id'],
        request.form.get('contract_id'),
        request.form.get('visit_date'),
    )
    v.elevator_id   = links['elevator_id']
    v.contract_id   = links['contract_id']
    v.technician_id = request.form.get('technician_id') or None
    v.visit_type    = request.form.get('visit_type','')
    v.visit_date    = datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date()
    v.visit_time    = request.form.get('visit_time','')
    v.priority      = request.form.get('priority','عادية')
    v.status        = request.form.get('status','مجدولة')
    v.works_done    = request.form.get('works_done','')
    v.observations  = request.form.get('observations','')
    v.notes         = request.form.get('notes','')

    from entity_links import link_fault_to_visit, lookup_fault
    fault_id = request.form.get('fault_id') or None
    fault_code = request.form.get('fault_code', '').strip()
    fault = Fault.query.get(int(fault_id)) if fault_id else lookup_fault(fault_code)
    if fault:
        link_fault_to_visit(fault, v)

    db.session.commit()
    return redirect(url_for('maintenance_visits'))

@app.route('/maintenance-visits/delete/<int:id>', methods=['POST'])
def visit_delete(id):
    v = MaintenanceVisit.query.get_or_404(id)
    db.session.delete(v)
    db.session.commit()
    return redirect(url_for('maintenance_visits'))


@app.route('/api/maintenance/visits', methods=['GET'])
def api_maintenance_visits():
    """قائمة زيارات شهر معيّن — لتحديث الجدول بعد تخطيط الشهر."""
    month = request.args.get('month', '').strip()
    q = MaintenanceVisit.query.order_by(MaintenanceVisit.visit_date.desc())
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
    return jsonify(generate_district_plan(year, month, district))


@app.route('/api/maintenance/assign-visits', methods=['POST'])
def api_assign_visits():
    from operations import assign_visits_to_technician, get_plan

    data = request.get_json(silent=True) or request.form
    visit_ids = data.get('visit_ids') or []
    if isinstance(visit_ids, str):
        visit_ids = [x for x in visit_ids.split(',') if x.strip()]
    tech_id = data.get('technician_id')
    plan_month = data.get('plan_month', '').strip()
    if not visit_ids or not tech_id:
        return jsonify({'error': 'اختر الزيارات والفني'}), 400
    n = assign_visits_to_technician([int(x) for x in visit_ids], int(tech_id), plan_month)
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
    result = generate_monthly_plan(year, month, replace_draft=bool(data.get('replace')))
    return jsonify(result)


@app.route('/api/maintenance/assign-district', methods=['POST'])
def api_assign_district():
    from operations import assign_district_technician

    data = request.get_json(silent=True) or request.form
    from operations import assign_district_technician, get_plan

    plan_month = (data.get('plan_month') or '').strip()
    district = (data.get('district') or '').strip()
    n = assign_district_technician(
        plan_month,
        district,
        int(data.get('technician_id')),
        only_unassigned=bool(data.get('only_unassigned', True)),
    )
    result = {'updated': n}
    if plan_month:
        result.update(get_plan(plan_month))
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
# واجهة الفني — الجوال
# =============================================
@app.route('/field')
def field_home():
    tech_id = request.args.get('tech_id', type=int)
    technicians = Technician.query.filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول'])
    ).order_by(Technician.name).all()
    payload = None
    if tech_id:
        from operations import field_technician_payload
        payload = field_technician_payload(tech_id, request.url_root)
    return render_template(
        'field.html',
        technicians=technicians,
        tech_id=tech_id,
        payload=payload,
    )


@app.route('/field/visit/<int:visit_id>')
def field_visit(visit_id):
    from operations import field_visit_detail

    tech_id = request.args.get('tech_id', type=int)
    try:
        detail = field_visit_detail(visit_id, tech_id)
    except PermissionError as e:
        return render_template('field.html', error=str(e), technicians=[]), 403
    report_qs = f'?tech_id={tech_id}' if tech_id else ''
    detail['report_url'] = f'/field/visit/{visit_id}/report{report_qs}'
    return render_template('field-visit.html', visit=detail, tech_id=tech_id)


@app.route('/field/visit/<int:visit_id>/report')
def field_visit_report(visit_id):
    from operations import visit_report_payload

    tech_id = request.args.get('tech_id', type=int)
    try:
        payload = visit_report_payload(
            visit_id, editable=True, tech_id=tech_id, base_url=request.url_root
        )
    except PermissionError as e:
        return render_template('field.html', error=str(e), technicians=[]), 403
    payload['back_url'] = url_for('field_visit', visit_id=visit_id, tech_id=tech_id)
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

    tech_id = request.args.get('tech_id', type=int)
    try:
        detail = field_fault_detail(fault_id, tech_id)
    except PermissionError as e:
        return render_template('field.html', error=str(e), technicians=[]), 403
    return render_template('field-fault.html', fault=detail, tech_id=tech_id)


@app.route('/field/fault/<int:fault_id>/report')
def field_fault_report(fault_id):
    from operations import fault_report_payload

    tech_id = request.args.get('tech_id', type=int)
    try:
        payload = fault_report_payload(
            fault_id, editable=True, tech_id=tech_id, base_url=request.url_root
        )
    except PermissionError as e:
        return render_template('field.html', error=str(e), technicians=[]), 403
    payload['back_url'] = url_for('field_fault', fault_id=fault_id, tech_id=tech_id)
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

    data = request.get_json(silent=True) or {}
    national_id = (data.get('national_id') or '').strip()
    pin = (data.get('pin') or '').strip()
    role = (data.get('role') or 'technician').strip()
    visit_id = data.get('visit_id')
    visit_technician_id = None
    if visit_id:
        v = MaintenanceVisit.query.get(visit_id)
        if v:
            visit_technician_id = v.technician_id

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
    result['signed_at'] = datetime.utcnow().isoformat() + 'Z'
    return jsonify(result)


def _signature_data_url(relative_path: str) -> str:
    from signature_crypto import image_data_url, load_encrypted_signature

    if not relative_path:
        return ''
    rel = relative_path.replace('\\', '/')
    if rel.endswith('.enc'):
        try:
            raw = load_encrypted_signature(app.root_path, app.config['SECRET_KEY'], rel)
            return image_data_url(raw)
        except (FileNotFoundError, ValueError):
            return ''
    static_path = os.path.join(app.root_path, 'static', rel.replace('/', os.sep))
    if os.path.isfile(static_path):
        with open(static_path, 'rb') as fh:
            return image_data_url(fh.read())
    return upload_url(rel)


@app.route('/api/maintenance-visits/<int:visit_id>/report', methods=['POST'])
def api_save_visit_report(visit_id):
    from operations import save_visit_report

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

    complete_field_visit(
        visit_id,
        works_done=request.form.get('works_done', ''),
        observations=request.form.get('observations', ''),
        status=request.form.get('status', 'مكتملة'),
    )
    tech_id = request.form.get('tech_id')
    return redirect(url_for('field_home', tech_id=tech_id))


@app.route('/field/fault/<int:fault_id>/complete', methods=['POST'])
def field_fault_complete(fault_id):
    from operations import complete_field_fault

    complete_field_fault(
        fault_id,
        tech_notes=request.form.get('tech_notes', ''),
        resolution=request.form.get('resolution', ''),
        status=request.form.get('status', 'تم الاصلاح'),
    )
    tech_id = request.form.get('tech_id')
    return redirect(url_for('field_home', tech_id=tech_id))


@app.route('/field/fault/<int:fault_id>/request-parts', methods=['POST'])
def field_fault_request_parts(fault_id):
    from operations import request_fault_parts

    sell = float(request.form.get('sell_price') or 0)
    request_fault_parts(
        fault_id,
        description=request.form.get('parts_description', ''),
        sell_price=sell,
    )
    tech_id = request.form.get('tech_id')
    return redirect(url_for('field_home', tech_id=tech_id))


# =============================================
# الأعطال
# =============================================
@app.route('/faults')
def faults():
    from operations import fault_alerts, fault_stats

    faults = Fault.query.order_by(Fault.reported_at.desc()).all()
    elevators = Elevator.query.all()
    customers = Customer.query.order_by(Customer.name).all()
    inventory_items = InventoryItem.query.order_by(InventoryItem.name).all()
    technicians = Technician.query.filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول'])
    ).all()
    pending_wa = session.pop('pending_whatsapp', '')
    fault_techs = [t for t in technicians if (t.team or 'عام') in ('أعطال', 'عام')] or list(technicians)
    return render_template(
        'faults.html',
        faults=faults,
        elevators=elevators,
        customers=customers,
        technicians=technicians,
        faults_js=_faults_js_list(faults),
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

    f = Fault.query.get_or_404(id)
    f.elevator_id   = request.form['elevator_id']
    f.technician_id = request.form.get('technician_id') or None
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
    _apply_fault_billing_from_form(f, request.form)
    db.session.commit()
    return redirect(url_for('faults'))

@app.route('/faults/add', methods=['POST'])
def fault_add():
    from entity_links import link_fault_to_visit, lookup_visit
    from operations import dispatch_fault

    billable = request.form.get('billable', 'no')
    client_report = request.form.get('client_report') or request.form.get('description', '')
    reported = _parse_reported_at(request.form.get('reported_at'))
    f = Fault(
        code          = next_code(Fault, 'FA-', digits=5),
        elevator_id   = request.form['elevator_id'],
        technician_id = request.form.get('technician_id') or None,
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

    visit_code = request.form.get('visit_code', '').strip()
    if visit_code:
        visit = lookup_visit(visit_code)
        if visit:
            link_fault_to_visit(f, visit)

    _apply_fault_billing_from_form(f, request.form)
    db.session.commit()

    if f.technician_id:
        base = request.url_root
        result = dispatch_fault(f.id, base)
        if result.get('whatsapp_url'):
            session['pending_whatsapp'] = result['whatsapp_url']
    return redirect(url_for('faults'))

@app.route('/faults/delete/<int:id>', methods=['POST'])
def fault_delete(id):
    f = Fault.query.get_or_404(id)
    db.session.delete(f)
    db.session.commit()
    return redirect(url_for('faults'))

# =============================================
# الإيرادات
# =============================================
@app.route('/revenues')
def revenues():
    revs = Revenue.query.order_by(Revenue.revenue_date.desc()).all()
    customers = Customer.query.all()
    return render_template('revenues.html', revenues=revs, customers=customers)

def _revenue_from_form(form, existing: Revenue | None = None):
    from customer_billing import apply_payment_to_source

    amount = float(form.get('amount', 0) or 0)
    tax = round(amount * 0.15, 2)
    total = round(amount + tax, 2)
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
    r = Revenue.query.get_or_404(id)
    old_contract_id = r.contract_id
    _revenue_from_form(request.form, existing=r)
    sync_contract_invoice_status(r.contract_id)
    if old_contract_id and old_contract_id != r.contract_id:
        sync_contract_invoice_status(old_contract_id)
    db.session.commit()
    return redirect(url_for('revenues'))

@app.route('/revenues/add', methods=['POST'])
def revenue_add():
    r = _revenue_from_form(request.form)
    db.session.flush()
    sync_contract_invoice_status(r.contract_id)
    db.session.commit()
    return redirect(url_for('revenues'))

@app.route('/revenues/delete/<int:id>', methods=['POST'])
def revenue_delete(id):
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
    return render_template('expenses.html', expenses=exps)
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
    e = Expense.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    return redirect(url_for('expenses'))

# =============================================
# الفواتير
# =============================================
@app.route('/invoices')
def invoices():
    invs = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
    customers = Customer.query.all()
    return render_template('invoices.html', invoices=invs, customers=customers)

@app.route('/invoices/edit/<int:id>', methods=['POST'])
def invoice_edit(id):
    i = Invoice.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    tax = amount * 0.15
    i.invoice_type   = request.form.get('invoice_type', 'فاتورة ضريبية')
    i.customer_id    = request.form.get('customer_id') or None
    i.invoice_date   = datetime.strptime(request.form['invoice_date'], '%Y-%m-%d').date()
    i.due_date       = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date() if request.form.get('due_date') else None
    i.description    = request.form.get('description','')
    i.amount         = amount
    i.tax_amount     = tax
    i.total          = amount + tax
    i.payment_method = request.form.get('payment_method','')
    i.status         = request.form.get('status','غير مدفوعة')
    i.notes          = request.form.get('notes','')
    sync_contract_invoice_status(i.contract_id)
    db.session.commit()
    return redirect(url_for('invoices'))

@app.route('/invoices/add', methods=['POST'])
def invoice_add():
    amount = float(request.form.get('amount', 0) or 0)
    tax = round(amount * 0.15, 2)
    total = round(amount + tax, 2)
    source_type = (request.form.get('source_type') or '').strip()
    source_id = (request.form.get('source_id') or '').strip()
    customer_id = request.form.get('customer_id') or None
    contract_id = request.form.get('contract_id') or None
    parts_billing_id = None
    notes = request.form.get('notes', '')

    if source_type == 'parts_billing' and source_id:
        pb = PartsBilling.query.get_or_404(int(source_id))
        if Invoice.query.filter_by(parts_billing_id=pb.id).first():
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

    due_raw = request.form.get('due_date', '').strip()
    invoice_status = request.form.get('status', 'غير مدفوعة')
    invoice_paid = 0.0
    if source_type == 'parts_billing' and source_id:
        pb = PartsBilling.query.get(int(source_id))
        if pb and (pb.paid_amount or 0) >= (pb.sell_price or 0) - 0.01:
            invoice_paid = total
            if invoice_status in ('', 'غير مدفوعة'):
                invoice_status = 'مدفوعة'
    elif source_type == 'contract' and source_id:
        from customer_billing import contract_paid_amount
        c = Contract.query.get(int(source_id))
        if c and contract_paid_amount(c.id) >= (c.total or 0) - 0.01:
            invoice_paid = total
            if invoice_status in ('', 'غير مدفوعة'):
                invoice_status = 'مدفوعة'

    i = Invoice(
        code=next_code(Invoice, 'INV-', digits=4),
        invoice_type=request.form.get('invoice_type', 'فاتورة ضريبية'),
        customer_id=int(customer_id) if customer_id else None,
        contract_id=int(contract_id) if contract_id else None,
        parts_billing_id=parts_billing_id,
        invoice_date=datetime.strptime(request.form['invoice_date'], '%Y-%m-%d').date(),
        due_date=datetime.strptime(due_raw, '%Y-%m-%d').date() if due_raw else None,
        description=request.form.get('description', ''),
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
    sync_contract_invoice_status(i.contract_id)
    db.session.commit()
    return redirect(url_for('invoices'))

@app.route('/invoices/<int:invoice_id>/print')
def invoice_print_page(invoice_id):
    from invoice_print import invoice_print_payload

    return render_template('invoice-print.html', **invoice_print_payload(invoice_id))


@app.route('/invoices/delete/<int:id>', methods=['POST'])
def invoice_delete(id):
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
    from seed_inventory_parts import ensure_inventory_catalog

    ensure_inventory_catalog()
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
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('inventory'))


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
    order = PurchaseOrder.query.get_or_404(order_id)
    if order.status == 'مستلم':
        return redirect(url_for('purchase_orders'))
    db.session.delete(order)
    db.session.commit()
    return redirect(url_for('purchase_orders'))

# =============================================
# حركة المخزن
# =============================================
@app.route('/stock-movements')
def stock_movements():
    movements = StockMovement.query.order_by(StockMovement.movement_date.desc()).all()
    items = InventoryItem.query.all()
    technicians = Technician.query.filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).all()
    return render_template('stock-movements.html', movements=movements, items=items, technicians=technicians)

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

    # تحديث الرصيد
    item = InventoryItem.query.get(item_id)
    if direction == 'وارد':
        item.current_qty += qty
    else:
        item.current_qty -= qty

    db.session.commit()
    return redirect(url_for('stock_movements'))

@app.route('/stock-movements/delete/<int:id>', methods=['POST'])
def stock_delete(id):
    m = StockMovement.query.get_or_404(id)
    db.session.delete(m)
    db.session.commit()
    return redirect(url_for('stock_movements'))

# =============================================
# بيان القطع
# =============================================
@app.route('/parts-billing')
def parts_billing():
    from operations import parts_alerts, parts_stats

    parts = PartsBilling.query.order_by(PartsBilling.billing_date.desc()).all()
    customers = Customer.query.order_by(Customer.name).all()
    contracts = Contract.query.order_by(Contract.code).all()
    pending_faults = Fault.query.filter_by(status='انتظار قطع').order_by(
        Fault.reported_at.desc()
    ).all()
    return render_template(
        'parts-billing.html',
        parts=parts,
        parts_js=_parts_js_list(parts),
        customers=customers,
        contracts=contracts,
        customers_js=[{'id': c.id, 'name': c.name} for c in customers],
        contracts_js=[{'id': c.id, 'code': c.code, 'customer_id': c.customer_id} for c in contracts],
        next_part_code=next_code(PartsBilling, 'PB-', digits=3),
        parts_workflow_stats=parts_stats(),
        parts_alerts=parts_alerts(),
        pending_faults=pending_faults,
    )

@app.route('/parts-billing/edit/<int:id>', methods=['POST'])
def parts_edit(id):
    from entity_links import normalize_parts_status, resolve_parts_links
    p = PartsBilling.query.get_or_404(id)
    cost  = float(request.form.get('cost_price', 0))
    sell  = float(request.form.get('sell_price', 0))
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
    p.billing_date   = datetime.strptime(request.form['billing_date'], '%Y-%m-%d').date()
    p.description    = request.form.get('description','')
    p.cost_price     = cost
    p.sell_price     = sell
    p.profit         = sell - cost
    p.payment_method = request.form.get('payment_method','')
    p.status         = normalize_parts_status(request.form.get('status', ''))
    p.notes          = request.form.get('notes','')
    if links['fault_id']:
        fault = Fault.query.get(links['fault_id'])
        if fault:
            fault.billed = True
    db.session.commit()
    return redirect(url_for('parts_billing'))

@app.route('/parts-billing/add', methods=['POST'])
def parts_add():
    from entity_links import normalize_parts_status, resolve_parts_links
    cost  = float(request.form.get('cost_price', 0))
    sell  = float(request.form.get('sell_price', 0))
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
        billing_date  = datetime.strptime(request.form['billing_date'], '%Y-%m-%d').date(),
        description   = request.form.get('description',''),
        cost_price    = cost,
        sell_price    = sell,
        profit        = sell - cost,
        payment_method= request.form.get('payment_method',''),
        status        = normalize_parts_status(request.form.get('status', '')),
        notes         = request.form.get('notes',''),
    )
    db.session.add(p)
    if links['fault_id']:
        fault = Fault.query.get(links['fault_id'])
        if fault:
            fault.billed = True
    db.session.commit()
    return redirect(url_for('parts_billing'))

@app.route('/parts-billing/delete/<int:id>', methods=['POST'])
def parts_delete(id):
    p = PartsBilling.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for('parts_billing'))

# =============================================
# التقارير
# =============================================
@app.route('/reports')
def reports():
    return render_template('reports.html')

@app.route('/reports/dashboard')
def report_dashboard():
    return render_template('report-dashboard.html')

@app.route('/reports/client-annual')
def report_client_annual():
    customers = Customer.query.all()
    return render_template('report-annual.html', customers=customers)

@app.route('/reports/clients')
def report_clients():
    return render_template('report-clients.html')

@app.route('/reports/elevators')
def report_elevators():
    return render_template('report-elevators.html')

@app.route('/reports/contracts')
def report_contracts():
    return render_template('report-contracts.html')

@app.route('/reports/technicians')
def report_technicians():
    return render_template('report-technicians.html')

@app.route('/reports/maintenance-visits')
def report_maintenance():
    return render_template('report-maintenance.html')

@app.route('/reports/faults')
def report_faults():
    return render_template('report-faults.html')

@app.route('/reports/revenues')
def report_revenues():
    return render_template('report-revenues.html')

@app.route('/reports/expenses')
def report_expenses():
    return render_template('report-expenses.html')

@app.route('/reports/invoices')
def report_invoices():
    return render_template('report-invoices.html')

@app.route('/reports/inventory')
def report_inventory():
    return render_template('report-inventory.html')

@app.route('/reports/stock-movements')
def report_stock():
    return render_template('report-stock.html')

@app.route('/reports/parts-billing')
def report_parts():
    return render_template('report-parts.html')

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


with app.app_context():
    try:
        _migrate_plain_text_passwords()
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
    return render_template(
        'settings.html',
        settings=s,
        users=users,
        signatories=signatories,
        current_user=user,
        active_tab=request.args.get('tab', 'company'),
        edit_user=edit_user,
        settings_notice=session.pop('settings_notice', None),
        generated_username=session.pop('settings_generated_username', None),
        generated_password=session.pop('settings_generated_password', None),
    )


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
        upsert_signatory(
            name=name,
            national_id=national_id,
            role=role,
            pin_plain=pin,
            pin_hash_fn=hash_password,
            image_bytes=file_storage.read(),
            app_root=app.root_path,
            secret=app.config['SECRET_KEY'],
        )
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
    if not require_admin():
        session['settings_notice'] = 'صلاحية المدير مطلوبة.'
        return _settings_redirect('signatures')
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
    try:
        s.tax_pct = float(request.form.get('tax_pct', 15))
    except ValueError:
        s.tax_pct = 15
    s.currency        = request.form.get('currency', 'SAR')
    s.language        = request.form.get('language', 'ar')
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
    theme = (request.form.get('theme') or 'dark').strip()
    if theme not in ('dark', 'light'):
        theme = 'dark'
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

    if role not in ('admin', 'manager', 'viewer'):
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
    if role not in ('admin', 'manager', 'viewer'):
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
    user = require_login()
    if not user:
        return redirect(url_for('login'))

    current = request.form.get('current_password') or ''
    new_pass = (request.form.get('new_password') or '').strip()
    confirm = (request.form.get('confirm_password') or '').strip()

    if not verify_password(user.password_hash, current):
        session['settings_notice'] = 'كلمة المرور الحالية غير صحيحة.'
        return _settings_redirect('account')

    if len(new_pass) < 6:
        session['settings_notice'] = 'كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل.'
        return _settings_redirect('account')

    if new_pass != confirm:
        session['settings_notice'] = 'تأكيد كلمة المرور غير متطابق.'
        return _settings_redirect('account')

    user.password_hash = hash_password(new_pass)
    db.session.commit()
    session['settings_notice'] = 'تم تغيير كلمة المرور بنجاح.'
    return _settings_redirect('account')

# =============================================
# API للداشبورد (بيانات حقيقية)
# =============================================
@app.route('/api/dashboard')
def api_dashboard():
    from sqlalchemy import extract
    year = int(request.args.get('year', datetime.now().year))

    # إيرادات شهرية
    monthly_rev = []
    monthly_exp = []
    for m in range(1, 13):
        rev = db.session.query(db.func.sum(Revenue.total)).filter(
            extract('year', Revenue.revenue_date) == year,
            extract('month', Revenue.revenue_date) == m
        ).scalar() or 0
        exp = db.session.query(db.func.sum(Expense.amount)).filter(
            extract('year', Expense.expense_date) == year,
            extract('month', Expense.expense_date) == m
        ).scalar() or 0
        monthly_rev.append(round(rev, 2))
        monthly_exp.append(round(exp, 2))

    stats, alerts = get_dashboard_stats()

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
        'expiring_contracts': alerts['expiring_contracts_count'],
        'low_stock':          alerts['low_stock_count'],
        'monthly_revenue': monthly_rev,
        'monthly_expenses': monthly_exp,
        'elev_status': {
            'نشط':          Elevator.query.filter_by(status='نشط').count(),
            'تحت الصيانة':  Elevator.query.filter_by(status='تحت الصيانة').count(),
            'متوقف':        Elevator.query.filter_by(status='متوقف').count(),
            'خارج الخدمة':  Elevator.query.filter_by(status='خارج الخدمة').count(),
        },
        'contract_status': {
            label: sum(1 for c in Contract.query.all() if contract_display_status(c) == label)
            for label in ('نشط', 'على وشك الانتهاء', 'منتهي', 'ملغي')
        },
    })
# =============================================
# أضف هذه الـ routes في app.py
# تحت قسم التقارير الموجود
# =============================================

@app.route('/api/reports/clients')
def api_report_clients():
    customers = Customer.query.order_by(Customer.id).all()
    return jsonify([{
        'code':     c.code,
        'name':     c.name,
        'city':     c.city or '',
        'district': c.district or '',
        'phone':    c.phone or '',
        'elevators':len(c.elevators),
        'contracts':len(c.contracts),
        'contract_status': contract_display_status(c.contracts[0]) if c.contracts else 'بدون عقد',
        'status':   c.status,
    } for c in customers])


@app.route('/api/reports/elevators')
def api_report_elevators():
    elevs = Elevator.query.order_by(Elevator.id).all()
    return jsonify([{
        'code':       e.code,
        'customer':   e.customer.name,
        'building':   e.building_name or '',
        'city':       e.city or '',
        'elev_type':  e.elev_type or '',
        'brand':      e.brand or '',
        'capacity':   str(e.capacity_kg or '') + ' كجم' if e.capacity_kg else '',
        'status':     e.status,
        'next_maint': str(e.next_maintenance or ''),
    } for e in elevs])


@app.route('/api/reports/contracts')
def api_report_contracts():
    contracts = Contract.query.order_by(Contract.id).all()
    return jsonify([{
        'code':          c.code,
        'customer':      c.customer.name,
        'contract_type': c.contract_type or '',
        'start_date':    str(c.start_date or ''),
        'end_date':      str(c.end_date or ''),
        'elevators':     len(c.elevators),
        'value':         c.value or 0,
        'total':         c.total or 0,
        'status':        c.status,
        'inv_status':    c.invoice_status or '',
    } for c in contracts])


@app.route('/api/reports/technicians')
def api_report_technicians():
    techs = Technician.query.order_by(Technician.id).all()
    return jsonify([{
        'code':           t.code,
        'name':           t.name,
        'phone':          t.phone or '',
        'job_title':      t.job_title or '',
        'specialization': t.specialization or '',
        'city':           t.city or '',
        'status':         t.status,
        'emergency':      'نعم' if t.emergency else 'لا',
        'visits':         len(t.visits),
    } for t in techs])


@app.route('/api/reports/visits')
def api_report_visits():
    visits = MaintenanceVisit.query.order_by(MaintenanceVisit.visit_date.desc()).all()
    return jsonify([{
        'code':       v.code,
        'customer':   v.elevator.customer.name,
        'elevator':   v.elevator.code,
        'technician': v.technician.name if v.technician else '—',
        'visit_type': v.visit_type or '',
        'visit_date': str(v.visit_date or ''),
        'priority':   v.priority or '',
        'status':     v.status,
    } for v in visits])


@app.route('/api/reports/faults')
def api_report_faults():
    faults = Fault.query.order_by(Fault.reported_at.desc()).all()
    return jsonify([{
        'code':       f.code,
        'customer':   f.elevator.customer.name,
        'elevator':   f.elevator.code,
        'fault_type': f.fault_type or '',
        'priority':   f.priority or '',
        'technician': f.technician.name if f.technician else '—',
        'response':   f.response_time or '—',
        'status':     f.status,
        'billed':     'مفوتر' if f.billed else 'غير مفوتر',
    } for f in faults])


@app.route('/api/reports/revenues')
def api_report_revenues():
    from sqlalchemy import extract
    year  = request.args.get('year', datetime.now().year)
    month = request.args.get('month', '')
    q = Revenue.query
    if year:  q = q.filter(extract('year',  Revenue.revenue_date) == int(year))
    if month: q = q.filter(extract('month', Revenue.revenue_date) == int(month))
    revs = q.order_by(Revenue.revenue_date.desc()).all()
    return jsonify([{
        'code':         r.code,
        'customer':     r.customer.name if r.customer else '—',
        'contract':     r.contract.code if r.contract else '—',
        'date':         str(r.revenue_date or ''),
        'revenue_type': r.revenue_type or '',
        'pay_method':   r.payment_method or '',
        'amount':       r.amount or 0,
        'tax':          r.tax_amount or 0,
        'total':        r.total or 0,
        'status':       r.status or '',
    } for r in revs])


@app.route('/api/reports/expenses')
def api_report_expenses():
    from sqlalchemy import extract
    year  = request.args.get('year', datetime.now().year)
    month = request.args.get('month', '')
    q = Expense.query
    if year:  q = q.filter(extract('year',  Expense.expense_date) == int(year))
    if month: q = q.filter(extract('month', Expense.expense_date) == int(month))
    exps = q.order_by(Expense.expense_date.desc()).all()
    return jsonify([{
        'code':         e.code,
        'date':         str(e.expense_date or ''),
        'expense_type': e.expense_type or '',
        'description':  e.description or '',
        'responsible':  e.responsible or '',
        'pay_method':   e.payment_method or '',
        'amount':       e.amount or 0,
    } for e in exps])


@app.route('/api/reports/invoices')
def api_report_invoices():
    invs = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
    return jsonify([{
        'code':         i.code,
        'invoice_type': i.invoice_type or '',
        'customer':     i.customer.name if i.customer else '—',
        'contract':     i.contract.code if i.contract else '—',
        'date':         str(i.invoice_date or ''),
        'description':  i.description or '',
        'amount':       i.amount or 0,
        'tax':          i.tax_amount or 0,
        'total':        i.total or 0,
        'pay_method':   i.payment_method or '',
        'status':       i.status or '',
    } for i in invs])


@app.route('/api/reports/inventory')
def api_report_inventory():
    items = InventoryItem.query.order_by(InventoryItem.id).all()
    return jsonify([{
        'code':        i.code,
        'name':        i.name,
        'category':    i.category or '',
        'current_qty': i.current_qty or 0,
        'unit':        i.unit or '',
        'min_qty':     i.min_qty or 0,
        'buy_price':   i.buy_price or 0,
        'stock_value': i.stock_value,
        'supplier':    i.supplier or '',
        'order_status':i.order_status,
    } for i in items])


@app.route('/api/reports/stock')
def api_report_stock():
    movements = StockMovement.query.order_by(StockMovement.movement_date.desc()).all()
    return jsonify([{
        'code':          m.code,
        'date':          str(m.movement_date or ''),
        'direction':     m.direction or '',
        'movement_type': m.movement_type or '',
        'item':          m.item.name,
        'item_code':     m.item.code,
        'quantity':      m.quantity or 0,
        'unit_price':    m.unit_price or 0,
        'total_value':   m.total_value or 0,
        'technician':    m.technician.name if m.technician else '—',
        'reason':        m.reason or '',
    } for m in movements])


@app.route('/api/reports/parts')
def api_report_parts():
    parts = PartsBilling.query.order_by(PartsBilling.billing_date.desc()).all()
    return jsonify([{
        'code':       p.code,
        'customer':   p.customer.name if p.customer else '—',
        'contract':   p.contract.code if p.contract else '—',
        'date':       str(p.billing_date or ''),
        'description':p.description or '',
        'cost_price': p.cost_price or 0,
        'sell_price': p.sell_price or 0,
        'profit':     p.profit or 0,
        'pay_method': p.payment_method or '',
        'status':     p.status or '',
    } for p in parts])


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
