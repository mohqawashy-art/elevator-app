"""شجرة حسابات افتراضية لشركات صيانة/تركيب المصاعد + ربط تشغيلي."""
from __future__ import annotations

from sqlalchemy import inspect, text

from models import Account, db
from tenant_scope import tenant_query


def ensure_chart_schema() -> None:
    """يضمن جدول الحسابات وعمود account_id (Postgres لا يشغّل ALTER اليدوي لـ SQLite)."""
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    if 'accounts' not in tables:
        Account.__table__.create(bind=db.engine, checkfirst=True)
        tables.add('accounts')
    for table in ('revenues', 'expenses'):
        if table not in tables:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if 'account_id' in cols:
            continue
        db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN account_id INTEGER'))
        db.session.commit()
        try:
            db.session.execute(
                text(f'CREATE INDEX IF NOT EXISTS ix_{table}_account_id ON {table} (account_id)')
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

# (code, name_ar, name_en, type, parent_code|None, map_key|None, postable, sort)
DEFAULT_CHART: list[tuple] = [
    ('1000', 'الأصول', 'Assets', 'asset', None, None, False, 1000),
    ('1100', 'الأصول المتداولة', 'Current Assets', 'asset', '1000', None, False, 1100),
    ('1110', 'الصندوق', 'Cash on Hand', 'asset', '1100', None, True, 1110),
    ('1120', 'البنك', 'Bank', 'asset', '1100', 'cash', True, 1120),
    ('1130', 'عهد نقدية — فنيين', 'Technician Petty Cash', 'asset', '1100', None, True, 1130),
    ('1140', 'ذمم عملاء — عقود صيانة', 'AR — Maintenance Contracts', 'asset', '1100', 'ar', True, 1140),
    ('1141', 'ذمم عملاء — تركيب وقطع', 'AR — Installation & Parts', 'asset', '1100', None, True, 1141),
    ('1150', 'شيكات تحت التحصيل', 'Checks in Collection', 'asset', '1100', None, True, 1150),
    ('1160', 'مخزون قطع الغيار', 'Spare Parts Inventory', 'asset', '1100', 'inventory', True, 1160),
    ('1170', 'دفعات مقدمة لموردين', 'Advances to Suppliers', 'asset', '1100', None, True, 1170),
    ('1180', 'مصروفات مدفوعة مقدماً', 'Prepaid Expenses', 'asset', '1100', None, True, 1180),
    ('1190', 'ضريبة مدخلات قابلة للاسترداد', 'Recoverable Input VAT', 'asset', '1100', None, True, 1190),

    ('1200', 'الأصول الثابتة', 'Fixed Assets', 'asset', '1000', None, False, 1200),
    ('1210', 'أراضي', 'Land', 'asset', '1200', None, True, 1210),
    ('1220', 'المباني', 'Buildings', 'asset', '1200', None, False, 1220),
    ('1221', 'مباني — تكلفة', 'Buildings — Cost', 'asset', '1220', None, True, 1221),
    ('1229', 'مجمع استهلاك المباني', 'Accum. Dep. — Buildings', 'asset', '1220', None, True, 1229),
    ('1230', 'السيارات', 'Vehicles', 'asset', '1200', None, False, 1230),
    ('1231', 'سيارات — تكلفة', 'Vehicles — Cost', 'asset', '1230', None, True, 1231),
    ('1239', 'مجمع استهلاك السيارات', 'Accum. Dep. — Vehicles', 'asset', '1230', None, True, 1239),
    ('1240', 'معدات الورشة', 'Workshop Equipment', 'asset', '1200', None, False, 1240),
    ('1241', 'معدات وعدد رأسمالية — تكلفة', 'Workshop Equipment — Cost', 'asset', '1240', None, True, 1241),
    ('1249', 'مجمع استهلاك المعدات', 'Accum. Dep. — Equipment', 'asset', '1240', None, True, 1249),
    ('1250', 'الأثاث والتجهيزات', 'Furniture & Fixtures', 'asset', '1200', None, False, 1250),
    ('1251', 'أثاث وتجهيزات — تكلفة', 'Furniture — Cost', 'asset', '1250', None, True, 1251),
    ('1259', 'مجمع استهلاك الأثاث', 'Accum. Dep. — Furniture', 'asset', '1250', None, True, 1259),
    ('1260', 'الأجهزة والحاسب', 'Computers & IT', 'asset', '1200', None, False, 1260),
    ('1261', 'أجهزة حاسب وبرامج رأسمالية', 'Computers & Capitalized Software', 'asset', '1260', None, True, 1261),
    ('1269', 'مجمع استهلاك الأجهزة', 'Accum. Dep. — Computers', 'asset', '1260', None, True, 1269),

    ('1300', 'أصول غير متداولة أخرى', 'Other Non-current Assets', 'asset', '1000', None, False, 1300),
    ('1310', 'تأمينات لدى الغير', 'Refundable Deposits', 'asset', '1300', None, True, 1310),

    ('2000', 'الخصوم', 'Liabilities', 'liability', None, None, False, 2000),
    ('2100', 'الخصوم المتداولة', 'Current Liabilities', 'liability', '2000', None, False, 2100),
    ('2110', 'ذمم موردين', 'Accounts Payable', 'liability', '2100', 'ap', True, 2110),
    ('2120', 'ضريبة القيمة المضافة المستحقة', 'VAT Payable', 'liability', '2100', 'vat_payable', True, 2120),
    ('2130', 'رواتب مستحقة', 'Accrued Salaries', 'liability', '2100', None, True, 2130),
    ('2140', 'تأمينات اجتماعية مستحقة', 'Accrued GOSI', 'liability', '2100', None, True, 2140),
    ('2150', 'إيرادات عقود مؤجلة', 'Deferred Contract Revenue', 'liability', '2100', None, True, 2150),
    ('2160', 'دفعات عملاء مقدمة — تركيب', 'Customer Advances — Installation', 'liability', '2100', None, True, 2160),
    ('2200', 'الخصوم غير المتداولة', 'Non-current Liabilities', 'liability', '2000', None, False, 2200),
    ('2210', 'مخصص مكافأة نهاية الخدمة', 'End-of-Service Provision', 'liability', '2200', None, True, 2210),

    ('3000', 'حقوق الملكية', 'Equity', 'equity', None, None, False, 3000),
    ('3100', 'رأس المال', 'Capital', 'equity', '3000', 'capital', True, 3100),
    ('3200', 'جاري الشركاء', "Partners' Current Account", 'equity', '3000', None, True, 3200),
    ('3300', 'أرباح مبقاة', 'Retained Earnings', 'equity', '3000', None, True, 3300),

    ('4000', 'الإيرادات', 'Revenue', 'revenue', None, None, False, 4000),
    ('4100', 'إيراد الصيانة', 'Maintenance Revenue', 'revenue', '4000', None, False, 4100),
    ('4110', 'عقود صيانة دورية', 'Periodic Maintenance Contracts', 'revenue', '4100', 'revenue:عقد صيانة', True, 4110),
    ('4120', 'تجديد عقود', 'Contract Renewals', 'revenue', '4100', 'revenue:تجديد عقد', True, 4120),
    ('4200', 'إيراد التركيب والتحديث', 'Installation & Modernization', 'revenue', '4000', None, False, 4200),
    ('4210', 'تركيب مصاعد جديدة', 'New Elevator Installation', 'revenue', '4200', 'revenue:عقد جديد', True, 4210),
    ('4220', 'تحديث وتطوير مصاعد', 'Elevator Modernization', 'revenue', '4200', 'revenue:عقد تحديث', True, 4220),
    ('4300', 'إيراد القطع والأعمال', 'Parts & Extra Works', 'revenue', '4000', None, False, 4300),
    ('4310', 'مبيعات قطع غيار', 'Spare Parts Sales', 'revenue', '4300', 'revenue:قطع غيار', True, 4310),
    ('4320', 'أعمال إضافية وأعطال خارج العقد', 'Extra Works & Out-of-contract Faults', 'revenue', '4300', 'revenue:أعمال إضافية', True, 4320),
    ('4330', 'استدعاءات طوارئ', 'Emergency Call-outs', 'revenue', '4300', None, True, 4330),
    ('4900', 'إيرادات أخرى', 'Other Revenue', 'revenue', '4000', None, False, 4900),
    ('4910', 'تسوية تحصيل مالك سابق', 'Prior-owner Settlement', 'revenue', '4900', 'revenue:تسوية مالك سابق', True, 4910),
    ('4920', 'إيرادات متنوعة', 'Miscellaneous Revenue', 'revenue', '4900', 'revenue:أخرى', True, 4920),

    ('5000', 'تكلفة الإيراد', 'Cost of Revenue', 'expense', None, None, False, 5000),
    ('5100', 'تكلفة قطع غيار مباعة', 'Cost of Parts Sold', 'expense', '5000', 'expense:قطع غيار', True, 5100),
    ('5200', 'مقاولو باطن — تركيب', 'Subcontractors — Installation', 'expense', '5000', None, True, 5200),
    ('5300', 'مواد تركيب مستهلكة', 'Consumed Installation Materials', 'expense', '5000', None, True, 5300),

    ('6000', 'المصروفات التشغيلية', 'Operating Expenses', 'expense', None, None, False, 6000),
    ('6100', 'الرواتب والمستحقات', 'Payroll', 'expense', '6000', None, False, 6100),
    ('6110', 'رواتب فنيين', 'Technician Salaries', 'expense', '6100', 'expense:رواتب', True, 6110),
    ('6120', 'رواتب إداريين', 'Admin Salaries', 'expense', '6100', None, True, 6120),
    ('6130', 'تأمينات اجتماعية — حصة الشركة', 'GOSI — Employer Share', 'expense', '6100', None, True, 6130),
    ('6140', 'بدلات سكن وانتقال', 'Housing & Transport Allowances', 'expense', '6100', None, True, 6140),
    ('6200', 'الأسطول', 'Fleet', 'expense', '6000', None, False, 6200),
    ('6210', 'محروقات', 'Fuel', 'expense', '6200', 'expense:محروقات', True, 6210),
    ('6220', 'صيانة سيارات', 'Vehicle Maintenance', 'expense', '6200', 'expense:صيانة سيارات', True, 6220),
    ('6230', 'تأمين سيارات', 'Vehicle Insurance', 'expense', '6200', None, True, 6230),
    ('6300', 'التشغيل الفني', 'Technical Operations', 'expense', '6000', None, False, 6300),
    ('6310', 'أدوات ومستلزمات', 'Tools & Supplies', 'expense', '6300', 'expense:أدوات', True, 6310),
    ('6320', 'فحوصات وسلامة', 'Inspections & Safety', 'expense', '6300', None, True, 6320),
    ('6400', 'إدارية وعمومية', 'General & Administrative', 'expense', '6000', None, False, 6400),
    ('6410', 'إيجار', 'Rent', 'expense', '6400', 'expense:إيجار', True, 6410),
    ('6420', 'كهرباء ومياه واتصالات', 'Utilities & Telecom', 'expense', '6400', None, True, 6420),
    ('6430', 'رسوم حكومية واشتراكات', 'Government Fees & Subscriptions', 'expense', '6400', None, True, 6430),
    ('6500', 'الاستهلاك', 'Depreciation', 'expense', '6000', None, False, 6500),
    ('6510', 'استهلاك مباني', 'Depreciation — Buildings', 'expense', '6500', None, True, 6510),
    ('6520', 'استهلاك سيارات', 'Depreciation — Vehicles', 'expense', '6500', None, True, 6520),
    ('6530', 'استهلاك معدات', 'Depreciation — Equipment', 'expense', '6500', None, True, 6530),
    ('6540', 'استهلاك أثاث', 'Depreciation — Furniture', 'expense', '6500', None, True, 6540),
    ('6550', 'استهلاك أجهزة', 'Depreciation — Computers', 'expense', '6500', None, True, 6550),
    ('6900', 'مصروفات أخرى', 'Other Expenses', 'expense', '6000', None, False, 6900),
    ('6910', 'مصروفات متنوعة', 'Miscellaneous Expenses', 'expense', '6900', 'expense:أخرى', True, 6910),
]

ACCOUNT_TYPE_LABELS = {
    'asset': 'أصول',
    'liability': 'خصوم',
    'equity': 'حقوق ملكية',
    'revenue': 'إيرادات',
    'expense': 'مصروفات',
}

_REVENUE_TYPE_ALIASES = {
    'عقد صيانة': 'revenue:عقد صيانة',
    'صيانة': 'revenue:عقد صيانة',
    'تجديد عقد': 'revenue:تجديد عقد',
    'تجديد': 'revenue:تجديد عقد',
    'الدفعات المستحقة': 'revenue:تجديد عقد',
    'دفعات مستحقة': 'revenue:تجديد عقد',
    'عقد جديد': 'revenue:عقد جديد',
    'عقد تركيب': 'revenue:عقد جديد',
    'تركيب': 'revenue:عقد جديد',
    'عقد تحديث': 'revenue:عقد تحديث',
    'تحديث': 'revenue:عقد تحديث',
    'ضمان': 'revenue:عقد صيانة',
    'قطع غيار': 'revenue:قطع غيار',
    'بيع قطع غيار': 'revenue:قطع غيار',
    'أعمال إضافية': 'revenue:أعمال إضافية',
    'زيارة': 'revenue:أعمال إضافية',
    'أخرى': 'revenue:أخرى',
    'إيرادات متنوعة': 'revenue:أخرى',
}

# خيارات نموذج «إضافة مصروف» — مطابقة لحسابات شجرة الدخل
EXPENSE_TYPE_OPTIONS = [
    'محروقات',
    'قطع غيار',
    'صيانة سيارات',
    'رواتب',
    'أدوات',
    'إيجار',
    'مصروفات متنوعة',
]

_EXPENSE_TYPE_ALIASES = {
    'محروقات': 'expense:محروقات',
    'وقود': 'expense:محروقات',
    'قطع غيار': 'expense:قطع غيار',
    'صيانة سيارات': 'expense:صيانة سيارات',
    'رواتب': 'expense:رواتب',
    'رواتب فنيين': 'expense:رواتب',
    'أجور': 'expense:رواتب',
    'أدوات': 'expense:أدوات',
    'أدوات ومستلزمات': 'expense:أدوات',
    'إيجار': 'expense:إيجار',
    'ايجار': 'expense:إيجار',
    'مصروفات متنوعة': 'expense:أخرى',
    'متنوعة': 'expense:أخرى',
    'ضيافة': 'expense:أخرى',
    'أخرى': 'expense:أخرى',
}

# حسابات إيراد عقود الصيانة في القيود — تُستبدل بإيراد مستحق بالزيارات في قائمة الدخل
MAINTENANCE_REVENUE_ACCOUNT_CODES = frozenset({'4110', '4120'})


def _is_prior_owner_note(notes: str | None) -> bool:
    text = notes or ''
    return 'مالك سابق' in text or 'تحصيل مالك سابق' in text or 'قبل استلام جما' in text


def ensure_chart_for_org(organization_id: int | None) -> int:
    """إنشاء الشجرة الافتراضية للمستأجر إن لم تكن موجودة. يرجع عدد الحسابات المضافة."""
    if not organization_id:
        return 0
    existing = {
        (a.code or '').strip(): a
        for a in (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=organization_id)
            .all()
        )
    }
    if existing:
        # أكمل الحسابات الناقصة فقط (لا تكرر)
        added = 0
        map_keys_patched = 0
        code_to_id = {c: a.id for c, a in existing.items()}
        for code, name, name_en, atype, parent_code, map_key, postable, sort in DEFAULT_CHART:
            if code in existing:
                acc = existing[code]
                if map_key and not (acc.map_key or '').strip():
                    acc.map_key = map_key
                    map_keys_patched += 1
                continue
            parent_id = code_to_id.get(parent_code) if parent_code else None
            acc = Account(
                organization_id=organization_id,
                code=code,
                name=name,
                name_en=name_en,
                account_type=atype,
                parent_id=parent_id,
                map_key=map_key,
                is_postable=postable,
                is_system=True,
                is_active=True,
                sort_order=sort,
            )
            db.session.add(acc)
            db.session.flush()
            code_to_id[code] = acc.id
            existing[code] = acc
            added += 1
        if added or map_keys_patched:
            db.session.commit()
        return added

    code_to_id: dict[str, int] = {}
    for code, name, name_en, atype, parent_code, map_key, postable, sort in DEFAULT_CHART:
        parent_id = code_to_id.get(parent_code) if parent_code else None
        acc = Account(
            organization_id=organization_id,
            code=code,
            name=name,
            name_en=name_en,
            account_type=atype,
            parent_id=parent_id,
            map_key=map_key,
            is_postable=postable,
            is_system=True,
            is_active=True,
            sort_order=sort,
        )
        db.session.add(acc)
        db.session.flush()
        code_to_id[code] = acc.id
    db.session.commit()
    return len(DEFAULT_CHART)


