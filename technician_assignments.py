"""تعيين أكثر من فني/مساعد على زيارة صيانة أو عطل."""

from __future__ import annotations

from sqlalchemy import and_, or_

from models import db, Technician, VisitTechnician, FaultTechnician, MaintenanceVisit, Fault
from tenant_scope import assign_organization, tenant_query


def parse_technician_ids(form) -> list[int]:
    """يقرأ technician_ids (متعدد) أو technician_id (واحد) من النموذج."""
    raw: list = []
    if hasattr(form, 'getlist'):
        raw = form.getlist('technician_ids')
        if not raw:
            single = form.get('technician_id')
            if single:
                raw = [single]
    else:
        val = form.get('technician_ids') if hasattr(form, 'get') else None
        if val:
            raw = val if isinstance(val, list) else [val]
        elif hasattr(form, 'get') and form.get('technician_id'):
            raw = [form.get('technician_id')]
    ids: list[int] = []
    for x in raw:
        try:
            n = int(x)
            if n > 0 and n not in ids:
                ids.append(n)
        except (TypeError, ValueError):
            continue
    return ids


def _role_for_index(index: int) -> str:
    return 'فني' if index == 0 else 'مساعد'


def sync_visit_technicians(visit, technician_ids: list[int]) -> None:
    """مزامنة فريق الزيارة — الأول هو الفني الرئيسي."""
    vid = visit.id if hasattr(visit, 'id') else int(visit)
    tenant_query(VisitTechnician).filter_by(visit_id=vid).delete(synchronize_session=False)
    for i, tid in enumerate(technician_ids):
        link = VisitTechnician(
            visit_id=vid,
            technician_id=tid,
            role=_role_for_index(i),
        )
        assign_organization(link)
        db.session.add(link)
    if hasattr(visit, 'technician_id'):
        visit.technician_id = technician_ids[0] if technician_ids else None


def sync_fault_technicians(fault, technician_ids: list[int]) -> None:
    fid = fault.id if hasattr(fault, 'id') else int(fault)
    tenant_query(FaultTechnician).filter_by(fault_id=fid).delete(synchronize_session=False)
    org_id = getattr(fault, 'organization_id', None)
    for i, tid in enumerate(technician_ids):
        link = FaultTechnician(
            fault_id=fid,
            technician_id=tid,
            role=_role_for_index(i),
        )
        if org_id:
            link.organization_id = org_id
        else:
            assign_organization(link)
        db.session.add(link)
    if hasattr(fault, 'technician_id'):
        fault.technician_id = technician_ids[0] if technician_ids else None


def visit_technician_rows(visit_id: int) -> list[VisitTechnician]:
    return (
        tenant_query(VisitTechnician)
        .filter_by(visit_id=visit_id)
        .order_by(VisitTechnician.id)
        .all()
    )


def fault_technician_rows(fault_id: int) -> list[FaultTechnician]:
    return (
        tenant_query(FaultTechnician)
        .filter_by(fault_id=fault_id)
        .order_by(FaultTechnician.id)
        .all()
    )


def fault_technician_rows_by_fault_ids(fault_ids: list[int]) -> dict[int, list[FaultTechnician]]:
    """تحميل صفوف فنيي الأعطال دفعة واحدة — يتجنب N+1 في قوائم الأعطال."""
    from sqlalchemy.orm import joinedload

    out: dict[int, list[FaultTechnician]] = {int(i): [] for i in fault_ids}
    if not fault_ids:
        return out
    rows = (
        tenant_query(FaultTechnician)
        .options(joinedload(FaultTechnician.technician))
        .filter(FaultTechnician.fault_id.in_(fault_ids))
        .order_by(FaultTechnician.id)
        .all()
    )
    for r in rows:
        out.setdefault(int(r.fault_id), []).append(r)
    return out


def visit_technician_rows_by_visit_ids(visit_ids: list[int]) -> dict[int, list[VisitTechnician]]:
    from sqlalchemy.orm import joinedload

    out: dict[int, list[VisitTechnician]] = {int(i): [] for i in visit_ids}
    if not visit_ids:
        return out
    rows = (
        tenant_query(VisitTechnician)
        .options(joinedload(VisitTechnician.technician))
        .filter(VisitTechnician.visit_id.in_(visit_ids))
        .order_by(VisitTechnician.id)
        .all()
    )
    for r in rows:
        out.setdefault(int(r.visit_id), []).append(r)
    return out


def _ids_from_rows(rows) -> list[int]:
    return [r.technician_id for r in rows]


def _payload_from_rows(rows, *, fallback_id=None, fallback_tech=None) -> list[dict]:
    if not rows and fallback_id:
        rows = [type('Row', (), {
            'technician_id': fallback_id,
            'role': 'فني',
            'technician': fallback_tech,
        })()]
    out = []
    for r in rows:
        tech = getattr(r, 'technician', None)
        if tech is None:
            tech = tenant_query(Technician).filter_by(id=r.technician_id).first()
        out.append({
            'id': r.technician_id,
            'name': tech.name if tech else '—',
            'role': getattr(r, 'role', 'فني') or 'فني',
        })
    return out


def visit_technician_ids(visit) -> list[int]:
    vid = visit.id if hasattr(visit, 'id') else int(visit)
    return [r.technician_id for r in visit_technician_rows(vid)]


