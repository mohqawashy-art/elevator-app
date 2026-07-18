#!/usr/bin/env python3
"""
تفريغ أو حذف مستأجر جما بالكامل.

أ) تفريغ البيانات مع الإبقاء على المؤسسة:
  python scripts/wipe_tenant_data.py --slug jama --confirm JAMA_WIPE

ب) حذف الحساب كاملاً (بيانات + مؤسسة) لإعادة دعوة كعميل جديد:
  python scripts/wipe_tenant_data.py --slug jama --delete-org --confirm JAMA_DELETE_ORG

لا يمسّ مستأجرين آخرين (default وغيره).
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
DELETE_ORG_TOKEN = 'JAMA_DELETE_ORG'


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
        ('settings', Settings),
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
    settings.company_name = COMPANY_AR
    settings.company_name_en = COMPANY_EN
    db.session.add(settings)

    org.name = COMPANY_AR
    org.name_en = COMPANY_EN
    org.notes = (
        f'[{datetime.utcnow().date()}] WIPE pilot data — account zeroed for formal kickoff'
    )
    db.session.add(org)

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
        'organization_deleted': False,
        'slug': org_slug,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='تفريغ أو حذف مستأجر جما')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--confirm', default='', help=f'{CONFIRM_TOKEN} أو {DELETE_ORG_TOKEN}')
    parser.add_argument('--keep-users', action='store_true')
    parser.add_argument('--delete-org', action='store_true', help='حذف المؤسسة بالكامل')
    parser.add_argument('--print-only', action='store_true')
    args = parser.parse_args()

    from app import app
    from models import (
        Customer, Elevator, Contract, MaintenanceVisit, Fault,
        Technician, User, InventoryItem, WhatsAppInbox, Organization,
    )

    slug = (args.slug or 'jama').strip().lower()
    delete_org = bool(args.delete_org)
    expected = DELETE_ORG_TOKEN if delete_org else CONFIRM_TOKEN

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'OK: لا توجد مؤسسة slug={slug} — الحساب غير موجود أصلاً')
            return 0

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

        if (args.confirm or '').strip() != expected:
            print('')
            if delete_org:
                print(f'لحذف الحساب كاملاً: --delete-org --confirm {DELETE_ORG_TOKEN}')
                print('تحذير: يحذف المؤسسة وكل بياناتها — لا يمكن التراجع.')
            else:
                print(f'لتفريغ البيانات فقط: --confirm {CONFIRM_TOKEN}')
            return 2

        result = wipe_tenant(
            org,
            keep_users=bool(args.keep_users) and not delete_org,
            delete_organization=delete_org,
        )
        print('')
        if result.get('organization_deleted'):
            print(f"==> تم حذف الحساب بالكامل: slug={result.get('slug')}")
            print('  قبل:', result['before'])
            print('')
            print('الخطوة التالية — دعوة كعميل جديد:')
            print('  1) https://admin.liftcoreapp.com/operator/onboarding')
            print('  2) شركة: شركة تقنية جما التميز للمصاعد')
            print('  3) المعرّف المقترح: jama')
            print('  4) أرسل رابط الدعوة لبريد جما')
            print('  5) بعد التفعيل: https://jama.liftcoreapp.com/login')
        else:
            print('==> تم التفريغ (المؤسسة ما زالت موجودة)')
            print('  قبل:', result['before'])
            print('  بعد:', result['after'])
            print('  ثم: bash deploy/kickoff_jama_formal.sh')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
