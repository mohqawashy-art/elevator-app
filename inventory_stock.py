"""خصم وإرجاع المخزون عند استخدام قطع الغيار."""

from __future__ import annotations

from datetime import date

from models import InventoryItem, StockMovement, db


def adjust_inventory_qty(item: InventoryItem | None, direction: str, qty: float, *, reverse: bool = False) -> None:
    if not item:
        return
    q = float(qty or 0)
    delta = q if direction == 'وارد' else -q
    if reverse:
        delta = -delta
    item.current_qty = (item.current_qty or 0) + delta


def stock_reference(prefix: str, entity_id: int) -> str:
    return f'{prefix}:{entity_id}'


def reverse_stock_by_reference(reference: str) -> None:
    if not reference:
        return
    from tenant_scope import tenant_query

    rows = tenant_query(StockMovement).filter_by(reference=reference).all()
    for m in rows:
        item = db.session.get(InventoryItem, m.item_id)
        if item:
            adjust_inventory_qty(item, m.direction, m.quantity, reverse=True)
        db.session.delete(m)


def _stock_lines(lines: list[dict]) -> list[dict]:
    out = []
    for ln in lines or []:
        if not isinstance(ln, dict):
            continue
        iid = ln.get('item_id')
        if iid in (None, '', 0, '0'):
            continue
        qty = float(ln.get('qty') or 0)
        if qty <= 0:
            continue
        out.append(ln)
    return out


def lines_with_inventory_ids(lines: list[dict]) -> list[dict]:
    return _stock_lines(lines)


def deduct_parts_from_stock(
    lines: list[dict],
    *,
    reference: str,
    technician_id: int | None = None,
    elevator_id: int | None = None,
    movement_type: str = 'استخدام قطع',
    notes: str = '',
) -> None:
    from operations import next_code
    from tenant_scope import assign_organization, tenant_query

    stock_lines = _stock_lines(lines)
    if not stock_lines:
        return

    for ln in stock_lines:
        item = tenant_query(InventoryItem).filter_by(id=int(ln['item_id'])).first()
        if not item:
            raise ValueError('أحد الأصناف المختارة غير موجود في المخزون')
        qty = float(ln.get('qty') or 0)
        available = float(item.current_qty or 0)
        if available + 1e-9 < qty:
            raise ValueError(
                f'رصيد «{item.name}» غير كافٍ (متوفر {available:g}، مطلوب {qty:g})'
            )

    for ln in stock_lines:
        item = tenant_query(InventoryItem).filter_by(id=int(ln['item_id'])).first()
        qty = float(ln.get('qty') or 0)
        unit_price = float(ln.get('cost_price') or item.buy_price or 0)
        m = StockMovement(
            code=next_code(StockMovement, 'MV-', digits=3),
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type=movement_type,
            quantity=qty,
            unit_price=unit_price,
            total_value=qty * unit_price,
            technician_id=technician_id,
            elevator_id=elevator_id,
            reference=reference,
            notes=notes or str(ln.get('name') or ''),
        )
        assign_organization(m)
        db.session.add(m)
        adjust_inventory_qty(item, 'صادر', qty)


def sync_entity_parts_stock(
    prefix: str,
    entity_id: int,
    lines: list[dict],
    *,
    technician_id: int | None = None,
    elevator_id: int | None = None,
    movement_type: str = 'استخدام قطع',
    notes: str = '',
) -> None:
    ref = stock_reference(prefix, entity_id)
    reverse_stock_by_reference(ref)
    deduct_parts_from_stock(
        lines,
        reference=ref,
        technician_id=technician_id,
        elevator_id=elevator_id,
        movement_type=movement_type,
        notes=notes,
    )