def fault_technician_ids(fault) -> list[int]:
    fid = fault.id if hasattr(fault, 'id') else int(fault)
    return [r.technician_id for r in fault_technician_rows(fid)]


def _names_from_rows(rows) -> str:
    if not rows:
        return '—'
    parts = []
    for r in rows:
        tech = r.technician or tenant_query(Technician).filter_by(id=r.technician_id).first()
        if not tech:
            continue
        label = tech.name
        if getattr(r, 'role', '') == 'مساعد':
            label = f'{label} (مساعد)'
        parts.append(label)
    return '، '.join(parts) if parts else '—'


def visit_technicians_label(visit) -> str:
    ids = visit_technician_ids(visit)
    if ids:
        rows = visit_technician_rows(visit.id)
        return _names_from_rows(rows)
    if visit.technician:
        return visit.technician.name
    return '—'


def fault_technicians_label(fault) -> str:
    ids = fault_technician_ids(fault)
    if ids:
        rows = fault_technician_rows(fault.id)
        return _names_from_rows(rows)
    if fault.technician:
        return fault.technician.name
    return '—'


def visit_technicians_payload(visit) -> list[dict]:
    rows = visit_technician_rows(visit.id)
    if not rows and visit.technician_id:
        rows = [type('Row', (), {'technician_id': visit.technician_id, 'role': 'فني', 'technician': visit.technician})()]
    out = []
    for r in rows:
        tech = r.technician if hasattr(r, 'technician') else tenant_query(Technician).filter_by(id=r.technician_id).first()
        out.append({
            'id': r.technician_id,
            'name': tech.name if tech else '—',
            'role': getattr(r, 'role', 'فني') or 'فني',
        })
    return out


def fault_technicians_payload(fault) -> list[dict]:
    rows = fault_technician_rows(fault.id)
    if not rows and fault.technician_id:
        rows = [type('Row', (), {'technician_id': fault.technician_id, 'role': 'فني', 'technician': fault.technician})()]
    out = []
    for r in rows:
        tech = r.technician if hasattr(r, 'technician') else tenant_query(Technician).filter_by(id=r.technician_id).first()
        out.append({
            'id': r.technician_id,
            'name': tech.name if tech else '—',
            'role': getattr(r, 'role', 'فني') or 'فني',
        })
    return out


def technician_assigned_to_visit(visit, tech_id: int) -> bool:
    if not tech_id:
        return True
    if visit.technician_id == tech_id:
        return True
    return tenant_query(VisitTechnician).filter_by(visit_id=visit.id, technician_id=tech_id).count() > 0


def technician_assigned_to_fault(fault, tech_id: int) -> bool:
    if not tech_id:
        return True
    if fault.technician_id == tech_id:
        return True
    return (
        FaultTechnician.query.execution_options(skip_tenant=True)
        .filter_by(fault_id=fault.id, technician_id=tech_id)
        .count()
        > 0
    )


def faults_for_technician_filter(tech_id: int):
    """أعطال مكلّفة للفني — يشمل صفوف الفريق حتى لو organization_id ناقص."""
    assigned = (
        db.session.query(FaultTechnician.fault_id)
        .filter(FaultTechnician.technician_id == int(tech_id))
        .execution_options(skip_tenant=True)
    )
    return or_(
        Fault.technician_id == int(tech_id),
        Fault.id.in_(assigned),
    )


def ensure_fault_links_for_technician(tech_id: int) -> int:
    """زامن FaultTechnician من technician_id لأي عطل مفتوح مكلّف للفني."""
    from operations import FAULT_OPEN

    fixed = 0
    rows = (
        tenant_query(Fault)
        .filter(
            Fault.technician_id == int(tech_id),
            Fault.status.in_(FAULT_OPEN),
        )
        .all()
    )
    for fault in rows:
        if not fault_technician_ids(fault):
            sync_fault_technicians(fault, [int(tech_id)])
            fixed += 1
    return fixed


def unassigned_open_faults_filter():
    """أعطال مفتوحة بلا فني رئيسي وبلا صف فريق."""
    from operations import FAULT_OPEN

    linked = db.session.query(FaultTechnician.fault_id).execution_options(skip_tenant=True)
    return and_(
        Fault.status.in_(FAULT_OPEN),
        Fault.technician_id.is_(None),
        ~Fault.id.in_(linked),
    )


def visits_for_technician_filter(tech_id: int):
    assigned = db.session.query(VisitTechnician.visit_id).filter(
        VisitTechnician.technician_id == tech_id
    )
    return or_(
        MaintenanceVisit.technician_id == tech_id,
        MaintenanceVisit.id.in_(assigned),
    )


def backfill_technician_assignments() -> None:
    """نسخ technician_id الحالي إلى جداول الفريق (مرة واحدة)."""
    for v in tenant_query(MaintenanceVisit).filter(MaintenanceVisit.technician_id.isnot(None)).all():
        if not visit_technician_ids(v):
            sync_visit_technicians(v, [v.technician_id])
    for f in tenant_query(Fault).filter(Fault.technician_id.isnot(None)).all():
        if not fault_technician_ids(f):
            sync_fault_technicians(f, [f.technician_id])
    db.session.commit()
