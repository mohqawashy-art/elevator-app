"""عهدة قطع الغيار لدى الفنيين — من حركات المخزون (صرف / إرجاع / تسوية)."""



from __future__ import annotations



from collections import defaultdict

from datetime import date



from models import InventoryItem, StockMovement, Technician, db

from tenant_scope import assign_organization, tenant_get_or_404, tenant_query



# زيادة العهدة عند الصرف للفني

CUSTODY_ISSUE_TYPES = ('صرف لفني', 'صرف عهدة للفني')



# إرجاع للمخزن — يخصم العهدة ويرفع رصيد المخزون

MOVEMENT_RETURN_WAREHOUSE = 'إرجاع عهدة للمخزن'



# تسوية بدون تأثير على رصيد المخزون (القطعة salت المخزن عند الصرف الأصلي)

MOVEMENT_SETTLE_CLIENT = 'تسوية عهدة — عميل'

MOVEMENT_SETTLE_PROJECT = 'تسوية عهدة — مشروع'



CUSTODY_SETTLE_TYPES = (

    MOVEMENT_RETURN_WAREHOUSE,

    MOVEMENT_SETTLE_CLIENT,

    MOVEMENT_SETTLE_PROJECT,

)



# للتوافق مع الكود القديم

CUSTODY_MOVEMENT_TYPES = CUSTODY_ISSUE_TYPES



ALL_CUSTODY_MOVEMENT_TYPES = CUSTODY_ISSUE_TYPES + CUSTODY_SETTLE_TYPES



SETTLE_TARGET_WAREHOUSE = 'warehouse'

SETTLE_TARGET_CLIENT = 'client'

SETTLE_TARGET_PROJECT = 'project'





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

    elevator_id: int | None = None,

    unit_price: float | None = None,

    snapshot: dict | None = None,

) -> StockMovement:

    """تحويل عهدة فني: مخزن / عميل / مشروع — يسجّل حركة مخزون ويحدّث الرصيد عند الإرجاع للمخزن."""

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



    if target == SETTLE_TARGET_WAREHOUSE:

        direction = 'وارد'

        movement_type = MOVEMENT_RETURN_WAREHOUSE

        if not reason:

            reason = 'إرجاع عهدة للمخزن'

        elev_id = None

    elif target == SETTLE_TARGET_CLIENT:

        direction = 'صادر'

        movement_type = MOVEMENT_SETTLE_CLIENT

        if not reason:

            raise ValueError('أدخل اسم العميل أو وصف التسوية')

        elev_id = None

    else:

        direction = 'صادر'

        movement_type = MOVEMENT_SETTLE_PROJECT

        if not reason and not elevator_id:

            raise ValueError('أدخل اسم المشروع أو اختر المصعد')

        if not reason and elevator_id:

            from models import Elevator

            elev = tenant_query(Elevator).filter_by(id=int(elevator_id)).first()

            if elev:

                cust = elev.customer.name if elev.customer else ''

                reason = f'{cust} — {elev.code or elev.id}'.strip(' —')

        elev_id = int(elevator_id) if elevator_id else None



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


