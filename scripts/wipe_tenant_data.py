#!/usr/bin/env python3
"""
تفريغ بيانات مستأجر جما بالكامل (عملاء/مصاعد/عقود/زيارات/أعطال/مخزن…).

يُبقي مؤسسة organizations، ويعيد ضبط الإعدادات.
لا يمسّ مستأجرين آخرين (default وغيره).

الاستخدام على السيرفر:
  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/wipe_tenant_data.py --slug jama --confirm JAMA_WIPE
  python scripts/kickoff_jama_formal.py   # إعادة مستخدمي الاختبار + اسم الشركة

خيارات:
  --keep-users     الإبقاء على المستخدمين الحاليين
  --print-only     عرض الإحصاءات دون حذف
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

COMPANY_AR = 'شركة تقنية جما التميز للمصاعد'
COMPANY_EN = 'Jama Elevator Excellence Tech Co.'
CONFIRM_TOKEN = 'JAMA_WIPE'


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


def wipe_tenant(org, *, keep_users: bool) -> dict:
    from app import db, hash_password
    from flask import g
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
        PartsBilling,
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

    org_id = org.id
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

    # فك الروابط الدائرية + حذف صفوف الربط عبر الآباء (حتى لو organization_id ناقص)
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
    db.session.commit()

    deleted: dict[str, int] = {}

    # التركيب أولاً إن وُجد
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
        ('revenues', Revenue),
        ('expenses', Expense),
        ('invoices', Invoice),
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
    )
    for label, model in wipe_order:
        deleted[label] = _delete(model, org_id)

    if not keep_users:
        deleted['users'] = _delete(User, org_id)

    # إعدادات نظيفة باسم الشركة الرسمي
    settings = (
        Settings.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=org_id)
        .first()
    )
    if not settings:
        settings = Settings()
        assign_organization(settings)
        db.session.add(settings)
    settings.company_name = COMPANY_AR
    settings.company_name_en = COMPANY_EN
    settings.phone = None
    settings.email = None
    settings.address = None
    settings.logo_path = None
    settings.cr_number = None
    settings.vat_number = None
    settings.rep_name = None
    settings.rep_mobile = None
    settings.rep_national_id = None
    settings.rep_signature_path = None
    settings.rep_sign_pin_hash = None

    org.name = COMPANY_AR
    org.name_en = COMPANY_EN
    org.notes = (
        f'[{datetime.utcnow().date()}] WIPE pilot data — account zeroed for formal kickoff'
    )
    db.session.add(org)
    db.session.add(settings)

    # إن لم يُبقَ مستخدمون: أنشئ admin مؤقتاً حتى يعمل kickoff
    if not keep_users:
        admin = User(
            username='admin',
            password_hash=hash_password('ChangeMeNow1'),
            full_name='مدير مؤقت — غيّر فوراً',
            email='admin@jama.liftcoreapp.com',
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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='تفريغ بيانات مستأجر جما')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--confirm', default='', help=f'يجب: {CONFIRM_TOKEN}')
    parser.add_argument('--keep-users', action='store_true')
    parser.add_argument('--print-only', action='store_true')
    args = parser.parse_args()

    from app import app
    from models import (
        Customer, Elevator, Contract, MaintenanceVisit, Fault,
        Technician, User, InventoryItem, WhatsAppInbox, Organization,
    )

    slug = (args.slug or 'jama').strip().lower()

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1

        print(f'==> مستأجر: {org.slug} (id={org.id}) — {org.name}')
        before = {
            'customers': _count(Customer, org.id),
            'elevators': _count(Elevator, org.id),
            'contracts': _count(Contract, org.id),
            'visits': _count(MaintenanceVisit, org.id),
            'faults': _count(Fault, org.id),
            'technicians': _count(Technician, org.id),
            'users': _count(User, org.id),
            'inventory': _count(InventoryItem, org.id),
            'whatsapp': _count(WhatsAppInbox, org.id),
        }
        for k, v in before.items():
            print(f'  {k}: {v}')

        if args.print_only:
            return 0

        if (args.confirm or '').strip() != CONFIRM_TOKEN:
            print('')
            print(f'للتنفيذ أعد الأمر مع: --confirm {CONFIRM_TOKEN}')
            print('تحذير: سيحذف كل البيانات التشغيلية لهذا المستأجر فقط.')
            return 2

        result = wipe_tenant(org, keep_users=bool(args.keep_users))
        print('')
        print('==> تم التفريغ')
        print('  قبل:', result['before'])
        print('  بعد:', result['after'])
        print('')
        print('الخطوة التالية:')
        print('  python scripts/kickoff_jama_formal.py')
        print('  أو: bash deploy/kickoff_jama_formal.sh')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
