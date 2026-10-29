"""دورة حياة مستأجر المنصة: تصدير بيانات عميل + تفريغ/حذف الحساب."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime, timezone

from flask import g

# جداول التشغيل المصدَّرة (ترتيب منطقي للقراءة)
EXPORT_TABLES: tuple[tuple[str, str], ...] = (
    ('users', 'User'),
    ('settings', 'Settings'),
    ('signatories', 'Signatory'),
    ('customers', 'Customer'),
    ('technicians', 'Technician'),
    ('technician_documents', 'TechnicianDocument'),
    ('maintenance_teams', 'MaintenanceTeam'),
    ('inventory_items', 'InventoryItem'),
    ('elevators', 'Elevator'),
    ('contracts', 'Contract'),
    ('contract_elevators', 'ContractElevator'),
    ('maintenance_visits', 'MaintenanceVisit'),
    ('visit_technicians', 'VisitTechnician'),
    ('faults', 'Fault'),
    ('fault_technicians', 'FaultTechnician'),
    ('whatsapp_inbox', 'WhatsAppInbox'),
    ('revenues', 'Revenue'),
    ('expenses', 'Expense'),
    ('invoices', 'Invoice'),
    ('stock_movements', 'StockMovement'),
    ('parts_billing', 'PartsBilling'),
    ('purchase_orders', 'PurchaseOrder'),
    ('purchase_order_lines', 'PurchaseOrderLine'),
    ('elevator_estimates', 'ElevatorEstimate'),
    ('elevator_estimate_lines', 'ElevatorEstimateLine'),
    ('zatca_credentials', 'ZatcaCredentials'),
    ('audit_logs', 'AuditLog'),
    ('platform_payments', 'PlatformPayment'),
    ('onboarding_invites', 'OnboardingInvite'),
    ('fault_events', 'FaultEvent'),
    ('accounts', 'Account'),
    ('journal_entries', 'JournalEntry'),
    ('journal_lines', 'JournalLine'),
    ('fiscal_years', 'FiscalYear'),
    ('customer_opening_balances', 'CustomerOpeningBalance'),
    ('suppliers', 'Supplier'),
    ('supplier_prices', 'SupplierPrice'),
    ('supplier_quote_requests', 'SupplierQuoteRequest'),
    ('supplier_quote_request_lines', 'SupplierQuoteRequestLine'),
    ('maintenance_quotes', 'MaintenanceQuote'),
    ('maintenance_quote_elevators', 'MaintenanceQuoteElevator'),
    ('maintenance_quote_surveys', 'MaintenanceQuoteSurvey'),
    ('maintenance_quote_survey_units', 'MaintenanceQuoteSurveyUnit'),
    ('external_elevator_inspections', 'ExternalElevatorInspection'),
    ('attendance_branches', 'AttendanceBranch'),
    ('attendance_employees', 'AttendanceEmployee'),
    ('biometric_devices', 'BiometricDevice'),
    ('attendance_punches', 'AttendancePunch'),
    ('attendance_days', 'AttendanceDay'),
    ('installation_leads', 'InstallLead'),
    ('installation_projects', 'InstallProject'),
    ('installation_quotations', 'InstallQuotation'),
    ('installation_quotation_lines', 'InstallQuotationLine'),
    ('installation_timeline_steps', 'InstallTimelineStep'),
    ('installation_project_costs', 'InstallProjectCostItem'),
    ('installation_project_receipts', 'InstallProjectReceipt'),
    ('installation_project_documents', 'InstallProjectDocument'),
    ('installation_contracts', 'InstallContract'),
    ('installation_contract_installments', 'InstallContractInstallment'),
    ('installation_contract_documents', 'InstallContractDocument'),
)

# تذكير مدير الشركة بتنزيل نسخة على جهازه. 0 = إيقاف التذكير.
BACKUP_REMIND_DEFAULT_DAYS = 30
BACKUP_REMIND_DAY_CHOICES = (7, 14, 30, 60, 90)
BACKUP_SNOOZE_DAYS = 7

# حقول حساسة — لا تُسلَّم في تصدير المنصة (hashes / مفاتيح / أسرار)
EXPORT_REDACT_MARKER = '[REDACTED]'
EXPORT_SENSITIVE_FIELDS: dict[str, frozenset[str]] = {
    'users': frozenset({'password_hash'}),
    'technicians': frozenset({'sign_pin_hash'}),
    'signatories': frozenset({'sign_pin_hash'}),
    'settings': frozenset({'rep_sign_pin_hash', 'google_maps_api_key'}),
    'zatca_credentials': frozenset({
        'private_key', 'api_secret', 'csid', 'certificate',
    }),
    'onboarding_invites': frozenset({'token'}),
    'biometric_devices': frozenset({'auth_token'}),
}


def _model_map():
    from models import (
        Account,
        AttendanceBranch,
        AttendanceDay,
        AttendanceEmployee,
        AttendancePunch,
        AuditLog,
        BiometricDevice,
        Contract,
        ContractElevator,
        Customer,
        CustomerOpeningBalance,
        Elevator,
        ElevatorEstimate,
        ElevatorEstimateLine,
        Expense,
        ExternalElevatorInspection,
        Fault,
        FaultEvent,
        FaultTechnician,
        FiscalYear,
        InventoryItem,
        Invoice,
        JournalEntry,
        JournalLine,
        MaintenanceQuote,
        MaintenanceQuoteElevator,
        MaintenanceQuoteSurvey,
        MaintenanceQuoteSurveyUnit,
        MaintenanceTeam,
        MaintenanceVisit,
        OnboardingInvite,
        PartsBilling,
        PlatformPayment,
        PurchaseOrder,
        PurchaseOrderLine,
        Revenue,
        Settings,
        Signatory,
        StockMovement,
        Supplier,
        SupplierPrice,
        SupplierQuoteRequest,
        SupplierQuoteRequestLine,
        Technician,
        TechnicianDocument,
        User,
        VisitTechnician,
        WhatsAppInbox,
        ZatcaCredentials,
    )
    from installation.models import (
        InstallContract,
        InstallContractDocument,
        InstallContractInstallment,
        InstallLead,
        InstallProject,
        InstallProjectCostItem,
        InstallProjectDocument,
        InstallProjectReceipt,
        InstallQuotation,
        InstallQuotationLine,
        InstallTimelineStep,
    )

    return {
        'User': User,
        'Settings': Settings,
        'Signatory': Signatory,
        'Customer': Customer,
        'Technician': Technician,
        'TechnicianDocument': TechnicianDocument,
        'MaintenanceTeam': MaintenanceTeam,
        'InventoryItem': InventoryItem,
        'Elevator': Elevator,
        'Contract': Contract,
        'ContractElevator': ContractElevator,
        'MaintenanceVisit': MaintenanceVisit,
        'VisitTechnician': VisitTechnician,
        'Fault': Fault,
        'FaultEvent': FaultEvent,
        'FaultTechnician': FaultTechnician,
        'WhatsAppInbox': WhatsAppInbox,
        'Revenue': Revenue,
        'Expense': Expense,
        'Invoice': Invoice,
        'Account': Account,
        'JournalEntry': JournalEntry,
        'JournalLine': JournalLine,
        'FiscalYear': FiscalYear,
        'CustomerOpeningBalance': CustomerOpeningBalance,
        'StockMovement': StockMovement,
        'PartsBilling': PartsBilling,
        'PurchaseOrder': PurchaseOrder,
        'PurchaseOrderLine': PurchaseOrderLine,
        'Supplier': Supplier,
        'SupplierPrice': SupplierPrice,
        'SupplierQuoteRequest': SupplierQuoteRequest,
        'SupplierQuoteRequestLine': SupplierQuoteRequestLine,
        'MaintenanceQuote': MaintenanceQuote,
        'MaintenanceQuoteElevator': MaintenanceQuoteElevator,
        'MaintenanceQuoteSurvey': MaintenanceQuoteSurvey,
        'MaintenanceQuoteSurveyUnit': MaintenanceQuoteSurveyUnit,
        'ExternalElevatorInspection': ExternalElevatorInspection,
        'ElevatorEstimate': ElevatorEstimate,
        'ElevatorEstimateLine': ElevatorEstimateLine,
        'AttendanceBranch': AttendanceBranch,
        'AttendanceEmployee': AttendanceEmployee,
        'BiometricDevice': BiometricDevice,
        'AttendancePunch': AttendancePunch,
        'AttendanceDay': AttendanceDay,
        'InstallLead': InstallLead,
        'InstallProject': InstallProject,
        'InstallQuotation': InstallQuotation,
        'InstallQuotationLine': InstallQuotationLine,
        'InstallTimelineStep': InstallTimelineStep,
        'InstallProjectCostItem': InstallProjectCostItem,
        'InstallProjectReceipt': InstallProjectReceipt,
        'InstallProjectDocument': InstallProjectDocument,
        'InstallContract': InstallContract,
        'InstallContractInstallment': InstallContractInstallment,
        'InstallContractDocument': InstallContractDocument,
        'ZatcaCredentials': ZatcaCredentials,
        'AuditLog': AuditLog,
        'PlatformPayment': PlatformPayment,
        'OnboardingInvite': OnboardingInvite,
    }


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return None
    if isinstance(value, bool):
        return value
    return value


def _row_to_dict(row) -> dict:
    data = {}
    for col in row.__table__.columns:
        data[col.name] = _serialize(getattr(row, col.name))
    return data


def _sanitize_export_row(table_name: str, data: dict) -> dict:
    """يحذف/يستبدل الحقول الحساسة قبل كتابة ملف التصدير."""
    sensitive = EXPORT_SENSITIVE_FIELDS.get(table_name)
    if not sensitive:
        return data
    out = dict(data)
    for field in sensitive:
        if field not in out:
            continue
        raw = out.get(field)
        present = raw not in (None, '', b'', EXPORT_REDACT_MARKER)
        out[field] = EXPORT_REDACT_MARKER if present else None
        # إشارة غير سرّية لإعادة التهيئة لاحقاً (بدون كشف القيمة)
        flag = f'{field}_was_set'
        if flag not in out:
            out[flag] = bool(present)
    return out


def _org_meta(org) -> dict:
    return {
        'id': org.id,
        'slug': org.slug,
        'name': org.name,
        'name_en': getattr(org, 'name_en', None),
        'status': org.status,
        'plan': org.plan,
        'admin_email': org.admin_email,
        'created_at': _serialize(getattr(org, 'created_at', None)),
        'trial_ends_at': _serialize(getattr(org, 'trial_ends_at', None)),
        'suspended_at': _serialize(getattr(org, 'suspended_at', None)),
        'billing_cycle': getattr(org, 'billing_cycle', None),
        'billing_amount': getattr(org, 'billing_amount', None),
        'billing_status': getattr(org, 'billing_status', None),
        'notes': org.notes,
    }


def export_tenant_payload(org) -> dict:
    """تصدير كل بيانات المؤسسة إلى dict قابل للـ JSON."""
    models = _model_map()
    org_id = org.id
    tables: dict[str, list] = {}
    counts: dict[str, int] = {}

    present = _present_table_names()
    skipped: list[str] = []

    prev = getattr(g, '_resolving_default_org', False)
    g._resolving_default_org = True
    try:
        for table_name, model_name in EXPORT_TABLES:
            if present and table_name not in present:
                skipped.append(table_name)
                continue
            model = models[model_name]
            q = model.query.execution_options(skip_tenant=True)
            if hasattr(model, 'organization_id'):
                q = q.filter_by(organization_id=org_id)
            else:
                continue
            rows = q.order_by(model.id).all()
            tables[table_name] = [
                _sanitize_export_row(table_name, _row_to_dict(r)) for r in rows
            ]
            counts[table_name] = len(rows)
    finally:
        g._resolving_default_org = prev

    payload = {
        'version': 2,
        'format': 'liftcore-tenant-export',
        'exported_at': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'organization': _org_meta(org),
        'security': {
            'redacted_fields': {
                table: sorted(fields)
                for table, fields in EXPORT_SENSITIVE_FIELDS.items()
            },
            'note': (
                'Password hashes, PIN hashes, ZATCA keys/secrets, invite tokens, '
                'biometric device tokens, and Maps API keys are redacted. '
                'Re-set credentials after restore.'
            ),
        },
        'counts': counts,
        'tables': tables,
    }
    if skipped:
        payload['skipped_tables'] = skipped
    return payload


def _present_table_names() -> set[str]:
    try:
        from app import db
        from sqlalchemy import inspect
        return set(inspect(db.engine).get_table_names())
    except Exception:
        return set()


def build_tenant_export_zip(org) -> tuple[bytes, str, dict]:
    """يرجع (محتوى zip، اسم الملف، الملخص)."""
    payload = export_tenant_payload(org)
    slug = (org.slug or f'org-{org.id}').strip().lower()
    ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    filename = f'liftcore-{slug}-export-{ts}.zip'
    json_name = f'liftcore-{slug}-data.json'

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            json_name,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            'README.txt',
            (
                'LiftCore — نسخة احتياطية لبيانات عميل\n'
                f"المؤسسة: {org.name}\n"
                f"المعرّف: {slug}\n"
                f"التاريخ: {payload['exported_at']}\n"
                f"اسم الملف: {filename}\n"
                f"الملف الرئيسي: {json_name}\n"
                '\n'
                'اسم الملف مؤرخ (UTC) حتى تميّز كل نسخة على جهازك.\n'
                'احفظ هذا الملف خارج المتصفح — على القرص أو وحدة تخزين خاصة بك.\n'
                'لا يحتوي على ملفات الوسائط المرفوعة (الصور/PDF) — فقط سجلات قاعدة البيانات.\n'
                '\n'
                'أمني: تم تهذيب الحقول الحساسة (كلمات مرور مشفّرة، PIN، مفاتيح ZATCA،\n'
                'أسرار API، رموز الدعوات، رمز جهاز البصمة، مفتاح خرائط).\n'
                'أعِد ضبط الاعتمادات بعد الاستعادة.\n'
            ),
        )
    return buf.getvalue(), filename, payload.get('counts') or {}


def normalize_backup_remind_days(value) -> int:
    """0 يوقف التذكير. أي قيمة أخرى تُقرَّب لأقرب خيار مسموح."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        return BACKUP_REMIND_DEFAULT_DAYS
    if days == 0:
        return 0
    if days in BACKUP_REMIND_DAY_CHOICES:
        return days
    return BACKUP_REMIND_DEFAULT_DAYS


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_backup_stamp(value) -> str:
    """وقت التنزيل بتوقيت الرياض للعرض داخل الواجهة."""
    if not value:
        return ''
    try:
        from zoneinfo import ZoneInfo
        local = _as_utc(value).astimezone(ZoneInfo('Asia/Riyadh'))
    except Exception:
        local = _as_utc(value)
    return local.strftime('%Y-%m-%d %H:%M')


