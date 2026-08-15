"""
LiftCore — نماذج قاعدة البيانات
models.py
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()


# =============================================
# 0. المؤسسات (multi-tenant)
# =============================================
class Organization(db.Model):
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(63), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    name_en = db.Column(db.String(200))
    status = db.Column(db.String(20), default='trial')  # trial | active | suspended
    plan = db.Column(db.String(30), default='basic')
    admin_email = db.Column(db.String(100))
    trial_ends_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    suspended_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    # اشتراك المنصة (يدوي — بدون بوابة دفع بعد)
    billing_cycle = db.Column(db.String(20), default='monthly')  # monthly | yearly
    billing_amount = db.Column(db.Float)  # ر.س للفترة — فارغ = سعر الباقة الافتراضي
    billing_status = db.Column(db.String(20), default='ok')  # ok | due | overdue | complimentary
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    last_payment_at = db.Column(db.DateTime)
    last_payment_amount = db.Column(db.Float)
    last_payment_ref = db.Column(db.String(100))
    billing_notes = db.Column(db.Text)

    # تجاوزات حدود الباقة (فارغ = استخدم الباقة + الإضافات)
    elevators_limit_override = db.Column(db.Integer)
    office_users_limit_override = db.Column(db.Integer)
    technicians_limit_override = db.Column(db.Integer)
    storage_gb_limit_override = db.Column(db.Integer)

    def __repr__(self):
        return f'<Organization {self.slug}>'


class PlatformPayment(db.Model):
    """سجل دفعات اشتراك العملاء لـ LiftCore (يدوي من لوحة المنصة)."""
    __tablename__ = 'platform_payments'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='SAR')
    method = db.Column(db.String(40), default='transfer')  # transfer | cash | card | complimentary | other
    reference = db.Column(db.String(100))
    note = db.Column(db.Text)
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    plan = db.Column(db.String(30))
    recorded_by_user_id = db.Column(db.Integer)
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PlatformPayment org={self.organization_id} {self.amount}>'


class OrganizationAddon(db.Model):
    """إضافات اشتراك لكل مؤسسة (تُدار من لوحة المنصة)."""
    __tablename__ = 'organization_addons'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    addon_key = db.Column(db.String(50), nullable=False, index=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price_monthly = db.Column(db.Float)
    status = db.Column(db.String(20), default='active')  # active | cancelled
    note = db.Column(db.Text)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime)
    created_by_user_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<OrganizationAddon org={self.organization_id} {self.addon_key} x{self.quantity}>'


class TenantMixin:
    """Mixin — organization_id على كل جدول تشغيلي."""

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey('organizations.id'),
        nullable=False,
        index=True,
    )


# =============================================
# 0b. دعوات الانضمام (منصة المشغّل)
# =============================================
class OnboardingInvite(db.Model):
    """دعوة يرسلها المشغّل للعميل لملء بيانات الشركة قبل التفعيل."""
    __tablename__ = 'onboarding_invites'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default='pending')  # pending | submitted | activated | expired | cancelled
    plan = db.Column(db.String(30), default='basic')
    suggested_slug = db.Column(db.String(63))
    contact_email = db.Column(db.String(100))
    contact_name = db.Column(db.String(100))
    notes = db.Column(db.Text)
    expires_at = db.Column(db.DateTime)
    created_by_user_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    activated_at = db.Column(db.DateTime)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))

    # بيانات يملأها العميل
    company_name = db.Column(db.String(200))
    company_name_en = db.Column(db.String(200))
    cr_number = db.Column(db.String(50))
    vat_number = db.Column(db.String(50))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(100))
    city = db.Column(db.String(100))
    address = db.Column(db.Text)
    admin_name = db.Column(db.String(100))
    admin_email = db.Column(db.String(100))
    admin_phone = db.Column(db.String(30))
    preferred_slug = db.Column(db.String(63))
    # بعد التفعيل — مرجع دائم للمشغّل
    admin_username = db.Column(db.String(50))
    login_url = db.Column(db.String(300))
    credentials_email_sent_at = db.Column(db.DateTime)
    credentials_email_error = db.Column(db.String(300))

    def __repr__(self):
        return f'<OnboardingInvite {self.token[:8]}… {self.status}>'


# =============================================
# 0c. طلبات التجربة / عروض السعر (من صفحات التسويق)
# =============================================
class SalesLead(db.Model):
    """طلب من الصفحة التعريفية/الأسعار — يظهر في لوحة المنصة + يُرسل إيميل."""
    __tablename__ = 'sales_leads'

    id = db.Column(db.Integer, primary_key=True)
    request_type = db.Column(db.String(20), default='demo')  # demo | quote
    status = db.Column(db.String(20), default='new')  # new | contacted | fulfilled | closed
    company_name = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    contact_email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(40))
    city = db.Column(db.String(100))
    elevators = db.Column(db.String(40))
    notes = db.Column(db.Text)
    source_path = db.Column(db.String(40))  # / | /pricing | /product | /start
    utm_source = db.Column(db.String(80))
    utm_medium = db.Column(db.String(80))
    utm_campaign = db.Column(db.String(120))
    gclid = db.Column(db.String(120))
    email_sent = db.Column(db.Boolean, default=False)
    email_error = db.Column(db.String(300))
    fulfilled_at = db.Column(db.DateTime)
    result_org_id = db.Column(db.Integer)
    customer_mail_sent = db.Column(db.Boolean, default=False)
    action_note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SalesLead {self.id} {self.request_type} {self.status}>'


# =============================================
# 1. العملاء
# =============================================
class Customer(TenantMixin, db.Model):
    __tablename__ = 'customers'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_customer_org_code'),
    )

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(20), nullable=False)   # C-0001
    name        = db.Column(db.String(200), nullable=False)
    name_en     = db.Column(db.String(200))
    city        = db.Column(db.String(100))
    district    = db.Column(db.String(100))
    address     = db.Column(db.Text)
    phone       = db.Column(db.String(40))
    phone2      = db.Column(db.String(40))
    # أرقام إضافية JSON: [{"label":"المحاسب","number":"+9665..."}, ...]
    extra_phones = db.Column(db.Text)
    email       = db.Column(db.String(100))
    contact_person = db.Column(db.String(100))
    status      = db.Column(db.String(20), default='نشط')   # نشط / غير نشط
    notes       = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    contact_role = db.Column(db.String(50))
    entity_type  = db.Column(db.String(20), default='فرد')   # فرد / شركة
    national_id  = db.Column(db.String(20))
    cr_number    = db.Column(db.String(50))   # السجل التجاري
    vat_number   = db.Column(db.String(50))   # الرقم الضريبي (B2B / ZATCA)
    national_address = db.Column(db.String(200))  # العنوان الوطني للفواتير الضريبية
    lat          = db.Column(db.String(20))
    lng          = db.Column(db.String(20))
    maps_url     = db.Column(db.String(500))
    building_photo_path = db.Column(db.String(300))  # uploads/clients/{id}/building.jpg
    # علاقات
    elevators   = db.relationship('Elevator',  backref='customer', lazy=True)
    contracts   = db.relationship('Contract',  backref='customer', lazy=True)

    def __repr__(self):
        return f'<Customer {self.code} {self.name}>'


# =============================================
# 2. المصاعد
# =============================================
class Elevator(TenantMixin, db.Model):
    __tablename__ = 'elevators'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_elevator_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # EL-0001
    customer_id     = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    building_name   = db.Column(db.String(200))
    city            = db.Column(db.String(100))
    district        = db.Column(db.String(100))
    address         = db.Column(db.Text)
    elev_type       = db.Column(db.String(100))   # مصعد ركاب / بضائع / مستشفى
    brand           = db.Column(db.String(100))   # Otis / Kone / Schindler
    model           = db.Column(db.String(100))
    capacity_kg     = db.Column(db.Integer)
    capacity_persons= db.Column(db.Integer)
    floors          = db.Column(db.Integer)
    stops           = db.Column(db.Integer)
    doors_count     = db.Column(db.Integer)
    speed           = db.Column(db.String(50))
    machine_type    = db.Column(db.String(30))    # MR / MRL / Hydraulic
    door_type       = db.Column(db.String(50))    # نصف أوتوماتيك / أوتوماتيك / سنتر أوتوماتيك / تلسكوبي
    control_type    = db.Column(db.String(50))    # Relay / PLC / VVVF
    control_drive   = db.Column(db.String(50))    # AC VVVF / Hydraulic / DC
    control_operation = db.Column(db.String(50))  # Simplex / Group / Destination
    control_detail  = db.Column(db.String(200))   # Otis Gen2, Kone KCM...
    serial_number   = db.Column(db.String(100))
    install_date    = db.Column(db.Date)
    warranty_end    = db.Column(db.Date)
    last_maintenance= db.Column(db.Date)
    next_maintenance= db.Column(db.Date)
    maint_frequency = db.Column(db.String(50))
    status          = db.Column(db.String(30), default='نشط')  # نشط / متوقف / خارج الخدمة / تحت الصيانة
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    # علاقات
    visits          = db.relationship('MaintenanceVisit', backref='elevator', lazy=True)
    faults          = db.relationship('Fault',            backref='elevator', lazy=True)

    def __repr__(self):
        return f'<Elevator {self.code}>'


# =============================================
# 3. العقود
# =============================================
class Contract(TenantMixin, db.Model):
    __tablename__ = 'contracts'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_contract_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # CN-00001 / CI-00001 أو …-2026
    customer_id     = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    contract_type   = db.Column(db.String(50))   # عقد صيانة / ضمان / تركيب / تحديث / طوارئ
    start_date      = db.Column(db.Date, nullable=False)
    end_date        = db.Column(db.Date, nullable=False)
    duration_months = db.Column(db.Integer)
    maint_frequency = db.Column(db.String(50))   # شهري / ربع سنوي / نصف سنوي / سنوي
    visits_per_month= db.Column(db.Integer, default=1)
    value           = db.Column(db.Float, default=0)
    tax_pct         = db.Column(db.Float, default=15)
    tax_amount      = db.Column(db.Float, default=0)
    total           = db.Column(db.Float, default=0)
    payment_terms   = db.Column(db.String(50))   # دفعة واحدة / ربع سنوي / نصف سنوي / سنوي
    invoice_status  = db.Column(db.String(30), default='غير مدفوع')  # مدفوع / مدفوع جزئياً / غير مدفوع / متأخر
    paid_amount     = db.Column(db.Float, default=0)                 # محصّل العقد (مخزّن — يُحدَّث عند الدفع)
    status          = db.Column(db.String(30), default='نشط')        # نشط / على وشك الانتهاء / منتهي / ملغي
    reminder_date   = db.Column(db.Date)
    due_date        = db.Column(db.Date)  # تاريخ استحقاق تحصيل قيمة العقد
    city            = db.Column(db.String(100))
    district        = db.Column(db.String(100))
    address         = db.Column(db.Text)
    file_path       = db.Column(db.String(300))
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    # علاقات
    elevators       = db.relationship('ContractElevator', backref='contract', lazy=True)
    visits          = db.relationship('MaintenanceVisit', backref='contract', lazy=True)

    def __repr__(self):
        return f'<Contract {self.code}>'


# جدول وسيط بين العقد والمصاعد (علاقة many-to-many)
class ContractElevator(TenantMixin, db.Model):
    __tablename__ = 'contract_elevators'
    id          = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False)
    elevator_id = db.Column(db.Integer, db.ForeignKey('elevators.id'), nullable=False)


# =============================================
# 4. الفنيون
# =============================================
class Technician(TenantMixin, db.Model):
    __tablename__ = 'technicians'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_technician_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # Tech-001
    name            = db.Column(db.String(100), nullable=False)
    name_en         = db.Column(db.String(100))
    phone           = db.Column(db.String(40))
    phone2          = db.Column(db.String(40))
    job_title       = db.Column(db.String(100))   # فني أول / فني ثانٍ / مشرف
    specialization  = db.Column(db.String(100))   # مصاعد ركاب / كهرباء / ميكانيكا
    city            = db.Column(db.String(100))
    national_id     = db.Column(db.String(20))
    nationality     = db.Column(db.String(100))
    experience_years = db.Column(db.Integer)
    email           = db.Column(db.String(120))
    national_id_expiry = db.Column(db.Date)
    license_number  = db.Column(db.String(50))
    license_expiry  = db.Column(db.Date)
    districts_json  = db.Column(db.Text)  # JSON قائمة أحياء
    hire_date       = db.Column(db.Date)
    salary          = db.Column(db.Float)
    emergency       = db.Column(db.Boolean, default=False)  # متاح للطوارئ
    status          = db.Column(db.String(20), default='متاح')  # متاح / مشغول / إجازة / غير نشط
    team            = db.Column(db.String(30), default='عام')   # صيانة / أعطال / عام
    photo_path      = db.Column(db.String(300))   # uploads/technicians/{id}/photo.jpg
    signature_path  = db.Column(db.String(300))   # uploads/technicians/{id}/signature.png
    sign_pin_hash   = db.Column(db.String(200))   # رمز توقيع من 6 أرقام (مشفّر)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    # علاقات
    visits          = db.relationship('MaintenanceVisit', backref='technician', lazy=True)
    faults          = db.relationship('Fault',            backref='technician', lazy=True)
    documents       = db.relationship(
        'TechnicianDocument', backref='technician', lazy=True,
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f'<Technician {self.code} {self.name}>'


class TechnicianDocument(TenantMixin, db.Model):
    __tablename__ = 'technician_documents'

    id              = db.Column(db.Integer, primary_key=True)
    technician_id   = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=False)
    doc_type        = db.Column(db.String(50))   # شهادة / مؤهل / إقامة / رخصة / تدريب / أخرى
    title           = db.Column(db.String(200))
    file_path       = db.Column(db.String(300), nullable=False)
    file_name       = db.Column(db.String(200))
    mime_type       = db.Column(db.String(100))
    uploaded_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TechnicianDocument {self.id} {self.title}>'


# =============================================
# 4ب. فرق الصيانة الدورية (فني + مساعد)
# =============================================
class MaintenanceTeam(TenantMixin, db.Model):
    __tablename__ = 'maintenance_teams'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_mteam_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # MT-001
    name            = db.Column(db.String(100), nullable=False)
    leader_id       = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=False)
    assistant_id    = db.Column(db.Integer, db.ForeignKey('technicians.id'))
    active          = db.Column(db.Boolean, default=True)
    sort_order      = db.Column(db.Integer, default=0)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    leader = db.relationship('Technician', foreign_keys=[leader_id])
    assistant = db.relationship('Technician', foreign_keys=[assistant_id])

    def __repr__(self):
        return f'<MaintenanceTeam {self.code} {self.name}>'


# =============================================
# 5. زيارات الصيانة
# =============================================
class MaintenanceVisit(TenantMixin, db.Model):
    __tablename__ = 'maintenance_visits'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_visit_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # VI-00001
    contract_id     = db.Column(db.Integer, db.ForeignKey('contracts.id'))
    elevator_id     = db.Column(db.Integer, db.ForeignKey('elevators.id'), nullable=False)
    technician_id   = db.Column(db.Integer, db.ForeignKey('technicians.id'))
    maintenance_team_id = db.Column(db.Integer, db.ForeignKey('maintenance_teams.id'))
    fault_id        = db.Column(db.Integer, db.ForeignKey('faults.id'))
    visit_type      = db.Column(db.String(50))   # دورية / طارئة / متابعة
    visit_date      = db.Column(db.Date, nullable=False)
    visit_time      = db.Column(db.String(10))
    duration_hours  = db.Column(db.Float)
    priority        = db.Column(db.String(20), default='عادية')  # عادية / عاجلة / حرجة
    status          = db.Column(db.String(30), default='مجدولة')  # مجدولة / مُرسلة للفني / جارية / مكتملة / ملغاة / متأخرة
    plan_month      = db.Column(db.String(7))   # 2026-06
    route_order     = db.Column(db.Integer, default=0)
    dispatched_at   = db.Column(db.DateTime)
    works_done      = db.Column(db.Text)   # الأعمال المنفذة
    observations    = db.Column(db.Text)   # الملاحظات
    checklist_json  = db.Column(db.Text)   # محضر الفحص (JSON — SaaS: template_key داخل JSON)
    checklist_template_key = db.Column(db.String(50), default='liftcore_standard_v1')
    completed_at    = db.Column(db.DateTime)
    next_visit_date = db.Column(db.Date)
    customer_signature = db.Column(db.Boolean, default=False)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    maintenance_team = db.relationship('MaintenanceTeam', backref='visits', lazy=True)

    def __repr__(self):
        return f'<Visit {self.code}>'


class VisitTechnician(TenantMixin, db.Model):
    __tablename__ = 'visit_technicians'

    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('maintenance_visits.id', ondelete='CASCADE'), nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=False)
    role = db.Column(db.String(20), default='فني')  # فني / مساعد

    visit = db.relationship(
        'MaintenanceVisit',
        backref=db.backref('assigned_technicians', lazy=True, cascade='all, delete-orphan'),
    )
    technician = db.relationship('Technician', lazy=True)

    __table_args__ = (db.UniqueConstraint('visit_id', 'technician_id', name='uq_visit_technician'),)

    def __repr__(self):
        return f'<VisitTechnician {self.visit_id}:{self.technician_id}>'


# =============================================
# 6. الأعطال
# =============================================
class Fault(TenantMixin, db.Model):
    __tablename__ = 'faults'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_fault_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # FA-00001
    elevator_id     = db.Column(db.Integer, db.ForeignKey('elevators.id'), nullable=False)
    technician_id   = db.Column(db.Integer, db.ForeignKey('technicians.id'))
    visit_id        = db.Column(db.Integer, db.ForeignKey('maintenance_visits.id'))
    fault_type      = db.Column(db.String(100))
    description     = db.Column(db.Text)
    client_report   = db.Column(db.Text)   # وصف العميل كما أُبلِغ
    reporter_name   = db.Column(db.String(100))
    reporter_phone  = db.Column(db.String(20))
    tech_notes      = db.Column(db.Text)   # ملاحظات الفني
    needs_parts     = db.Column(db.Boolean, default=False)
    priority        = db.Column(db.String(20), default='عادية')  # عادية / عاجلة / حرجة
    reported_at     = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at    = db.Column(db.DateTime)
    resolved_at     = db.Column(db.DateTime)
    response_time   = db.Column(db.String(50))  # محسوبة تلقائياً
    status          = db.Column(db.String(30), default='مفتوح')  # مفتوح / قيد المعالجة / انتظار قطع / تم الاصلاح / مغلق
    resolution      = db.Column(db.Text)   # طريقة الحل
    dispatched_at   = db.Column(db.DateTime)
    billed          = db.Column(db.Boolean, default=False)
    notes           = db.Column(db.Text)
    report_json     = db.Column(db.Text)

    def __repr__(self):
        return f'<Fault {self.code}>'


class WhatsAppInbox(TenantMixin, db.Model):
    """وارد واتساب — يستلمه المكتب أولاً ثم يُوزَّع كعطل."""
    __tablename__ = 'whatsapp_inbox'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_whatsapp_inbox_org_code'),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)  # WA-00001
    direction = db.Column(db.String(20), default='inbound')  # inbound / outbound
    from_phone = db.Column(db.String(40), nullable=False)
    from_name = db.Column(db.String(120))
    body = db.Column(db.Text)
    media_url = db.Column(db.String(500))
    status = db.Column(db.String(40), default='جديد')  # جديد / مربوط / تم إنشاء عطل / مغلق / مُرسل
    stage = db.Column(db.String(40))  # received / assigned / on_way / resolved / inbound
    receive_target = db.Column(db.String(40), default='office')  # office أولاً ثم توزيع
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    elevator_id = db.Column(db.Integer, db.ForeignKey('elevators.id'))
    fault_id = db.Column(db.Integer, db.ForeignKey('faults.id'))
    wa_message_id = db.Column(db.String(120))  # idempotency for webhook
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    journey_json = db.Column(db.Text)  # سجل مراحل نفس البلاغ بدون أكواد جديدة
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', foreign_keys=[customer_id])
    elevator = db.relationship('Elevator', foreign_keys=[elevator_id])
    fault = db.relationship('Fault', foreign_keys=[fault_id])

    def __repr__(self):
        return f'<WhatsAppInbox {self.code}>'


class FaultTechnician(TenantMixin, db.Model):
    __tablename__ = 'fault_technicians'

    id = db.Column(db.Integer, primary_key=True)
    fault_id = db.Column(db.Integer, db.ForeignKey('faults.id', ondelete='CASCADE'), nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=False)
    role = db.Column(db.String(20), default='فني')

    fault = db.relationship(
        'Fault',
        backref=db.backref('assigned_technicians', lazy=True, cascade='all, delete-orphan'),
    )
    technician = db.relationship('Technician', lazy=True)

    __table_args__ = (db.UniqueConstraint('fault_id', 'technician_id', name='uq_fault_technician'),)

    def __repr__(self):
        return f'<FaultTechnician {self.fault_id}:{self.technician_id}>'


# =============================================
# 7. الإيرادات
# =============================================
class Revenue(TenantMixin, db.Model):
    __tablename__ = 'revenues'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_revenue_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # REV-001
    customer_id     = db.Column(db.Integer, db.ForeignKey('customers.id'))
    contract_id     = db.Column(db.Integer, db.ForeignKey('contracts.id'))
    invoice_id      = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    parts_billing_id = db.Column(db.Integer, db.ForeignKey('parts_billing.id'))
    revenue_date    = db.Column(db.Date, nullable=False)
    revenue_type    = db.Column(db.String(100))  # عقد صيانة / قطع غيار / أعمال إضافية
    payment_method  = db.Column(db.String(50))   # نقد / تحويل / شيك / بطاقة
    amount          = db.Column(db.Float, nullable=False)
    tax_amount      = db.Column(db.Float, default=0)
    total           = db.Column(db.Float, nullable=False)
    status          = db.Column(db.String(30), default='محصّل')  # محصّل / معلق / ملغي
    reference       = db.Column(db.String(500))  # رقم الشيك أو التحويل / مرفقات
    proof_path      = db.Column(db.String(300))  # إثبات الدفع (صورة/PDF)
    notes           = db.Column(db.Text)
    account_id      = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    created_by_user_id = db.Column(db.Integer)
    created_by_name = db.Column(db.String(100))  # اسم من سجّل العملية (لقطة عند الإنشاء)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    customer        = db.relationship('Customer', foreign_keys=[customer_id])
    contract        = db.relationship('Contract', foreign_keys=[contract_id])
    invoice         = db.relationship('Invoice', foreign_keys=[invoice_id])
    parts_billing   = db.relationship('PartsBilling', foreign_keys=[parts_billing_id])
    account         = db.relationship('Account', foreign_keys=[account_id])

    def __repr__(self):
        return f'<Revenue {self.code}>'


# =============================================
# 7b. شجرة الحسابات (محاسبة تشغيلية للمصاعد)
# =============================================
class Account(TenantMixin, db.Model):
    __tablename__ = 'accounts'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_account_org_code'),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)  # 1100, 4100, ...
    name = db.Column(db.String(200), nullable=False)
    name_en = db.Column(db.String(200))
    # asset | liability | equity | revenue | expense
    account_type = db.Column(db.String(20), nullable=False, default='expense')
    parent_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    # مفتاح ربط تشغيلي: revenue:تجديد عقد | expense:محروقات | cash | ar | ...
    map_key = db.Column(db.String(80), index=True)
    is_postable = db.Column(db.Boolean, default=True)  # الحسابات الورقية = False
    is_system = db.Column(db.Boolean, default=False)  # من القالب — لا يُحذف
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parent = db.relationship('Account', remote_side=[id], backref='children')

    def __repr__(self):
        return f'<Account {self.code} {self.name}>'


# =============================================
# 8. المصروفات
# =============================================
class Expense(TenantMixin, db.Model):
    __tablename__ = 'expenses'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_expense_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # EXP-001
    expense_date    = db.Column(db.Date, nullable=False)
    expense_type    = db.Column(db.String(100))  # رواتب / قطع غيار / وقود / أدوات
    description     = db.Column(db.String(300))
    responsible     = db.Column(db.String(100))
    payment_method  = db.Column(db.String(50))
    amount          = db.Column(db.Float, nullable=False)
    reference       = db.Column(db.String(500))
    proof_path      = db.Column(db.String(300))  # إثبات الصرف (صورة/PDF)
    notes           = db.Column(db.Text)
    account_id      = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    created_by_user_id = db.Column(db.Integer)
    created_by_name = db.Column(db.String(100))  # اسم من سجّل العملية (لقطة عند الإنشاء)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    account         = db.relationship('Account', foreign_keys=[account_id])

    def __repr__(self):
        return f'<Expense {self.code}>'


# =============================================
# 9. الفواتير وسندات القبض
# =============================================
class Invoice(TenantMixin, db.Model):
    __tablename__ = 'invoices'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_invoice_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # INV-0001
    invoice_type    = db.Column(db.String(30))   # فاتورة / سند قبض / إشعار دائن
    customer_id     = db.Column(db.Integer, db.ForeignKey('customers.id'))
    contract_id     = db.Column(db.Integer, db.ForeignKey('contracts.id'))
    parts_billing_id = db.Column(db.Integer, db.ForeignKey('parts_billing.id'))
    invoice_date    = db.Column(db.Date, nullable=False)
    due_date        = db.Column(db.Date)
    description     = db.Column(db.String(300))
    amount          = db.Column(db.Float, nullable=False)
    tax_amount      = db.Column(db.Float, default=0)
    total           = db.Column(db.Float, nullable=False)
    paid_amount     = db.Column(db.Float, default=0)
    payment_method  = db.Column(db.String(50))
    status          = db.Column(db.String(30), default='غير مدفوعة')
    notes           = db.Column(db.Text)
    parent_invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    revenue_id      = db.Column(db.Integer, db.ForeignKey('revenues.id'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    # ZATCA Phase 2 — تبليغ الفاتورة المبسطة
    zatca_uuid         = db.Column(db.String(64))
    zatca_invoice_hash = db.Column(db.String(128))
    zatca_qr_payload   = db.Column(db.Text)
    zatca_status       = db.Column(db.String(20))  # draft|reported|cleared|failed|skipped
    zatca_reported_at  = db.Column(db.DateTime)
    zatca_last_error   = db.Column(db.Text)

    customer        = db.relationship('Customer', foreign_keys=[customer_id])
    contract        = db.relationship('Contract', foreign_keys=[contract_id])
    parts_billing   = db.relationship('PartsBilling', foreign_keys=[parts_billing_id])
    parent_invoice  = db.relationship('Invoice', remote_side=[id], foreign_keys=[parent_invoice_id])
    linked_revenue  = db.relationship('Revenue', foreign_keys=[revenue_id], uselist=False)

    def __repr__(self):
        return f'<Invoice {self.code}>'


# =============================================
# 10. الأصناف (المخزن)
# =============================================
class InventoryItem(TenantMixin, db.Model):
    __tablename__ = 'inventory_items'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_inventory_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # #001
    name            = db.Column(db.String(200), nullable=False)
    category        = db.Column(db.String(100))   # أبواب / كهرباء / ميكانيكا / تشحيم
    unit            = db.Column(db.String(20))    # قطعة / لتر / متر
    current_qty     = db.Column(db.Float, default=0)
    min_qty         = db.Column(db.Float, default=0)   # الحد الأدنى للطلب
    buy_price       = db.Column(db.Float, default=0)
    sell_price      = db.Column(db.Float, default=0)
    supplier        = db.Column(db.String(100))
    location        = db.Column(db.String(100))   # موقع التخزين
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    # علاقات
    movements       = db.relationship('StockMovement', backref='item', lazy=True)

    @property
    def stock_value(self):
        return self.current_qty * self.buy_price

    @property
    def order_status(self):
        if self.current_qty <= 0:
            return 'نافد'
        elif self.current_qty <= self.min_qty:
            return 'منخفض'
        return 'كافي'

    def __repr__(self):
        return f'<Item {self.code} {self.name}>'


# =============================================
# 11. حركة المخزن
# =============================================
class StockMovement(TenantMixin, db.Model):
    __tablename__ = 'stock_movements'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_stockmv_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # MV-001
    item_id         = db.Column(db.Integer, db.ForeignKey('inventory_items.id'), nullable=False)
    movement_date   = db.Column(db.Date, nullable=False)
    direction       = db.Column(db.String(10))   # وارد / صادر
    movement_type   = db.Column(db.String(100))  # شراء / استخدام في صيانة / استبدال / إرجاع
    quantity        = db.Column(db.Float, nullable=False)
    unit_price      = db.Column(db.Float, default=0)
    total_value     = db.Column(db.Float, default=0)
    technician_id   = db.Column(db.Integer, db.ForeignKey('technicians.id'))
    elevator_id     = db.Column(db.Integer, db.ForeignKey('elevators.id'))
    reason          = db.Column(db.String(300))
    reference       = db.Column(db.String(100))
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<StockMovement {self.code}>'


# =============================================
# 12. بيان تركيب قطع الغيار
# =============================================
class PartsBilling(TenantMixin, db.Model):
    __tablename__ = 'parts_billing'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_partsbill_org_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(20), nullable=False)  # PB-001
    customer_id     = db.Column(db.Integer, db.ForeignKey('customers.id'))
    contract_id     = db.Column(db.Integer, db.ForeignKey('contracts.id'))
    elevator_id     = db.Column(db.Integer, db.ForeignKey('elevators.id'))
    technician_id   = db.Column(db.Integer, db.ForeignKey('technicians.id'))
    visit_id        = db.Column(db.Integer, db.ForeignKey('maintenance_visits.id'))
    fault_id        = db.Column(db.Integer, db.ForeignKey('faults.id'))
    billing_date    = db.Column(db.Date, nullable=False)
    description     = db.Column(db.Text)   # بيان القطع
    cost_price      = db.Column(db.Float, default=0)   # تكلفة الشراء
    sell_price      = db.Column(db.Float, default=0)   # سعر البيع للعميل
    paid_amount     = db.Column(db.Float, default=0)
    profit          = db.Column(db.Float, default=0)   # الربح
    payment_method  = db.Column(db.String(50))
    payment_note    = db.Column(db.Text)   # بيان السداد (سند/فاتورة) — الدفع عبر الإيرادات
    status          = db.Column(db.String(30), default='غير محصل')
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    elevator        = db.relationship('Elevator', foreign_keys=[elevator_id])
    contract        = db.relationship('Contract', foreign_keys=[contract_id])
    customer        = db.relationship('Customer', foreign_keys=[customer_id])
    technician      = db.relationship('Technician', foreign_keys=[technician_id])
    visit           = db.relationship('MaintenanceVisit', foreign_keys=[visit_id])
    fault           = db.relationship('Fault', foreign_keys=[fault_id])

    def __repr__(self):
        return f'<PartsBilling {self.code}>'


# =============================================
# 12ب. طلبات الشراء
# =============================================
class PurchaseOrder(TenantMixin, db.Model):
    __tablename__ = 'purchase_orders'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_po_org_code'),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    supplier = db.Column(db.String(200))
    supplier_phone = db.Column(db.String(30))
    supplier_email = db.Column(db.String(120))
    order_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(30), default='مسودة')
    total_amount = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    signature_data = db.Column(db.Text)
    pdf_path = db.Column(db.String(300))
    received_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lines = db.relationship(
        'PurchaseOrderLine', back_populates='order', cascade='all, delete-orphan', lazy='joined'
    )


class PurchaseOrderLine(TenantMixin, db.Model):
    __tablename__ = 'purchase_order_lines'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'), nullable=False)
    quantity = db.Column(db.Float, default=1)
    unit_price = db.Column(db.Float, default=0)
    line_total = db.Column(db.Float, default=0)

    order = db.relationship('PurchaseOrder', back_populates='lines')
    item = db.relationship('InventoryItem')


# =============================================
# 12ج. تقدير تكلفة إنشاء مصعد
# =============================================
class ElevatorEstimate(TenantMixin, db.Model):
    __tablename__ = 'elevator_estimates'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_est_org_code'),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    project_name = db.Column(db.String(200))
    city = db.Column(db.String(100))
    machine_type = db.Column(db.String(30), default='MR')
    elev_type = db.Column(db.String(100), default='مصعد ركاب')
    floors = db.Column(db.Integer, default=2)
    stops = db.Column(db.Integer, default=2)
    capacity_kg = db.Column(db.Integer, default=630)
    speed = db.Column(db.String(50))
    travel_m = db.Column(db.Float)
    doors_count = db.Column(db.Integer, default=2)
    include_installation = db.Column(db.Boolean, default=True)
    include_shaft_work = db.Column(db.Boolean, default=False)
    margin_pct = db.Column(db.Float, default=12)
    vat_pct = db.Column(db.Float, default=15)
    cost_subtotal = db.Column(db.Float, default=0)
    margin_amount = db.Column(db.Float, default=0)
    subtotal = db.Column(db.Float, default=0)
    vat_amount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    status = db.Column(db.String(30), default='مسودة')
    estimate_date = db.Column(db.Date, default=date.today)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', foreign_keys=[customer_id])
    lines = db.relationship(
        'ElevatorEstimateLine', back_populates='estimate', cascade='all, delete-orphan', lazy='joined'
    )


class ElevatorEstimateLine(TenantMixin, db.Model):
    __tablename__ = 'elevator_estimate_lines'

    id = db.Column(db.Integer, primary_key=True)
    estimate_id = db.Column(db.Integer, db.ForeignKey('elevator_estimates.id'), nullable=False)
    category = db.Column(db.String(50))
    description = db.Column(db.String(300))
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(30))
    unit_price = db.Column(db.Float, default=0)
    line_total = db.Column(db.Float, default=0)

    estimate = db.relationship('ElevatorEstimate', back_populates='lines')


# =============================================
# 12ب. الموقّعون (توقيعات مشفّرة)
# =============================================
class Signatory(TenantMixin, db.Model):
    __tablename__ = 'signatories'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    national_id     = db.Column(db.String(20), nullable=False, index=True)
    role            = db.Column(db.String(30), default='technician')  # technician | manager
    sign_pin_hash   = db.Column(db.String(200), nullable=False)
    signature_path  = db.Column(db.String(300))  # uploads/signatures/{id}.enc
    technician_id   = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=True)
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    technician = db.relationship('Technician', backref='signatory', uselist=False)


# =============================================
# 13. إعدادات النظام
# =============================================
class Settings(TenantMixin, db.Model):
    __tablename__ = 'settings'

    id              = db.Column(db.Integer, primary_key=True)
    company_name    = db.Column(db.String(200))
    company_name_en = db.Column(db.String(200))
    phone           = db.Column(db.String(20))
    whatsapp_phone  = db.Column(db.String(40))  # رقم واتساب استقبال البلاغات
    whatsapp_receive_mode = db.Column(db.String(20), default='office')  # office أولاً ثم توزيع
    email           = db.Column(db.String(100))
    address         = db.Column(db.Text)
    address_en      = db.Column(db.Text)
    city            = db.Column(db.String(100))
    cr_number       = db.Column(db.String(50))    # السجل التجاري
    vat_number      = db.Column(db.String(50))    # الرقم الضريبي
    tax_pct         = db.Column(db.Float, default=15)
    currency        = db.Column(db.String(10), default='SAR')
    language        = db.Column(db.String(10), default='ar')
    logo_path       = db.Column(db.String(300))
    logo_width_sidebar = db.Column(db.Integer, default=150)
    logo_width_report  = db.Column(db.Integer, default=150)
    logo_width_login   = db.Column(db.Integer, default=180)
    rep_name        = db.Column(db.String(200))   # ممثل الشركة في العقود
    rep_mobile      = db.Column(db.String(20))      # جوال الممثل
    rep_national_id = db.Column(db.String(20))    # هوية الممثل للتوقيع الرقمي
    rep_signature_path = db.Column(db.String(300))
    rep_sign_pin_hash = db.Column(db.String(200))
    default_sign_method = db.Column(db.String(20), default='both')  # draw | pin | both
    idle_screensaver_enabled = db.Column(db.Boolean, default=True)
    idle_screensaver_seconds = db.Column(db.Integer, default=60)
    checklist_template_key = db.Column(db.String(50), default='liftcore_standard_v1')  # SaaS: قالب الفحص الافتراضي
    google_maps_api_key = db.Column(db.String(200))  # اختياري — يُستخدم إن لم يُضبط GOOGLE_MAPS_API_KEY
    company_website   = db.Column(db.String(200))
    bank_name         = db.Column(db.String(100))
    bank_account_name = db.Column(db.String(200))
    bank_iban         = db.Column(db.String(50))
    bank_account_no   = db.Column(db.String(50))
    work_country      = db.Column(db.String(2), default='SA')
    work_weekdays_json = db.Column(db.Text)
    work_hours_start  = db.Column(db.String(5), default='08:00')
    work_hours_end    = db.Column(db.String(5), default='17:00')
    respect_public_holidays = db.Column(db.Boolean, default=True)
    custom_holidays_json = db.Column(db.Text)
    extra_work_days_json = db.Column(db.Text)
    custom_permissions_enabled = db.Column(db.Boolean, default=False)  # صلاحيات اختيارية per-user


# =============================================
# 13b. اعتمادات زاتكا (لكل مؤسسة)
# =============================================
class ZatcaCredentials(TenantMixin, db.Model):
    __tablename__ = 'zatca_credentials'
    __table_args__ = (
        db.UniqueConstraint('organization_id', name='uq_zatca_credentials_org'),
    )

    id = db.Column(db.Integer, primary_key=True)
    vat_number = db.Column(db.String(15), nullable=False)
    cr_number = db.Column(db.String(20))
    csid = db.Column(db.Text)
    private_key = db.Column(db.Text)
    certificate = db.Column(db.Text)
    api_secret = db.Column(db.Text)  # Secret من بوابة فاتورة (مشفّر)
    environment = db.Column(db.String(10), default='sandbox')
    onboarded_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')

    def __repr__(self):
        return f'<ZatcaCredentials org={self.organization_id} status={self.status}>'


# =============================================
# 14. المستخدمون
# =============================================
class User(TenantMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'username', name='uq_user_org_username'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(50), nullable=False)
    password_hash   = db.Column(db.String(200), nullable=False)
    full_name       = db.Column(db.String(100))
    email           = db.Column(db.String(100))
    role            = db.Column(db.String(30), default='viewer')  # admin / manager / viewer / custom
    theme           = db.Column(db.String(10), default='dark')  # dark / light / report / premium
    language        = db.Column(db.String(10), default='ar')  # ar / en
    photo_path      = db.Column(db.String(300))
    is_active       = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=False)
    permissions_extra = db.Column(db.Text)  # JSON: {"grants":[],"denies":[]} — اختياري
    session_version = db.Column(db.Integer, default=0, nullable=False)  # جلسة واحدة: يزيد عند كل دخول جديد
    last_login      = db.Column(db.DateTime)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'


class AuditLog(TenantMixin, db.Model):
    """سجل تدقيق — حذف، إعدادات، تغيير كلمة مرور."""
    __tablename__ = 'audit_logs'

    id           = db.Column(db.Integer, primary_key=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id      = db.Column(db.Integer, index=True)
    username     = db.Column(db.String(80))
    action       = db.Column(db.String(80), nullable=False)
    entity_type  = db.Column(db.String(60))
    entity_id    = db.Column(db.String(40))
    details_json = db.Column(db.Text)
    ip_address   = db.Column(db.String(45))


class AppLiveState(db.Model):
    """عداد مركزي — يزيد عند أي تغيير في البيانات لمزامنة واجهات الموظفين."""
    __tablename__ = 'app_live_state'

    id = db.Column(db.Integer, primary_key=True, default=1)
    revision = db.Column(db.Integer, default=0, nullable=False)


class RateLimitEvent(db.Model):
    """أحداث rate limit مشتركة بين workers (login / field PIN) — ليست tenant-scoped."""
    __tablename__ = 'rate_limit_events'
    __table_args__ = (
        db.Index('ix_rate_limit_scope_key_created', 'scope', 'bucket_key', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(32), nullable=False)
    bucket_key = db.Column(db.String(191), nullable=False)
    created_at = db.Column(db.Float, nullable=False, index=True)


MaintenanceVisit.linked_fault = db.relationship(
    'Fault', foreign_keys=[MaintenanceVisit.fault_id], uselist=False
)
Fault.linked_visit = db.relationship(
    'MaintenanceVisit', foreign_keys=[Fault.visit_id], uselist=False
)