ROOT_GROUPS = [row for row in DEFAULT_CHART if row[4] is None]


def seed_root_groups_for_org(organization_id: int | None) -> int:
    """ينشئ مجموعات المستوى الأول فقط (أصول/خصوم/ملكية/إيرادات/مصروفات) دون الحسابات التفصيلية."""
    if not organization_id:
        return 0
    existing = {
        (a.code or '').strip()
        for a in (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=organization_id)
            .all()
        )
    }
    added = 0
    for code, name, name_en, atype, _parent, map_key, postable, sort in ROOT_GROUPS:
        if code in existing:
            continue
        db.session.add(Account(
            organization_id=organization_id,
            code=code,
            name=name,
            name_en=name_en,
            account_type=atype,
            parent_id=None,
            map_key=map_key,
            is_postable=postable,
            is_system=True,
            is_active=True,
            sort_order=sort,
        ))
        existing.add(code)
        added += 1
    if added:
        db.session.commit()
    return added


def account_by_map_key(map_key: str | None) -> Account | None:
    if not map_key:
        return None
    return (
        tenant_query(Account)
        .filter_by(map_key=map_key, is_active=True)
        .order_by(Account.sort_order.asc())
        .first()
    )


def resolve_revenue_account_id(revenue_type: str | None, notes: str | None = None) -> int | None:
    if _is_prior_owner_note(notes):
        acc = account_by_map_key('revenue:تسوية مالك سابق')
        if acc:
            return acc.id
    raw = (revenue_type or '').strip()
    key = _REVENUE_TYPE_ALIASES.get(raw)
    if not key:
        for alias, mk in _REVENUE_TYPE_ALIASES.items():
            if alias in raw:
                key = mk
                break
    if not key:
        key = 'revenue:أعمال إضافية'
    acc = account_by_map_key(key)
    return acc.id if acc else None