def data_backup_status(settings) -> dict:
    """هل حان تذكير المدير بتنزيل نسخة على جهازه."""
    raw_days = getattr(settings, 'data_backup_remind_days', None) if settings else None
    remind_days = (
        BACKUP_REMIND_DEFAULT_DAYS if raw_days is None
        else normalize_backup_remind_days(raw_days)
    )
    last = getattr(settings, 'last_data_backup_at', None) if settings else None
    age_days = None
    due = False
    if remind_days > 0:
        if last is None:
            due = True
        else:
            age = datetime.now(timezone.utc) - _as_utc(last)
            age_days = max(0, age.days)
            due = age_days >= remind_days
    return {
        'remind_days': remind_days,
        'last_at': last,
        'last_label': format_backup_stamp(last),
        'age_days': age_days,
        'due': due,
        'never': last is None,
        'snooze_days': BACKUP_SNOOZE_DAYS,
    }


def is_protected_operator_org(org) -> bool:
    from platform_admin import operator_org_slugs

    slug = (getattr(org, 'slug', '') or '').strip().lower()
    return slug in operator_org_slugs() or slug in ('default', 'app', 'liftcore', 'platform')


def _count(model, org_id: int) -> int:
    return (
        model.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=org_id)
        .count()
    )


def _delete(model, org_id: int) -> int:
    q = model.query.execution_options(skip_tenant=True).filter_by(organization_id=org_id)
    n = q.count()
    if n:
        q.delete(synchronize_session=False)
    return n


