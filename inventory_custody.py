"""عهدة قطع الغيار لدى الفنيين — من حركات المخزون (صرف لفني / صرف عهدة)."""

from __future__ import annotations

from collections import defaultdict

from models import InventoryItem, StockMovement, Technician
from tenant_scope import tenant_query

CUSTODY_MOVEMENT_TYPES = ('صرف لفني', 'صرف عهدة للفني')


def _custody_delta(movement: StockMovement) -> float:
    """تغيّر العهدة: صرف للفني (+) — إرجاع وارد (−)."""
    if (movement.movement_type or '').strip() not in CUSTODY_MOVEMENT_TYPES:
        return 0.0
    if not movement.technician_id:
        return 0.0
    qty = float(movement.quantity or 0)
    if qty <= 0:
        return 0.0
    direction = (movement.direction or '').strip()
    if direction == 'صادر':
        return qty
    if direction == 'وارد':
        return -qty
    return 0.0


def build_technician_custody_snapshot() -> dict:
    """رصيد العهدة لكل (صنف، فني) من حركات المخزون."""
    tech_names = {
        t.id: t.name
        for t in tenant_query(Technician).all()
    }
    item_meta = {
        i.id: {'code': i.code or '', 'name': i.name or ''}
        for i in tenant_query(InventoryItem).all()
    }
    raw: dict[tuple[int, int], float] = defaultdict(float)
    for m in tenant_query(StockMovement).filter(
        StockMovement.technician_id.isnot(None),
        StockMovement.movement_type.in_(CUSTODY_MOVEMENT_TYPES),
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
