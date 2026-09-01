#!/usr/bin/env python3
"""مسح مصاعد مستأجر ثم استيراد من Excel (تنسيق جما / Notion).

يحذف: روابط العقود، زيارات وأعطال مرتبطة بالمصاعد، تقديرات المصاعد، ثم المصاعد.
ثم يستورد من الملف (نفس منطق import_elevators_xlsx).

  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/replace_tenant_elevators_from_xlsx.py \\
    --slug default --xlsx deploy/data/elevators_1_9_2026.xlsx --yes

  python scripts/replace_tenant_elevators_from_xlsx.py --slug jama --xlsx path.xlsx --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
SCRIPTS = os.path.join(ROOT, 'scripts')
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

CONFIRM_TOKEN = 'REPLACE_ELEVATORS'


def _delete_tenant_elevators(org_id: int, dry_run: bool) -> dict[str, int]:
    from sqlalchemy import and_

    from models import (
        ContractElevator,
        Elevator,
        ElevatorEstimate,
        ElevatorEstimateLine,
        Fault,
        FaultTechnician,
        MaintenanceVisit,
        PartsBilling,
        VisitTechnician,
        db,
    )

    elev_ids = [
        e.id for e in (
            Elevator.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org_id)
            .all()
        )
    ]
    stats = {'elevators': len(elev_ids)}
    if not elev_ids:
        return stats

    visit_ids = [
        v.id for v in (
            MaintenanceVisit.query.execution_options(skip_tenant=True)
            .filter(
                MaintenanceVisit.organization_id == org_id,
                MaintenanceVisit.elevator_id.in_(elev_ids),
            )
            .all()
        )
    ]
    fault_ids = [
        f.id for f in (
            Fault.query.execution_options(skip_tenant=True)
            .filter(
                Fault.organization_id == org_id,
                Fault.elevator_id.in_(elev_ids),
            )
            .all()
        )
    ]
    estimate_ids = [
        e.id for e in (
            ElevatorEstimate.query.execution_options(skip_tenant=True)
            .filter(
                ElevatorEstimate.organization_id == org_id,
                ElevatorEstimate.elevator_id.in_(elev_ids),
            )
            .all()
        )
    ]

    stats['visits'] = len(visit_ids)
    stats['faults'] = len(fault_ids)
    stats['estimates'] = len(estimate_ids)

    if dry_run:
        stats['contract_links'] = (
            ContractElevator.query.execution_options(skip_tenant=True)
            .filter(
                ContractElevator.organization_id == org_id,
                ContractElevator.elevator_id.in_(elev_ids),
            )
            .count()
        )
        return stats

    if visit_ids:
        VisitTechnician.query.execution_options(skip_tenant=True).filter(
            VisitTechnician.visit_id.in_(visit_ids),
        ).delete(synchronize_session=False)
        MaintenanceVisit.query.execution_options(skip_tenant=True).filter(
            MaintenanceVisit.id.in_(visit_ids),
        ).delete(synchronize_session=False)

    if fault_ids:
        FaultTechnician.query.execution_options(skip_tenant=True).filter(
            FaultTechnician.fault_id.in_(fault_ids),
        ).delete(synchronize_session=False)
        Fault.query.execution_options(skip_tenant=True).filter(
            Fault.id.in_(fault_ids),
        ).delete(synchronize_session=False)

    if estimate_ids:
        ElevatorEstimateLine.query.execution_options(skip_tenant=True).filter(
            ElevatorEstimateLine.estimate_id.in_(estimate_ids),
        ).delete(synchronize_session=False)
        ElevatorEstimate.query.execution_options(skip_tenant=True).filter(
            ElevatorEstimate.id.in_(estimate_ids),
        ).delete(synchronize_session=False)

    PartsBilling.query.execution_options(skip_tenant=True).filter(
        and_(
            PartsBilling.organization_id == org_id,
            PartsBilling.elevator_id.in_(elev_ids),
        )
    ).update({PartsBilling.elevator_id: None}, synchronize_session=False)

    stats['contract_links'] = (
        ContractElevator.query.execution_options(skip_tenant=True)
        .filter(
            ContractElevator.organization_id == org_id,
            ContractElevator.elevator_id.in_(elev_ids),
        )
        .delete(synchronize_session=False)
    )

    stats['elevators_deleted'] = (
        Elevator.query.execution_options(skip_tenant=True)
        .filter(
            Elevator.organization_id == org_id,
            Elevator.id.in_(elev_ids),
        )
        .delete(synchronize_session=False)
    )
    db.session.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Replace tenant elevators from Excel')
    parser.add_argument('--xlsx', required=True, help='Path to elevators Excel file')
    parser.add_argument('--slug', default='default', help='Organization slug')
    parser.add_argument('--dry-run', action='store_true', help='Preview delete + import only')
    parser.add_argument('--yes', action='store_true', help='Confirm destructive replace')
    parser.add_argument(
        '--confirm',
        default='',
        help=f'Must be {CONFIRM_TOKEN} when using --yes',
    )
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL — source /etc/liftcore/platform.env أولاً')
        return 1

    xlsx = os.path.abspath(args.xlsx)
    if not os.path.isfile(xlsx):
        print(f'ERROR: ملف غير موجود: {xlsx}')
        return 1

    if not args.dry_run and not args.yes:
        print('أضف --yes --confirm REPLACE_ELEVATORS للتنفيذ أو --dry-run للمعاينة')
        return 2
    if args.yes and args.confirm != CONFIRM_TOKEN:
        print(f'ERROR: --confirm يجب أن يكون {CONFIRM_TOKEN}')
        return 2

    from flask import g

    from app import app, db
    from import_elevators_xlsx import import_elevators
    from models import Elevator, Organization
    from tenant_scope import assign_organization

    slug = (args.slug or 'default').strip().lower()

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            return 1

        g.organization = org
        g.organization_id = org.id

        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print(f'==> {org.name} ({slug}) id={org.id}')
        print(f'Database: {db_uri}')
        print(f'File: {xlsx}')

        before = Elevator.query.filter_by(organization_id=org.id).count()
        print(f'مصاعد قبل المسح: {before}')

        del_stats = _delete_tenant_elevators(org.id, dry_run=args.dry_run)
        print('==> مسح المصاعد')
        for k, v in del_stats.items():
            print(f'  {k}: {v}')

        if args.dry_run:
            from import_elevators_xlsx import load_rows

            rows = load_rows(xlsx)
            print(f'==> معاينة الاستيراد: {len(rows)} صف في الملف')
            imp_stats = import_elevators(xlsx, dry_run=True)
        else:
            orig_add = db.session.add

            def add_wrapped(obj):
                if isinstance(obj, Elevator) and getattr(obj, 'organization_id', None) is None:
                    assign_organization(obj)
                return orig_add(obj)

            db.session.add = add_wrapped  # type: ignore[method-assign]
            try:
                imp_stats = import_elevators(xlsx, dry_run=False)
            finally:
                db.session.add = orig_add  # type: ignore[method-assign]

        print('==> استيراد المصاعد')
        for k, v in imp_stats.items():
            print(f'  {k}: {v}')

        after = Elevator.query.filter_by(organization_id=org.id).count()
        print(f'مصاعد بعد الاستيراد: {after}')
        if args.dry_run:
            print('DRY-RUN — بدون تعديل')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