def _null_fk(model, org_id: int, *columns) -> None:
    rows = (
        model.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=org_id)
        .all()
    )
    for row in rows:
        for col in columns:
            setattr(row, col, None)


def wipe_tenant(org, *, keep_users: bool, delete_organization: bool = False) -> dict:
    """تفريغ بيانات مستأجر؛ مع delete_organization يحذف المؤسسة نفسها."""
    from app import db, hash_password
    from models import (
        AuditLog,
        Contract,
        ContractElevator,
        Customer,
        Elevator,
        ElevatorEstimate,
        ElevatorEstimateLine,
        Expense,
        Fault,
        FaultTechnician,
        InventoryItem,
        Invoice,
        MaintenanceTeam,
        MaintenanceVisit,
        OnboardingInvite,
        PartsBilling,
        PlatformPayment,
        PurchaseOrder,
        PurchaseOrderLine,
        Revenue,
        Settings,
        Signatory,
        StockMovement,
        Technician,
        TechnicianDocument,
        User,
        VisitTechnician,
        WhatsAppInbox,
        ZatcaCredentials,
    )
    from tenant_scope import assign_organization

    try:
        import installation.models as im
    except Exception:
        im = None

    if delete_organization and is_protected_operator_org(org):
        raise ValueError('لا يمكن حذف مؤسسة مشغّل المنصة (default).')

    org_id = org.id
    org_slug = org.slug
    g.organization = org
    g.organization_id = org_id

    stats_before = {
        'customers': _count(Customer, org_id),
        'elevators': _count(Elevator, org_id),
        'contracts': _count(Contract, org_id),
        'visits': _count(MaintenanceVisit, org_id),
        'faults': _count(Fault, org_id),
        'technicians': _count(Technician, org_id),
        'users': _count(User, org_id),
        'inventory': _count(InventoryItem, org_id),
        'whatsapp': _count(WhatsAppInbox, org_id),
    }

    deleted: dict[str, int] = {}

    visit_ids = [
        r.id for r in (
            MaintenanceVisit.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org_id).with_entities(MaintenanceVisit.id).all()
        )
    ]
    fault_ids = [
        r.id for r in (
            Fault.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org_id).with_entities(Fault.id).all()
        )
    ]
    if visit_ids:
        deleted['visit_technicians_by_visit'] = (
            VisitTechnician.query.execution_options(skip_tenant=True)
            .filter(VisitTechnician.visit_id.in_(visit_ids))
            .delete(synchronize_session=False)
        )
    if fault_ids:
        deleted['fault_technicians_by_fault'] = (
            FaultTechnician.query.execution_options(skip_tenant=True)
            .filter(FaultTechnician.fault_id.in_(fault_ids))
            .delete(synchronize_session=False)
        )

    _null_fk(MaintenanceVisit, org_id, 'fault_id')
    _null_fk(Fault, org_id, 'visit_id')
    # إيراد ↔ فاتورة (FK متبادل) + فاتورة أب/ابن + ربط قطع الغيار — فكّ قبل الحذف
    _null_fk(Invoice, org_id, 'revenue_id', 'parent_invoice_id', 'parts_billing_id')
    _null_fk(Revenue, org_id, 'invoice_id', 'parts_billing_id')
    db.session.commit()

    if im is not None:
        for label, model in (
            ('install_timeline', getattr(im, 'InstallTimelineStep', None)),
            ('install_quote_lines', getattr(im, 'InstallQuotationLine', None)),
            ('install_quotes', getattr(im, 'InstallQuotation', None)),
            ('install_projects', getattr(im, 'InstallProject', None)),
            ('install_leads', getattr(im, 'InstallLead', None)),
        ):
            if model is not None and hasattr(model, 'organization_id'):
                deleted[label] = _delete(model, org_id)

    wipe_order = (
        ('visit_technicians', VisitTechnician),
        ('fault_technicians', FaultTechnician),
        ('stock_movements', StockMovement),
        ('parts_billing', PartsBilling),
        ('po_lines', PurchaseOrderLine),
        ('purchase_orders', PurchaseOrder),
        ('estimate_lines', ElevatorEstimateLine),
        ('estimates', ElevatorEstimate),
        # الفواتير قبل الإيرادات (بعد فك FK المتبادل أعلاه)
        ('invoices', Invoice),
        ('revenues', Revenue),
        ('expenses', Expense),
        ('whatsapp_inbox', WhatsAppInbox),
        ('visits', MaintenanceVisit),
        ('faults', Fault),
        ('contract_elevators', ContractElevator),
        ('contracts', Contract),
        ('elevators', Elevator),
        ('tech_documents', TechnicianDocument),
        ('signatories', Signatory),
        ('maintenance_teams', MaintenanceTeam),
        ('technicians', Technician),
        ('inventory', InventoryItem),
        ('customers', Customer),
        ('audit_logs', AuditLog),
        ('zatca', ZatcaCredentials),
        ('settings', Settings),
        ('onboarding_invites', OnboardingInvite),
    )
    for label, model in wipe_order:
        deleted[label] = _delete(model, org_id)

    if delete_organization or not keep_users:
        deleted['users'] = _delete(User, org_id)

    deleted['platform_payments'] = (
        PlatformPayment.query.filter_by(organization_id=org_id)
        .delete(synchronize_session=False)
    )

    if delete_organization:
        db.session.delete(org)
        db.session.commit()
        return {
            'before': stats_before,
            'deleted': deleted,
            'after': {'organization': 'deleted', 'slug': org_slug},
            'organization_deleted': True,
            'slug': org_slug,
        }

    settings = Settings()
    assign_organization(settings)
    settings.company_name = org.name or org_slug
    settings.company_name_en = getattr(org, 'name_en', None) or org_slug
    db.session.add(settings)

    org.notes = (
        f'[{datetime.utcnow().date()}] WIPE — tenant data cleared from platform console'
    )
    db.session.add(org)

    if not keep_users:
        admin = User(
            username='admin',
            password_hash=hash_password('ChangeMeNow1'),
            full_name='مدير مؤقت — غيّر فوراً',
            email=org.admin_email or f'admin@{org_slug}.liftcoreapp.com',
            role='admin',
            is_active=True,
            must_change_password=True,
        )
        assign_organization(admin)
        db.session.add(admin)
        deleted['temp_admin'] = 1

    db.session.commit()

    stats_after = {
        'customers': _count(Customer, org_id),
        'elevators': _count(Elevator, org_id),
        'contracts': _count(Contract, org_id),
        'visits': _count(MaintenanceVisit, org_id),
        'faults': _count(Fault, org_id),
        'technicians': _count(Technician, org_id),
        'users': _count(User, org_id),
        'inventory': _count(InventoryItem, org_id),
        'whatsapp': _count(WhatsAppInbox, org_id),
    }
    return {
        'before': stats_before,
        'deleted': deleted,
        'after': stats_after,
        'organization_deleted': False,
        'slug': org_slug,
    }
