#!/usr/bin/env python3
"""تصفير عملاء مستأجر (وما يعتمد عليهم) مع الإبقاء على المستخدمين/الفنيين/المخزن.

  cd ~/liftcore/elevator-app
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/clear_tenant_customers.py --slug jama --dry-run
  python scripts/clear_tenant_customers.py --slug jama --confirm CLEAR_CUSTOMERS
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CONFIRM = 'CLEAR_CUSTOMERS'


def main() -> int:
    parser = argparse.ArgumentParser(description='تصفير عملاء مستأجر')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--confirm', default='')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    from app import app, db
    from flask import g
    from models import (
        Contract,
        ContractElevator,
        Customer,
        Elevator,
        ElevatorEstimate,
        ElevatorEstimateLine,
        Expense,
        Fault,
        FaultTechnician,
        Invoice,
        MaintenanceVisit,
        Organization,
        PartsBilling,
        PurchaseOrder,
        PurchaseOrderLine,
        Revenue,
        StockMovement,
        VisitTechnician,
        WhatsAppInbox,
    )

    slug = (args.slug or 'jama').strip().lower()

    def _count(model, org_id: int) -> int:
        return (
            model.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org_id)
            .count()
        )

    def _delete(model, org_id: int) -> int:
        return (
            model.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org_id)
            .delete(synchronize_session=False)
        )

    def _null(model, org_id: int, *cols) -> None:
        rows = (
            model.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org_id)
            .all()
        )
        for row in rows:
            for col in cols:
                setattr(row, col, None)

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1

        g.organization = org
        g.organization_id = org.id
        oid = org.id

        before = {
            'customers': _count(Customer, oid),
            'elevators': _count(Elevator, oid),
            'contracts': _count(Contract, oid),
            'visits': _count(MaintenanceVisit, oid),
            'faults': _count(Fault, oid),
            'invoices': _count(Invoice, oid),
            'revenues': _count(Revenue, oid),
        }
        print(f'==> {org.slug} (id={oid}) — {org.name}')
        for k, v in before.items():
            print(f'  {k}: {v}')

        if args.dry_run:
            print('DRY-RUN — بدون حذف')
            return 0

        if (args.confirm or '').strip() != CONFIRM:
            print(f'للتأكيد: --confirm {CONFIRM}')
            return 2

        visit_ids = [
            r.id
            for r in (
                MaintenanceVisit.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=oid)
                .with_entities(MaintenanceVisit.id)
                .all()
            )
        ]
        fault_ids = [
            r.id
            for r in (
                Fault.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=oid)
                .with_entities(Fault.id)
                .all()
            )
        ]
        if visit_ids:
            VisitTechnician.query.execution_options(skip_tenant=True).filter(
                VisitTechnician.visit_id.in_(visit_ids)
            ).delete(synchronize_session=False)
        if fault_ids:
            FaultTechnician.query.execution_options(skip_tenant=True).filter(
                FaultTechnician.fault_id.in_(fault_ids)
            ).delete(synchronize_session=False)

        _null(MaintenanceVisit, oid, 'fault_id')
        _null(Fault, oid, 'visit_id')
        _null(Invoice, oid, 'revenue_id', 'parent_invoice_id', 'parts_billing_id')
        _null(Revenue, oid, 'invoice_id', 'parts_billing_id')
        db.session.commit()

        try:
            import installation.models as im
        except Exception:
            im = None
        if im is not None:
            for model in (
                getattr(im, 'InstallTimelineStep', None),
                getattr(im, 'InstallQuotationLine', None),
                getattr(im, 'InstallQuotation', None),
                getattr(im, 'InstallProject', None),
                getattr(im, 'InstallLead', None),
            ):
                if model is not None and hasattr(model, 'organization_id'):
                    _delete(model, oid)

        deleted = {}
        for label, model in (
            ('visit_technicians', VisitTechnician),
            ('fault_technicians', FaultTechnician),
            ('stock_movements', StockMovement),
            ('parts_billing', PartsBilling),
            ('po_lines', PurchaseOrderLine),
            ('purchase_orders', PurchaseOrder),
            ('estimate_lines', ElevatorEstimateLine),
            ('estimates', ElevatorEstimate),
            ('invoices', Invoice),
            ('revenues', Revenue),
            ('expenses', Expense),
            ('whatsapp_inbox', WhatsAppInbox),
            ('visits', MaintenanceVisit),
            ('faults', Fault),
            ('contract_elevators', ContractElevator),
            ('contracts', Contract),
            ('elevators', Elevator),
            ('customers', Customer),
        ):
            deleted[label] = _delete(model, oid)

        db.session.commit()

        after = {
            'customers': _count(Customer, oid),
            'elevators': _count(Elevator, oid),
            'contracts': _count(Contract, oid),
            'visits': _count(MaintenanceVisit, oid),
            'faults': _count(Fault, oid),
            'invoices': _count(Invoice, oid),
            'revenues': _count(Revenue, oid),
        }
        print('==> تم التصفير')
        print('  deleted:', deleted)
        print('  after:', after)
        return 0 if after['customers'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