def resolve_expense_account_id(expense_type: str | None) -> int | None:
    raw = (expense_type or '').strip()
    key = _EXPENSE_TYPE_ALIASES.get(raw)
    if not key:
        for alias, mk in _EXPENSE_TYPE_ALIASES.items():
            if alias in raw:
                key = mk
                break
    if not key:
        key = 'expense:أخرى'
    acc = account_by_map_key(key)
    return acc.id if acc else None


def accounts_tree_rows(organization_id: int | None = None) -> list[dict]:
    """صفوف مسطّحة مرتبة للعرض الشجري."""
    if organization_id is None:
        q = tenant_query(Account)
    else:
        q = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=organization_id
        )
    accounts = q.order_by(Account.sort_order.asc(), Account.code.asc()).all()
    by_parent: dict[int | None, list[Account]] = {}
    for a in accounts:
        by_parent.setdefault(a.parent_id, []).append(a)

    rows: list[dict] = []

    def walk(parent_id: int | None, depth: int):
        for a in by_parent.get(parent_id, []):
            rows.append({
                'id': a.id,
                'code': a.code,
                'name': a.name,
                'name_en': a.name_en or '',
                'account_type': a.account_type,
                'type_label': ACCOUNT_TYPE_LABELS.get(a.account_type or '', a.account_type or ''),
                'map_key': a.map_key or '',
                'is_postable': bool(a.is_postable),
                'is_system': bool(a.is_system),
                'is_active': bool(a.is_active),
                'parent_id': a.parent_id,
                'depth': depth,
                'sort_order': a.sort_order or 0,
                'notes': a.notes or '',
                'has_children': bool(by_parent.get(a.id)),
            })
            walk(a.id, depth + 1)

    walk(None, 0)
    return rows


