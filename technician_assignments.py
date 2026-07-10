"""تعيين أكثر من فني/مساعد على زيارة صيانة أو عطل."""

from __future__ import annotations

from sqlalchemy import or_

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
    for i, tid in enumerate(technician_ids):
        link = FaultTechnician(
            fault_id=fid,
            technician_id=tid,
            role=_role_for_index(i),
        )
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
    return tenant_query(FaultTechnician).filter_by(fault_id=fault.id, technician_id=tech_id).count() > 0


def visits_for_technician_filter(tech_id: int):
    assigned = db.session.query(VisitTechnician.visit_id).filter(
        VisitTechnician.technician_id == tech_id
    )
    return or_(
        MaintenanceVisit.technician_id == tech_id,
        MaintenanceVisit.id.in_(assigned),
    )


def faults_for_technician_filter(tech_id: int):
    assigned = db.session.query(FaultTechnician.fault_id).filter(
        FaultTechnician.technician_id == tech_id
    )
    return or_(
        Fault.technician_id == tech_id,
        Fault.id.in_(assigned),
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
