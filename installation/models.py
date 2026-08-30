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

QUOTE_TYPE_LABELS = {
    'new': 'توريد وتركيب مصعد جديد',
    'upgrade': 'تحديث مصعد قائم',
    'extend': 'إضافة أدوار لمصعد قائم',
}

QUOTE_TYPE_SHORT = {
    'new': 'تركيب جديد',
    'upgrade': 'تحديث',
    'extend': 'إضافة أدوار',
}

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
    # ربط بعقد تركيب/تحديث LiftCore لحفظ القيمة المرجعية والطباعة
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=True, index=True)
    # عقد ضمان الصيانة (الربط الوحيد المسموح مع الصيانة بعد اكتمال المراحل)
    warranty_contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=True, index=True)
    execution_started_at = db.Column(db.DateTime, nullable=True)
    # قيمة العقد الفعلية (إن وُجدت؛ وإلا يُستخدم إجمالي العرض المعتمد)
    contract_value = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('Customer', backref='installation_projects')
    contract = db.relationship('Contract', foreign_keys=[contract_id], uselist=False)
    warranty_contract = db.relationship('Contract', foreign_keys=[warranty_contract_id], uselist=False)
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
    cost_items = db.relationship(
        'InstallProjectCostItem',
        back_populates='project',
        cascade='all, delete-orphan',
        order_by='InstallProjectCostItem.cost_date.desc(), InstallProjectCostItem.id.desc()',
    )
    receipts = db.relationship(
        'InstallProjectReceipt',
        back_populates='project',
        cascade='all, delete-orphan',
        order_by='InstallProjectReceipt.installment_no.asc(), InstallProjectReceipt.id.asc()',
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


MAX_PAY_INSTALLMENTS = 8


def default_pay_labels(count):
    presets = {
        1: ['دفعة واحدة'],
        2: ['دفعة مقدمة', 'عند التسليم'],
        3: ['دفعة مقدمة', 'عند التوريد', 'دفعة نهائية'],
        4: ['دفعة مقدمة', 'عند التوريد', 'بعد التركيب', 'دفعة نهائية'],
    }
    if count in presets:
        return list(presets[count])
    labels = ['دفعة مقدمة']
    for i in range(2, count):
        labels.append(f'دفعة {i}')
    labels.append('دفعة نهائية')
    return labels


def default_pay_installments(count):
    try:
        count = int(count or 3)
    except (TypeError, ValueError):
        count = 3
    count = max(1, min(count, MAX_PAY_INSTALLMENTS))
    presets = {
        1: [100],
        2: [50, 50],
        3: [50, 40, 10],
        4: [40, 30, 20, 10],
    }
    labels = default_pay_labels(count)
    if count in presets:
        pcts = presets[count]
    else:
        each = 100 // count
        pcts = [each] * count
        pcts[-1] = 100 - each * (count - 1)
    return assign_pay_keys([
        {'label': labels[i], 'pct': pcts[i]} for i in range(count)
    ])


def assign_pay_keys(items):
    n = len(items)
    out = []
    for i, it in enumerate(items):
        row = {
            'label': (it.get('label') or f'دفعة {i + 1}').strip() or f'دفعة {i + 1}',
            'pct': float(it.get('pct') or 0),
        }
        if i == 0:
            row['key'] = 'advance_payment'
        elif n >= 2 and i == n - 1:
            row['key'] = 'payment_final'
        elif n == 3 and i == 1:
            row['key'] = 'payment_on_delivery'
        else:
            row['key'] = f'client_payment_{i + 1}'
        out.append(row)
    return out


def normalize_pay_installments(raw):
    """تحقق من قائمة الدفعات الحرة. يرفع ValueError عند الخطأ."""
    if not raw:
        raise ValueError('أدخل دفعة واحدة على الأقل')
    items = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            pct = float(row.get('pct') or 0)
        except (TypeError, ValueError):
            pct = 0.0
        if pct < 0:
            raise ValueError('نسب الدفعات لا يمكن أن تكون سالبة')
        items.append({
            'label': (row.get('label') or '').strip(),
            'pct': pct,
        })
    items = [it for it in items if it['pct'] > 0]
    if not items:
        raise ValueError('أدخل دفعة واحدة على الأقل')
    if len(items) > MAX_PAY_INSTALLMENTS:
        raise ValueError(f'الحد الأقصى {MAX_PAY_INSTALLMENTS} دفعات')
    for i, it in enumerate(items):
        if not it['label']:
            it['label'] = f'دفعة {i + 1}'
    if round(sum(it['pct'] for it in items), 2) != 100:
        raise ValueError('مجموع نسب الدفعات يجب أن يساوي 100%')
    return assign_pay_keys(items)


def legacy_pcts_from_items(items):
    if not items:
        return 50.0, 40.0, 10.0
    if len(items) == 1:
        return float(items[0]['pct']), 0.0, 0.0
    if len(items) == 2:
        return float(items[0]['pct']), 0.0, float(items[1]['pct'])
    mid = sum(float(i['pct']) for i in items[1:-1])
    return float(items[0]['pct']), float(mid), float(items[-1]['pct'])


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
    quote_type = db.Column(db.String(20), default='new')  # new | upgrade | extend
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
    pay_schedule_json = db.Column(db.Text)  # قائمة دفعات حرة حسب الاتفاق

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

    def quote_type_label(self):
        return QUOTE_TYPE_LABELS.get(self.quote_type or 'new', QUOTE_TYPE_LABELS['new'])

    def quote_type_short(self):
        return QUOTE_TYPE_SHORT.get(self.quote_type or 'new', QUOTE_TYPE_SHORT['new'])

    def spec(self):
        if not self.spec_json:
            return {}
        try:
            return json.loads(self.spec_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _pay_installments_raw(self):
        if not self.pay_schedule_json:
            return None
        try:
            data = json.loads(self.pay_schedule_json)
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(data, list) and data:
            return data
        return None

    def payment_items(self):
        """دفعات العرض ذات النسبة الأكبر من صفر — للطباعة والمعاينة."""
        gt = float(self.grand_total or 0)
        raw = self._pay_installments_raw()
        items = None
        if raw:
            try:
                items = normalize_pay_installments(raw)
            except ValueError:
                cleaned = []
                for row in raw:
                    if not isinstance(row, dict):
                        continue
                    try:
                        pct = float(row.get('pct') or 0)
                    except (TypeError, ValueError):
                        pct = 0
                    if pct > 0:
                        cleaned.append({
                            'label': (row.get('label') or '').strip() or 'دفعة',
                            'pct': pct,
                        })
                items = assign_pay_keys(cleaned) if cleaned else None
        if not items:
            sched_adv = self.pay_advance_pct if self.pay_advance_pct is not None else 50.0
            sched_sup = self.pay_supply_pct if self.pay_supply_pct is not None else 40.0
            sched_fin = self.pay_final_pct if self.pay_final_pct is not None else 10.0
            fallback = [{'label': 'دفعة مقدمة', 'pct': sched_adv}]
            if (sched_sup or 0) > 0:
                fallback.append({'label': 'عند التوريد', 'pct': sched_sup})
            if (sched_fin or 0) > 0:
                fallback.append({
                    'label': 'عند التسليم' if (sched_sup or 0) <= 0 else 'دفعة نهائية',
                    'pct': sched_fin,
                })
            items = assign_pay_keys(fallback)
        out = []
        for it in items:
            pct = float(it.get('pct') or 0)
            if pct <= 0:
                continue
            out.append({
                'key': it.get('key'),
                'label': it.get('label') or 'دفعة',
                'pct': pct,
                'amount': round(gt * pct / 100.0),
            })
        return out

    def payment_count(self):
        return max(1, len(self.payment_items()))

    def payment_schedule(self):
        """نسب دفعات العميل — متوافق مع الحقول الثلاثة القديمة."""
        items = self.payment_items()
        adv, sup, fin = legacy_pcts_from_items(items)
        return {
            'advance_pct': adv,
            'supply_pct': sup,
            'final_pct': fin,
            'count': len(items),
        }

    def payment_amount(self, step_key, grand_total=None):
        """مبلغ دفعة من العقد حسب نوع الخطوة — الأساس: الإجمالي شامل الضريبة."""
        gt = grand_total if grand_total is not None else (self.grand_total or 0)
        if not gt:
            return None
        for it in self.payment_items():
            if it.get('key') == step_key:
                return round(float(gt) * float(it['pct']) / 100.0)
        return None


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


# =============================================
# كارت المشروع — مصروفات بنود + دفعات العميل
# =============================================
COST_CATEGORIES = (
    'السكك والأبواب',
    'الماكينة والشاسيه',
    'الكابينة والكنترول',
)

COST_PHASE_LABELS = {
    'السكك والأبواب': 'مرحلة 1 — السكك والأبواب',
    'الماكينة والشاسيه': 'مرحلة 2 — الماكينة والشاسيه',
    'الكابينة والكنترول': 'مرحلة 3 — الكابينة والكنترول',
}


def normalize_cost_category(category, installment_no=None):
    """تحويل الفئات القديمة (قطع غيار / عمالة …) إلى مراحل التركيب الثلاث."""
    cat = (category or '').strip()
    if cat in COST_CATEGORIES:
        return cat
    if cat == 'عمالة':
        by_inst = {
            1: 'السكك والأبواب',
            2: 'الماكينة والشاسيه',
            3: 'الكابينة والكنترول',
        }
        if installment_no in by_inst:
            return by_inst[installment_no]
        return 'السكك والأبواب'
    legacy = {
        'قطع غيار': 'السكك والأبواب',
        'نقل': 'السكك والأبواب',
        'موردين': 'الماكينة والشاسيه',
        'أخرى': 'الكابينة والكنترول',
    }
    return legacy.get(cat, 'السكك والأبواب')

COST_PAYMENT_STATUSES = (
    'مدفوعة',
    'غير مدفوعة',
)

RECEIPT_STATUSES = (
    'مستلمة',
    'معلقة',
)


class InstallProjectCostItem(TenantMixin, db.Model):
    """بند تكلفة على مشروع تركيب — مرتبط بمرحلة تركيب (سكك / ماكينة / كبينة)."""
    __tablename__ = 'installation_project_costs'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('installation_projects.id'), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, default='أخرى')
    title = db.Column(db.String(300), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)
    cost_date = db.Column(db.Date, default=date.today)
    # لعمالة بالدفعات أو أي بند مقسّم: رقم الدفعة
    installment_no = db.Column(db.Integer, nullable=True)
    # حالة سداد بند العمالة/الدفعة: مدفوعة | غير مدفوعة
    payment_status = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('InstallProject', back_populates='cost_items')


class InstallProjectReceipt(TenantMixin, db.Model):
    """دفعة مستلمة من العميل على قيمة المشروع."""
    __tablename__ = 'installation_project_receipts'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('installation_projects.id'), nullable=False, index=True)
    installment_no = db.Column(db.Integer, nullable=False, default=1)
    label = db.Column(db.String(200))  # مثال: دفعة مقدمة / عند التوريد
    amount = db.Column(db.Float, nullable=False, default=0)
    received_date = db.Column(db.Date, default=date.today)
    payment_method = db.Column(db.String(50))
    status = db.Column(db.String(30), default='مستلمة')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('InstallProject', back_populates='receipts')