def backfill_missing_account_links(limit: int = 5000) -> dict[str, int]:
    """يربط الإيرادات/المصروفات القديمة بالحساب المناسب إن كان account_id فارغاً."""
    from models import Expense, Revenue

    stats = {'revenues': 0, 'expenses': 0}
    for rev in tenant_query(Revenue).filter(Revenue.account_id.is_(None)).limit(limit).all():
        aid = resolve_revenue_account_id(rev.revenue_type, rev.notes)
        if aid:
            rev.account_id = aid
            stats['revenues'] += 1
    for exp in tenant_query(Expense).filter(Expense.account_id.is_(None)).limit(limit).all():
        aid = resolve_expense_account_id(exp.expense_type)
        if aid:
            exp.account_id = aid
            stats['expenses'] += 1
    if stats['revenues'] or stats['expenses']:
        db.session.commit()
    return stats


def create_custom_account(
    *,
    code: str,
    name: str,
    account_type: str,
    parent_id: int | None = None,
    is_postable: bool = True,
    name_en: str = '',
    notes: str = '',
) -> Account:
    """إنشاء حساب جديد في شجرة المستأجر الحالي."""
    from tenant_scope import assign_organization, effective_organization_id

    ensure_chart_schema()
    oid = effective_organization_id()
    if not oid:
        raise ValueError('المؤسسة غير معروفة')

    code = (code or '').strip()
    name = (name or '').strip()
    name_en = (name_en or '').strip()[:200]
    notes = (notes or '').strip() or None
    account_type = (account_type or '').strip()

    if not code:
        raise ValueError('كود الحساب مطلوب')
    if len(code) > 20:
        raise ValueError('كود الحساب طويل جداً')
    if not name:
        raise ValueError('اسم الحساب مطلوب')
    if account_type not in ACCOUNT_TYPE_LABELS:
        raise ValueError('نوع الحساب غير صالح')

    dup = (
        Account.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid, code=code)
        .first()
    )
    if dup:
        raise ValueError(f'الكود {code} مستخدم مسبقاً')

    parent = None
    if parent_id:
        parent = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(id=parent_id, organization_id=oid)
            .first()
        )
        if not parent:
            raise ValueError('الحساب الأب غير موجود')
        if parent.account_type != account_type:
            raise ValueError('نوع الحساب يجب أن يطابق الحساب الأب')

    digits = ''.join(ch for ch in code if ch.isdigit())
    try:
        sort_order = int(digits) if digits else 9000
    except ValueError:
        sort_order = 9000

    acc = Account(
        code=code,
        name=name[:200],
        name_en=name_en or None,
        account_type=account_type,
        parent_id=parent.id if parent else None,
        map_key=None,
        is_postable=bool(is_postable),
        is_system=False,
        is_active=True,
        sort_order=sort_order,
        notes=notes,
    )
    assign_organization(acc)
    db.session.add(acc)
    db.session.flush()
    return acc


