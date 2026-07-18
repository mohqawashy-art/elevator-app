"""اكتشاف وحذف زيارات الصيانة المكررة."""

from __future__ import annotations

from models import db, MaintenanceVisit
from operations import is_fault_visit_type


def _visit_score(v: MaintenanceVisit) -> tuple:
    has_report = bool((v.checklist_json or '').strip())
    has_work = bool((v.works_done or '').strip())
    completed = 1 if (v.status or '') in ('مكتملة', 'مكتمل') else 0
    return (completed, has_report, has_work, -(v.id or 0))


def _duplicate_key(v: MaintenanceVisit) -> tuple:
    return (
        v.elevator_id,
        str(v.visit_date or ''),
        (v.visit_type or '').strip(),
        (v.visit_time or '').strip(),
        v.technician_id,
        v.contract_id,
    )


def find_duplicate_visit_ids_from(visits: list) -> list[int]:
    """اكتشاف المكررات من قائمة محمّلة مسبقاً (بدون استعلام إضافي)."""
    periodic = [v for v in visits if not is_fault_visit_type(getattr(v, 'visit_type', None))]
    groups: dict[tuple, list] = {}
    for v in periodic:
        groups.setdefault(_duplicate_key(v), []).append(v)

    to_delete: list[int] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        keep = max(group, key=_visit_score)
        for v in group:
            if v.id != keep.id:
                to_delete.append(v.id)
    return sorted(to_delete)


def find_duplicate_visit_ids() -> list[int]:
    from tenant_scope import tenant_query

    return find_duplicate_visit_ids_from(
        tenant_query(MaintenanceVisit).order_by(MaintenanceVisit.id).all()
    )


def remove_duplicate_visits(*, dry_run: bool = False) -> dict:
    from app import _purge_visit_dependencies

    ids = find_duplicate_visit_ids()
    stats = {'found': len(ids), 'deleted': 0, 'ids': ids}
    if dry_run:
        return stats

    for vid in ids:
        v = MaintenanceVisit.query.get(vid)
        if not v:
            continue
        _purge_visit_dependencies(vid)
        db.session.delete(v)
        stats['deleted'] += 1

    db.session.commit()
    return stats
