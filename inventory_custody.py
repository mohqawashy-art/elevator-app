"""عهدة قطع الغيار لدى الفنيين — من حركات المخزون (صرف / إرجاع / تسوية)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from models import InventoryItem, StockMovement, Technician, db
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query

CUSTODY_ISSUE_TYPES = ('صرف لفني', 'صرف عهدة للفني')
MOVEMENT_RETURN_WAREHOUSE = 'إرجاع عهدة للمخزن'
MOVEMENT_SETTLE_CLIENT = 'تسوية عهدة — عميل'
MOVEMENT_SETTLE_PROJECT = 'تسوية عهدة — مشروع'

CUSTODY_SETTLE_TYPES = (
    MOVEMENT_RETURN_WAREHOUSE,
    MOVEMENT_SETTLE_CLIENT,
    MOVEMENT_SETTLE_PROJECT,
)

CUSTODY_MOVEMENT_TYPES = CUSTODY_ISSUE_TYPES
ALL_CUSTODY_MOVEMENT_TYPES = CUSTODY_ISSUE_TYPES + CUSTODY_SETTLE_TYPES

SETTLE_TARGET_WAREHOUSE = 'warehouse'
SETTLE_TARGET_CLIENT = 'client'
SETTLE_TARGET_PROJECT = 'project'

_CANCELLED_STATUSES = frozenset({'ملغي', 'ملغى', 'cancelled', 'canceled'})


def _custody_delta(movement: StockMovement) -> float:
    """تغيّر العهدة: صرف (+) — إرجاع/تسوية (−)."""
    mt = (movement.movement_type or '').strip()
    if not movement.technician_id:
        return 0.0
    qty = float(movement.quantity or 0)
    if qty <= 0:
        return 0.0
    direction = (movement.direction or '').strip()

    if mt in (MOVEMENT_SETTLE_CLIENT, MOVEMENT_SETTLE_PROJECT):
        return -qty
    if mt == MOVEMENT_RETURN_WAREHOUSE and direction == 'وارد':
        return -qty
    if mt in CUSTODY_ISSUE_TYPES:
        if direction == 'صادر':
            return qty
        if direction == 'وارد':
            return -qty
    return 0.0


def _first_elevator_id_for_contract(contract_id: int) -> int | None:
    from models import ContractElevator

    link = tenant_query(ContractElevator).filter_by(contract_id=int(contract_id)).first()
    return int(link.elevator_id) if link and link.elevator_id else None


def maintenance_contracts_for_custody() -> list[dict]:
    """عقود الصيانة النشطة — للتسوية إلى عميل."""
    from models import Contract
    from operations import _is_maintenance_contract
    from sqlalchemy.orm import joinedload

    rows = (
        tenant_query(Contract)
        .options(joinedload(Contract.customer))
        .order_by(Contract.id.desc())
        .all()
    )
    out: list[dict] = []
    for c in rows:
        if not _is_maintenance_contract(c):
            continue
        if (c.status or '').strip() in _CANCELLED_STATUSES:
            continue
        cust = c.customer.name if c.customer else '—'
        ctype = (c.contract_type or 'صيانة').strip()
        out.append({
            'id': c.id,
            'code': c.code or '',
            'name': f'{cust} — {ctype}',
            'customer': cust,
            'contract_type': ctype,
            'elevator_id': _first_elevator_id_for_contract(c.id),
        })
    return out


def installation_contracts_for_custody() -> list[dict]:
    """عقود التركيب / المشاريع — للتسوية إلى مشروع."""
    try:
        from installation.models import InstallContract
    except ImportError:
        return []

    from sqlalchemy.orm import joinedload

    rows = (
        tenant_query(InstallContract)
        .options(
            joinedload(InstallContract.customer),
            joinedload(InstallContract.project),
        )
        .order_by(InstallContract.id.desc())
        .all()
    )
    out: list[dict] = []
    for ic in rows:
        if (ic.status or '').strip() in _CANCELLED_STATUSES:
            continue
        proj = ic.project
        proj_title = (proj.title or '').strip() if proj and proj.title else ''
        client = ic.client_display if hasattr(ic, 'client_display') else (
            ic.customer.name if ic.customer else '—'
        )
        label = proj_title or client or '—'
        ctype = (ic.contract_type or 'عقد تركيب').strip()
        out.append({
            'id': ic.id,
            'code': ic.code or '',
            'name': f'{label} — {ctype}',
            'customer': client,
            'project_title': proj_title,
            'project_id': ic.project_id,
            'contract_type': ctype,
        })
    return out


def build_technician_custody_snapshot() -> dict:
    """رصيد العهدة لكل (صنف، فني) من حركات المخزون."""
    tech_names = {t.id: t.name for t in tenant_query(Technician).all()}
    item_meta = {
        i.id: {'code': i.code or '', 'name': i.name or ''}
        for i in tenant_query(InventoryItem).all()
    }
    raw: dict[tuple[int, int], float] = defaultdict(float)
    for m in tenant_query(StockMovement).filter(
        StockMovement.technician_id.isnot(None),
        StockMovement.movement_type.in_(ALL_CUSTODY_MOVEMENT_TYPES),
    ).all():
        delta = _custody_delta(m)
        if abs(delta) < 1e-9:
            continue
        raw[(int(m.item_id), int(m.technician_id))] += delta

    by_item: dict[int, dict] = {}
    rows: list[dict] = []
    tech_ids_with_custody: set[int] = set()

    for (item_id, tech_id), qty in raw.items():
        qty = round(qty, 4)
        if qty <= 0.01:
            continue
        tech_name = tech_names.get(tech_id) or '—'
        meta = item_meta.get(item_id) or {}
        tech_ids_with_custody.add(tech_id)
        entry = {
            'item_id': item_id,
            'item_code': meta.get('code') or '',
            'item_name': meta.get('name') or '—',
            'technician_id': tech_id,
            'technician_name': tech_name,
            'qty': qty,
        }
        rows.append(entry)
        block = by_item.setdefault(item_id, {'total_qty': 0.0, 'technicians': []})
        block['total_qty'] = round(block['total_qty'] + qty, 4)
        block['technicians'].append({
            'technician_id': tech_id,
            'technician_name': tech_name,
            'qty': qty,
        })

    for block in by_item.values():
        block['technicians'].sort(
            key=lambda x: (-float(x.get('qty') or 0), x.get('technician_name') or ''),
        )

    rows.sort(
        key=lambda r: (
            r.get('technician_name') or '',
            -float(r.get('qty') or 0),
            int(r.get('item_id') or 0),
        ),
    )

    total_qty = round(sum(r['qty'] for r in rows), 4)
    return {
        'by_item': by_item,
        'rows': rows,
        'summary': {
            'items_with_custody': len(by_item),
            'technicians_with_custody': len(tech_ids_with_custody),
            'total_qty': total_qty,
            'line_count': len(rows),
        },
    }


def technician_item_custody_qty(
    item_id: int,
    technician_id: int,
    snapshot: dict | None = None,
) -> float:
    snap = snapshot if snapshot is not None else build_technician_custody_snapshot()
    for row in snap.get('rows') or []:
        if int(row.get('item_id') or 0) == int(item_id) and int(row.get('technician_id') or 0) == int(technician_id):
            return float(row.get('qty') or 0)
    return 0.0


def settle_technician_custody(
    *,
    item_id: int,
    technician_id: int,
    quantity: float,
    target: str,
    movement_date: date | None = None,
    reason: str = '',
    notes: str = '',
    contract_id: int | None = None,
    install_contract_id: int | None = None,
    unit_price: float | None = None,
    snapshot: dict | None = None,
) -> StockMovement:
    """تحويل عهدة فني: مخزن / عميل (عقد صيانة) / مشروع (عقد تركيب)."""
    from inventory_stock import adjust_inventory_qty
    from operations import next_code

    qty = float(quantity or 0)
    if qty <= 0:
        raise ValueError('أدخل كمية أكبر من صفر')

    target = (target or '').strip().lower()
    if target not in (SETTLE_TARGET_WAREHOUSE, SETTLE_TARGET_CLIENT, SETTLE_TARGET_PROJECT):
        raise ValueError('وجهة التسوية غير صالحة')

    available = technician_item_custody_qty(item_id, technician_id, snapshot)
    if qty > available + 1e-9:
        raise ValueError(f'الكمية أكبر من العهدة المتاحة ({available:g})')

    item = tenant_get_or_404(InventoryItem, item_id)
    tenant_get_or_404(Technician, technician_id)

    price = float(unit_price if unit_price is not None else (item.buy_price or 0))
    mv_date = movement_date or date.today()
    reason = (reason or '').strip()
    notes = (notes or '').strip()
    reference = None
    elev_id = None

    if target == SETTLE_TARGET_WAREHOUSE:
        direction = 'وارد'
        movement_type = MOVEMENT_RETURN_WAREHOUSE
        if not reason:
            reason = 'إرجاع عهدة للمخزن'
    elif target == SETTLE_TARGET_CLIENT:
        from models import Contract
        from operations import _is_maintenance_contract

        direction = 'صادر'
        movement_type = MOVEMENT_SETTLE_CLIENT
        if not contract_id:
            raise ValueError('اختر عقد الصيانة من سجل العقود')
        contract = tenant_get_or_404(Contract, int(contract_id))
        if not _is_maintenance_contract(contract):
            raise ValueError('العقد المختار ليس عقد صيانة')
        cust = contract.customer.name if contract.customer else '—'
        reason = f'{contract.code} — {cust}'
        reference = f'custody:maint:{contract.id}'
        elev_id = _first_elevator_id_for_contract(contract.id)
    else:
        from installation.models import InstallContract

        direction = 'صادر'
        movement_type = MOVEMENT_SETTLE_PROJECT
        if not install_contract_id:
            raise ValueError('اختر عقد التركيب / المشروع من سجل العقود')
        ic = tenant_get_or_404(InstallContract, int(install_contract_id))
        proj = ic.project
        proj_label = (proj.title or '').strip() if proj and proj.title else ic.client_display
        reason = f'{ic.code} — {proj_label}'
        reference = f'custody:install:{ic.id}'

    movement = StockMovement(
        code=next_code(StockMovement, 'MV-', digits=3),
        item_id=int(item_id),
        movement_date=mv_date,
        direction=direction,
        movement_type=movement_type,
        quantity=qty,
        unit_price=price,
        total_value=qty * price,
        technician_id=int(technician_id),
        elevator_id=elev_id,
        reason=reason[:300],
        reference=(reference or '')[:100] or None,
        notes=notes or None,
    )
    assign_organization(movement)
    db.session.add(movement)

    if target == SETTLE_TARGET_WAREHOUSE:
        adjust_inventory_qty(item, 'وارد', qty)

    return movement


def item_custody_fields(item_id: int, snapshot: dict | None = None) -> dict:
    """حقول العهدة لصف صنف في جدول الأصناف."""
    snap = snapshot if snapshot is not None else build_technician_custody_snapshot()
    block = snap.get('by_item', {}).get(int(item_id)) or {
        'total_qty': 0.0,
        'technicians': [],
    }
    techs = block.get('technicians') or []
    parts = []
    for t in techs:
        name = (t.get('technician_name') or '—').strip()
        q = float(t.get('qty') or 0)
        if q <= 0.01:
            continue
        qtxt = int(q) if abs(q - int(q)) < 1e-9 else round(q, 2)
        parts.append(f'{qtxt} — {name}')
    return {
        'custody_qty': float(block.get('total_qty') or 0),
        'custody_techs': techs,
        'custody_summary': ' · '.join(parts) if parts else '—',
    }