def _sort_order_from_code(code: str) -> int:
    digits = ''.join(ch for ch in code if ch.isdigit())
    try:
        return int(digits) if digits else 9000
    except ValueError:
        return 9000


def _descendant_ids(account_id: int, organization_id: int) -> set[int]:
    children_by_parent: dict[int | None, list[int]] = {}
    for row in (
        Account.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=organization_id)
        .all()
    ):
        children_by_parent.setdefault(row.parent_id, []).append(row.id)
    found: set[int] = set()
    stack = list(children_by_parent.get(account_id, []))
    while stack:
        cid = stack.pop()
        if cid in found:
            continue
        found.add(cid)
        stack.extend(children_by_parent.get(cid, []))
    return found


def update_account(
    account_id: int,
    *,
    code: str,
    name: str,
    account_type: str,
    parent_id: int | None = None,
    is_postable: bool = True,
    is_active: bool = True,
    name_en: str = '',
    notes: str = '',
) -> Account:
    """تعديل حساب في شجرة المستأجر الحالي."""
    from tenant_scope import effective_organization_id

    ensure_chart_schema()
    oid = effective_organization_id()
    if not oid:
        raise ValueError('المؤسسة غير معروفة')

    acc = (
        Account.query.execution_options(skip_tenant=True)
        .filter_by(id=account_id, organization_id=oid)
        .first()
    )
    if not acc:
        raise ValueError('الحساب غير موجود')

    code = (code or '').strip()
    name = (name or '').strip()
    name_en = (name_en or '').strip()[:200]
    notes = (notes or '').strip() or None
    account_type = (account_type or '').strip()

    if not code:
        raise ValueError('كود الحساب مطلوب')
    if len(code) > 20:
        raise ValueError('كود الحساب طويل جداً')
    if not name:
        raise ValueError('اسم الحساب مطلوب')
    if account_type not in ACCOUNT_TYPE_LABELS:
        raise ValueError('نوع الحساب غير صالح')

    dup = (
        Account.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid, code=code)
        .filter(Account.id != acc.id)
        .first()
    )
    if dup:
        raise ValueError(f'الكود {code} مستخدم مسبقاً')

    parent = None
    if parent_id:
        if int(parent_id) == acc.id:
            raise ValueError('لا يمكن أن يكون الحساب أباً لنفسه')
        if int(parent_id) in _descendant_ids(acc.id, oid):
            raise ValueError('لا يمكن نقل الحساب تحت أحد فروعه')
        parent = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(id=parent_id, organization_id=oid)
            .first()
        )
        if not parent:
            raise ValueError('الحساب الأب غير موجود')
        if parent.account_type != account_type:
            raise ValueError('نوع الحساب يجب أن يطابق الحساب الأب')

    has_children = (
        Account.query.execution_options(skip_tenant=True)
        .filter_by(parent_id=acc.id, organization_id=oid)
        .first()
        is not None
    )
    if has_children and account_type != acc.account_type:
        raise ValueError('لا يمكن تغيير النوع لحساب له فروع')

    if account_type != acc.account_type:
        from models import JournalLine

        has_lines = (
            JournalLine.query.execution_options(skip_tenant=True)
            .filter_by(account_id=acc.id, organization_id=oid)
            .first()
        )
        if has_lines:
            raise ValueError('لا يمكن تغيير النوع بعد ترحيل قيود على هذا الحساب')

    acc.code = code
    acc.name = name[:200]
    acc.name_en = name_en or None
    acc.account_type = account_type
    acc.parent_id = parent.id if parent else None
    acc.is_postable = bool(is_postable)
    acc.is_active = bool(is_active)
    acc.notes = notes
    acc.sort_order = _sort_order_from_code(code)
    db.session.flush()
    return acc


