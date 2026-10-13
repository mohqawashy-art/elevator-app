"""أرشيف العقود المنتهية: السجلات تبقى على السيرفر، والقوائم التشغيلية تخفيها حتى الفلتر."""
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, exists, false, func, or_

ARCHIVE_DISPLAY_STATUSES = frozenset({'منتهي', 'تم تجديده', 'ملغي'})


def request_wants_archive(args) -> bool:
    raw = (args.get('archive') or args.get('renewed') or '').strip().lower()
    return raw in ('1', 'true', 'yes', 'archive')


def display_is_archived(display: str | None) -> bool:
    return (display or '').strip() in ARCHIVE_DISPLAY_STATUSES


def contract_is_archived(contract, *, today: date | None = None, renewed_ids: set[int] | None = None) -> bool:
    today = today or date.today()
    raw = (contract.status or 'نشط').strip()
    if raw == 'ملغي':
        return True
    cid = getattr(contract, 'id', None)
    if renewed_ids is not None and cid is not None and int(cid) in renewed_ids:
        return True
    if raw in ('تم تجديده', 'مجدد', 'مُجدَّد'):
        return True
    if raw == 'منتهي' or (contract.end_date and contract.end_date < today):
        return True
    return False


def archived_contract_ids(*, today: date | None = None) -> set[int]:
    from flask import g, has_request_context

    from contract_codes import build_superseded_contract_ids
    from models import Contract
    from tenant_scope import tenant_query

    today = today or date.today()
    if has_request_context():
        cached = getattr(g, '_archived_contract_ids', None)
        if cached is not None:
            return cached

    contracts = tenant_query(Contract).all()
    renewed = build_superseded_contract_ids(contracts)
    ids = {
        int(c.id) for c in contracts
        if c.id is not None and contract_is_archived(c, today=today, renewed_ids=renewed)
    }
    if has_request_context():
        g._archived_contract_ids = ids
    return ids


def include_contract_in_list(display: str, *, archive: bool, status_filter: str = '') -> bool:
    """العقود الحالية افتراضياً. الفلتر أو الأرشيف يستدعي المنتهي/المجدَّد/الملغي."""
    archived = display_is_archived(display)
    if status_filter:
        return display == status_filter
    if archive:
        return archived
    return not archived


def apply_visit_archive_filter(query, *, archive: bool):
    """يخفي زيارات العقود القديمة من القائمة التشغيلية. الأرشيف يسترجعها بدون حذف."""
    from models import MaintenanceVisit
    from operations import VISIT_DONE

    archived_ids = list(archived_contract_ids())
    if not archived_ids:
        return query.filter(false()) if archive else query

    on_old = _row_on_archived_contract(
        MaintenanceVisit.elevator_id,
        MaintenanceVisit.visit_date,
        MaintenanceVisit.contract_id,
        archived_ids,
    )
    done = VISIT_DONE + ('ملغية',)
    if archive:
        return query.filter(on_old)
    return query.filter(or_(~on_old, ~MaintenanceVisit.status.in_(done)))


def apply_fault_archive_filter(query, *, archive: bool):
    """يخفي أعطال العقود القديمة المغلقة. المفتوح يبقى للمتابعة."""
    from models import Fault, MaintenanceVisit
    from operations import FAULT_OPEN

    archived_ids = list(archived_contract_ids())
    if not archived_ids:
        return query.filter(false()) if archive else query

    via_visit = exists().where(
        and_(
            MaintenanceVisit.id == Fault.visit_id,
            MaintenanceVisit.contract_id.in_(archived_ids),
        )
    )
    on_old = or_(
        via_visit,
        _row_on_archived_contract(
            Fault.elevator_id,
            func.date(Fault.reported_at),
            None,
            archived_ids,
        ),
    )
    if archive:
        return query.filter(on_old)
    return query.filter(or_(~on_old, Fault.status.in_(FAULT_OPEN)))


def _row_on_archived_contract(elevator_id_col, date_col, contract_id_col, archived_ids: list[int]):
    from models import Contract, ContractElevator

    old_cover = exists().where(
        and_(
            ContractElevator.elevator_id == elevator_id_col,
            ContractElevator.contract_id == Contract.id,
            Contract.id.in_(archived_ids),
            date_col >= Contract.start_date,
            date_col <= Contract.end_date,
        )
    )
    live_cover = exists().where(
        and_(
            ContractElevator.elevator_id == elevator_id_col,
            ContractElevator.contract_id == Contract.id,
            ~Contract.id.in_(archived_ids),
            date_col >= Contract.start_date,
            date_col <= Contract.end_date,
        )
    )
    by_dates = and_(old_cover, ~live_cover)
    if contract_id_col is None:
        return by_dates
    return or_(contract_id_col.in_(archived_ids), by_dates)
