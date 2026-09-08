"""نقل عقود تركيب/تحديث من جدول العقود العام إلى installation_contracts.

الاستخدام على السيرفر:
  cd /home/info/liftcore/elevator-app
  .venv/bin/python scripts/migrate_legacy_install_contracts.py --dry-run
  .venv/bin/python scripts/migrate_legacy_install_contracts.py
  .venv/bin/python scripts/migrate_legacy_install_contracts.py --ids 12,34
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from contract_codes import is_installation_contract_type
from installation.contracts_service import ensure_install_contract_schema
from installation.models import InstallContract, InstallContractInstallment, InstallProject
from models import Contract, db
from sales.service import add_months, money_round
from tenant_scope import assign_organization, tenant_query


def _legacy_candidates(contract_ids: list[int] | None = None):
    q = tenant_query(Contract).order_by(Contract.id.asc())
    if contract_ids:
        q = q.filter(Contract.id.in_(contract_ids))
    rows = []
    for legacy in q.all():
        code = (legacy.code or '').strip()
        is_install = is_installation_contract_type(legacy.contract_type) or code.upper().startswith('CI-')
        if not is_install:
            continue
        existing = tenant_query(InstallContract).filter(
            (InstallContract.code == legacy.code) | (InstallContract.legacy_contract_id == legacy.id)
        ).first()
        if existing:
            continue
        rows.append(legacy)
    return rows


def _project_for_legacy(legacy: Contract, next_project_code_fn) -> InstallProject:
    if legacy.customer_id:
        projects = (
            tenant_query(InstallProject)
            .filter_by(customer_id=legacy.customer_id)
            .order_by(InstallProject.created_at.desc())
            .all()
        )
        for project in projects:
            if not tenant_query(InstallContract).filter_by(project_id=project.id).first():
                if project.contract_id == legacy.id:
                    return project
        for project in projects:
            if not tenant_query(InstallContract).filter_by(project_id=project.id).first():
                return project

    project = InstallProject(
        code=next_project_code_fn(InstallProject, 'PRJ-', 4),
        title=f'مشروع {legacy.code}',
        status='عقد',
        customer_id=legacy.customer_id,
        contract_id=legacy.id,
    )
    assign_organization(project)
    db.session.add(project)
    db.session.flush()
    return project


def migrate_legacy_install_contracts(
    *,
    contract_ids: list[int] | None = None,
    dry_run: bool = False,
    next_project_code_fn=None,
) -> list[dict]:
    from flask import g

    ensure_install_contract_schema()
    if next_project_code_fn is None:
        def next_project_code_fn(model, prefix, digits=4):
            import re
            max_num = 0
            pattern = re.compile(r'^' + re.escape(prefix) + r'(\d+)$')
            for (code,) in tenant_query(model).with_entities(model.code).all():
                if not code:
                    continue
                m = pattern.match(str(code).strip())
                if m:
                    max_num = max(max_num, int(m.group(1)))
            return f'{prefix}{str(max_num + 1).zfill(digits)}'

    results = []
    for legacy in _legacy_candidates(contract_ids):
        total = money_round(legacy.total or 0)
        value = money_round(legacy.value or total)
        tax_amount = money_round(legacy.tax_amount or max(total - value, 0))
        tax_pct = float(legacy.tax_pct or 15)
        if value and not legacy.tax_pct and tax_amount:
            tax_pct = money_round((tax_amount / value) * 100.0)

        contract_type = legacy.contract_type or 'عقد تركيب'
        if not is_installation_contract_type(contract_type):
            contract_type = 'عقد تركيب'

        start = legacy.start_date
        end = legacy.end_date
        duration = legacy.duration_months or 12
        if start and not end and duration:
            end = add_months(start, duration)

        row = {
            'legacy_id': legacy.id,
            'code': legacy.code,
            'contract_type': contract_type,
            'customer_id': legacy.customer_id,
            'total': total,
        }
        results.append(row)
        if dry_run:
            continue

        g.organization_id = legacy.organization_id
        project = _project_for_legacy(legacy, next_project_code_fn)
        if not project.contract_id:
            project.contract_id = legacy.id

        contract = InstallContract(
            code=legacy.code,
            project_id=project.id,
            customer_id=legacy.customer_id,
            legacy_contract_id=legacy.id,
            contract_type=contract_type,
            start_date=start,
            end_date=end,
            duration_months=duration,
            value=value,
            tax_pct=tax_pct,
            tax_amount=tax_amount,
            total=total or money_round(value + tax_amount),
            progress_pct=0,
            collected_amount=money_round(legacy.paid_amount or 0),
            remaining_amount=money_round(max((total or 0) - float(legacy.paid_amount or 0), 0)),
            status=legacy.status if legacy.status in ('مسودة', 'نشط', 'مكتمل', 'ملغي') else 'نشط',
            signed_at=legacy.created_at or datetime.utcnow(),
            notes=(legacy.notes or '').strip() or f'منقول من العقود العامة #{legacy.id}',
        )
        assign_organization(contract)
        db.session.add(contract)
        db.session.flush()

        inst = InstallContractInstallment(
            contract_id=contract.id,
            seq=1,
            label='دفعة واحدة',
            pct=100,
            amount=contract.total,
            collected_amount=contract.collected_amount,
            status='محصّلة' if contract.collected_amount >= contract.total and contract.total > 0 else 'مستحقة',
        )
        assign_organization(inst)
        db.session.add(inst)

        if legacy.contract_type != contract_type:
            legacy.contract_type = contract_type

    if not dry_run and results:
        db.session.commit()
    elif dry_run:
        db.session.rollback()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Migrate legacy installation contracts')
    parser.add_argument('--dry-run', action='store_true', help='List candidates only')
    parser.add_argument('--ids', default='', help='Comma-separated legacy contract IDs')
    args = parser.parse_args(argv)

    from app import app

    ids = None
    if args.ids.strip():
        ids = [int(x.strip()) for x in args.ids.split(',') if x.strip()]

    with app.app_context():
        from flask import g
        from models import Organization

        org = Organization.query.filter_by(slug=os.environ.get('LIFTCORE_APP_ORG_SLUG') or 'default').first()
        if org:
            g.organization_id = org.id
        rows = migrate_legacy_install_contracts(contract_ids=ids, dry_run=args.dry_run)
        if not rows:
            print('No legacy installation contracts to migrate.')
            return 0
        print(f'{"Would migrate" if args.dry_run else "Migrated"} {len(rows)} contract(s):')
        for row in rows:
            print(f"  - {row['code']} (legacy #{row['legacy_id']}) type={row['contract_type']} total={row['total']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