def delete_account(account_id: int) -> tuple[str, str]:
    """حذف حساب واحد. يُرفض إن كان له فروع أو قيود مرحّلة."""
    from models import Expense, JournalLine, Revenue
    from tenant_scope import effective_organization_id

    ensure_chart_schema()
    oid = effective_organization_id()
    if not oid:
        raise ValueError('المؤسسة غير معروفة')

    acc = (
        Account.query.execution_options(skip_tenant=True)
        .filter_by(id=account_id, organization_id=oid)
        .first()
    )
    if not acc:
        raise ValueError('الحساب غير موجود')

    has_children = (
        Account.query.execution_options(skip_tenant=True)
        .filter_by(parent_id=acc.id, organization_id=oid)
        .first()
        is not None
    )
    if has_children:
        raise ValueError('لا يمكن حذف حساب له فروع — احذف الفروع أولاً')

    insp = inspect(db.engine)
    if 'journal_lines' in set(insp.get_table_names()):
        has_lines = (
            JournalLine.query.execution_options(skip_tenant=True)
            .filter_by(account_id=acc.id, organization_id=oid)
            .first()
        )
        if has_lines:
            raise ValueError('لا يمكن حذف حساب عليه قيود يومية')

    skip = {'synchronize_session': False}
    (
        Revenue.query.execution_options(skip_tenant=True)
        .filter_by(account_id=acc.id, organization_id=oid)
        .update({Revenue.account_id: None}, **skip)
    )
    (
        Expense.query.execution_options(skip_tenant=True)
        .filter_by(account_id=acc.id, organization_id=oid)
        .update({Expense.account_id: None}, **skip)
    )

    code, name = acc.code, acc.name
    db.session.delete(acc)
    db.session.flush()
    return code, name


