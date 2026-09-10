#!/usr/bin/env python3
"""تشخيص ظهور الأعطال في بوابة الفني — jama."""
from __future__ import annotations

from flask import g

from app import app
from models import Fault, FaultTechnician, Organization, Technician
from operations import fault_is_open, field_technician_payload, open_faults_filter
from tenant_scope import tenant_query


def main() -> int:
    with app.app_context():
        org = Organization.query.filter_by(slug='jama').first()
        if not org:
            print('ERROR: no jama org')
            return 1
        g.organization_id = org.id
        g.organization = org
        print(f'org={org.id} {org.name}')

        faults = tenant_query(Fault).order_by(Fault.id.desc()).limit(8).all()
        print(f'latest_faults={len(faults)}')
        for f in faults:
            fts = (
                FaultTechnician.query.execution_options(skip_tenant=True)
                .filter_by(fault_id=f.id)
                .all()
            )
            open_sql = (
                tenant_query(Fault)
                .filter(Fault.id == f.id, open_faults_filter())
                .count()
            )
            print(
                f'  {f.code} status={f.status!r} tech={f.technician_id} org={f.organization_id}'
                f' open_py={fault_is_open(f.status)} open_sql={open_sql}'
                f' team_ids={[x.technician_id for x in fts]} org_ft={[x.organization_id for x in fts]}'
            )

        techs = (
            Technician.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .order_by(Technician.id.asc())
            .all()
        )
        print(f'techs_in_jama={len(techs)}')
        for t in techs:
            p = field_technician_payload(t.id, portal_kind='both')
            faults_p = p.get('faults') or []
            pin = bool(t.sign_pin_hash)
            print(
                f'  TECH id={t.id} {t.code} {t.name} team={t.team} status={t.status}'
                f' pin={pin} faults={[(x["code"], x["status"]) for x in faults_p]}'
                f' show_faults={p.get("show_faults")} has_assigned={p.get("has_assigned_faults")}'
            )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
