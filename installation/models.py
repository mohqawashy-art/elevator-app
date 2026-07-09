"""
موديول تركيب المصاعد — جداول منفصلة (لا تعدّل جداول LiftCore الحالية).
"""

import json
from datetime import datetime, date

from models import TenantMixin, db

LEAD_STATUSES = (
    'جديد',
    'جاري التواصل',
    'موعد معاينة',
    'ملغي',
    'تم تحويله لمشروع',
)

LEAD_SOURCES = (
    'اتصال',
    'واتساب',
    'موقع إلكتروني',
    'معرض',
    'مندوب',
    'عميل سابق',
)

PROJECT_STATUSES = (
    'استفسار',
    'معاينة',
    'هندسة',
    'تسعير',
    'عرض سعر',
    'عقد',
    'توريد',
    'تركيب',
    'تسليم',
    'ضمان',
    'مغلق',
)

QUOTE_STATUSES = (
    'مسودة',
    'مُرسل',
    'تفاوض',
    'مقبول',
    'مرفوض',
)

TIMELINE_STEP_STATUSES = (
    'قادم',
    'جاري',
    'مكتمل',
    'متأخر',
    'ملغي',
)


class InstallLead(TenantMixin, db.Model):
    __tablename__ = 'installation_leads'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_install_lead_org_code'),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    inquiry_date = db.Column(db.Date, default=date.today)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    client_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    city = db.Column(db.String(100))
    district = db.Column(db.String(100))
    address = db.Column(db.Text)
    source = db.Column(db.String(50))
    building_type = db.Column(db.String(100))
    notes = db.Column(db.Text)
    status = db.Column(db.String(40), default='جديد')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('Customer', backref='installation_leads')
    project = db.relationship(
        'InstallProject',
        back_populates='lead',
        foreign_keys='InstallProject.lead_id',
        uselist=False,
    )

    @property
    def client_display(self):
        if self.customer:
            return self.customer.name
        return self.client_name or '—'

    @property
    def client_code(self):
        if self.customer:
            return self.customer.code
        return '—'


class InstallProject(TenantMixin, db.Model):
    __tablename__ = 'installation_projects'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_install_project_org_code'),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(300))
    status = db.Column(db.String(40), default='استفسار')
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('installation_leads.id'), nullable=True)
    accepted_quotation_id = db.Column(db.Integer, db.ForeignKey('installation_quotations.id'), nullable=True)
    execution_started_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('Customer', backref='installation_projects')
    accepted_quotation = db.relationship(
        'InstallQuotation',
        foreign_keys=[accepted_quotation_id],
        uselist=False,
    )
    lead = db.relationship(
        'InstallLead',
        back_populates='project',
        foreign_keys='InstallProject.lead_id',
        uselist=False,
    )
    quotations = db.relationship(
        'InstallQuotation',
        back_populates='project',
        foreign_keys='InstallQuotation.project_id',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )
    timeline_steps = db.relationship(
        'InstallTimelineStep',
        back_populates='project',
        cascade='all, delete-orphan',
        order_by='InstallTimelineStep.sort_order',
    )

    @property
    def execution_active(self):
        return bool(self.execution_started_at and self.accepted_quotation_id)

    @property
    def client_display(self):
        if self.customer:
            return self.customer.name
        if self.lead:
            return self.lead.client_name
        return self.title or '—'


class InstallQuotation(TenantMixin, db.Model):
    """عرض سعر / تسعير تركيب — مراحل 3–6."""
    __tablename__ = 'installation_quotations'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_install_quote_org_code'),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('installation_projects.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    quote_type = db.Column(db.String(20), default='new')  # new | upgrade
    status = db.Column(db.String(30), default='مسودة')

    client_name = db.Column(db.String(200))
    client_phone = db.Column(db.String(30))
    client_address = db.Column(db.String(300))
    valid_days = db.Column(db.Integer, default=30)

    spec_json = db.Column(db.Text)  # مواصفات المصعد / التحديث

    labor = db.Column(db.Float, default=0)
    transport = db.Column(db.Float, default=2000)
    other_costs = db.Column(db.Float, default=0)
    profit_pct = db.Column(db.Float, default=20)

    materials_total = db.Column(db.Float, default=0)
    cost_total = db.Column(db.Float, default=0)
    profit_amount = db.Column(db.Float, default=0)
    before_tax = db.Column(db.Float, default=0)
    vat_amount = db.Column(db.Float, default=0)
    grand_total = db.Column(db.Float, default=0)

    pay_advance_pct = db.Column(db.Float, default=50)
    pay_supply_pct = db.Column(db.Float, default=40)
    pay_final_pct = db.Column(db.Float, default=10)

    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = db.relationship(
        'InstallProject',
        back_populates='quotations',
        foreign_keys=[project_id],
    )
    customer = db.relationship('Customer', backref='installation_quotations')
    lines = db.relationship(
        'InstallQuotationLine',
        back_populates='quotation',
        cascade='all, delete-orphan',
        order_by='InstallQuotationLine.sort_order',
    )

    def spec(self):
        if not self.spec_json:
            return {}
        try:
            return json.loads(self.spec_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def payment_schedule(self):
        """نسب دفعات العميل المحددة في التسعير."""
        return {
            'advance_pct': self.pay_advance_pct if self.pay_advance_pct is not None else 50.0,
            'supply_pct': self.pay_supply_pct if self.pay_supply_pct is not None else 40.0,
            'final_pct': self.pay_final_pct if self.pay_final_pct is not None else 10.0,
        }

    def payment_amount(self, step_key, grand_total=None):
        """مبلغ دفعة من العقد حسب نوع الخطوة — الأساس: الإجمالي شامل الضريبة."""
        gt = grand_total if grand_total is not None else (self.grand_total or 0)
        if not gt:
            return None
        sched = self.payment_schedule()
        key_pct = {
            'advance_payment': sched['advance_pct'],
            'payment_on_delivery': sched['supply_pct'],
            'payment_final': sched['final_pct'],
        }
        pct = key_pct.get(step_key)
        if pct is None:
            return None
        return round(float(gt) * float(pct) / 100.0)


class InstallQuotationLine(TenantMixin, db.Model):
    __tablename__ = 'installation_quotation_lines'

    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('installation_quotations.id'), nullable=False)
    stage = db.Column(db.String(100))
    name = db.Column(db.String(300), nullable=False)
    unit = db.Column(db.String(40))
    qty = db.Column(db.Float, default=1)
    unit_price = db.Column(db.Float, default=0)
    sort_order = db.Column(db.Integer, default=0)

    quotation = db.relationship('InstallQuotation', back_populates='lines')

    @property
    def line_total(self):
        return (self.qty or 0) * (self.unit_price or 0)


class InstallTimelineStep(TenantMixin, db.Model):
    """خطوة في جدول تنفيذ المشروع بعد قبول العرض."""
    __tablename__ = 'installation_timeline_steps'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('installation_projects.id'), nullable=False)
    step_key = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    phase_group = db.Column(db.String(40))
    sort_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default='قادم')
    hint = db.Column(db.String(300))
    has_amount = db.Column(db.Boolean, default=False)
    planned_date = db.Column(db.Date, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    amount = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = db.relationship('InstallProject', back_populates='timeline_steps')

    __table_args__ = (
        db.UniqueConstraint('project_id', 'step_key', name='uq_install_timeline_step'),
    )