def wipe_chart_for_org(organization_id: int | None) -> dict[str, int]:
    """حذف شجرة الحسابات والقيود للمستأجر فقط. الإيرادات/المصروفات تبقى مع فك الربط."""
    from models import Expense, JournalEntry, JournalLine, Revenue

    if not organization_id:
        return {'accounts': 0, 'journals': 0, 'lines': 0}

    ensure_chart_schema()
    skip = {'synchronize_session': False}
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())

    n_lines = 0
    n_journals = 0
    if 'journal_lines' in tables:
        n_lines = (
            JournalLine.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=organization_id)
            .delete(**skip)
        )
    if 'journal_entries' in tables:
        n_journals = (
            JournalEntry.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=organization_id)
            .delete(**skip)
        )
    (
        Revenue.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=organization_id)
        .update({Revenue.account_id: None}, **skip)
    )
    (
        Expense.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=organization_id)
        .update({Expense.account_id: None}, **skip)
    )
    (
        Account.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=organization_id)
        .update({Account.parent_id: None}, **skip)
    )
    n_accounts = (
        Account.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=organization_id)
        .delete(**skip)
    )
    db.session.commit()
    return {
        'accounts': int(n_accounts or 0),
        'journals': int(n_journals or 0),
        'lines': int(n_lines or 0),
    }
