"""مرحلة 1 — إدارة المخزن (بدون تغيير مخطط قاعدة البيانات)."""

from __future__ import annotations

from datetime import date

from models import InventoryItem, StockMovement, Supplier, Technician, db
from inventory_stock import adjust_inventory_qty
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query

MOVEMENT_OPENING = 'رصيد افتتاحي'
MOVEMENT_PURCHASE = 'اضافة مخزنية (شراء)'
MOVEMENT_ISSUE_TECH = 'صرف لفني'
MOVEMENT_ISSUE_CUSTODY = 'صرف عهدة للفني'
MOVEMENT_ISSUE_SITE = 'صرف لمشروع / عميل'

ISSUE_TARGET_CLIENT = 'client'
ISSUE_TARGET_PROJECT = 'project'
ISSUE_TARGET_CUSTODY = 'custody'
ISSUE_TARGET_CONSUMABLE = 'consumable'

ISSUE_TARGETS = (
    ISSUE_TARGET_CLIENT,
    ISSUE_TARGET_PROJECT,
    ISSUE_TARGET_CUSTODY,
    ISSUE_TARGET_CONSUMABLE,
)


def available_stock_qty(item: InventoryItem | None) -> float:
    if not item:
        return 0.0
    return float(item.current_qty or 0)


def validate_outbound_stock(item: InventoryItem | None, quantity: float) -> None:
    qty = float(quantity or 0)
    if qty <= 0:
        raise ValueError('أدخل كمية أكبر من صفر')
    available = available_stock_qty(item)
    if available + 1e-9 < qty:
        name = (item.name if item else 'الصنف') or 'الصنف'
        raise ValueError(
            f'رصيد «{name}» غير كافٍ (متوفر {available:g}، مطلوب {qty:g})'
        )


def po_receipt_reference(order_id: int, item_id: int) -> str:
    return f'po:{int(order_id)}:item:{int(item_id)}'


def po_receipt_already_recorded(order_id: int) -> bool:
    prefix = f'po:{int(order_id)}:item:'
    return (
        tenant_query(StockMovement)
        .filter(StockMovement.reference.like(f'{prefix}%'))
        .first()
        is not None
    )


def create_stock_movement(
    *,
    item: InventoryItem,
    movement_date: date,
    direction: str,
    movement_type: str,
    quantity: float,
    unit_price: float | None = None,
    technician_id: int | None = None,
    elevator_id: int | None = None,
    reason: str = '',
    reference: str | None = None,
    notes: str = '',
) -> StockMovement:
    from operations import next_code

    qty = float(quantity or 0)
    if qty <= 0:
        raise ValueError('الكمية يجب أن تكون أكبر من صفر')
    direction = (direction or '').strip()
    if direction not in ('وارد', 'صادر'):
        raise ValueError('اتجاه الحركة غير صالح')

    price = float(unit_price if unit_price is not None else (item.buy_price or 0))
    movement = StockMovement(
        code=next_code(StockMovement, 'MV-', digits=3),
        item_id=int(item.id),
        movement_date=movement_date or date.today(),
        direction=direction,
        movement_type=(movement_type or '').strip() or '—',
        quantity=qty,
        unit_price=price,
        total_value=qty * price,
        technician_id=int(technician_id) if technician_id else None,
        elevator_id=int(elevator_id) if elevator_id else None,
        reason=(reason or '')[:300],
        reference=(reference or '')[:100] or None,
        notes=(notes or '') or None,
    )
    assign_organization(movement)
    db.session.add(movement)
    adjust_inventory_qty(item, direction, qty)
    return movement


def record_opening_stock(
    *,
    item_id: int,
    quantity: float,
    movement_date: date | None = None,
    unit_price: float | None = None,
    notes: str = '',
) -> StockMovement:
    item = tenant_get_or_404(InventoryItem, item_id)
    qty = float(quantity or 0)
    if qty <= 0:
        raise ValueError('أدخل كمية افتتاحية أكبر من صفر')
    price = float(unit_price if unit_price is not None else (item.buy_price or 0))
    movement = create_stock_movement(
        item=item,
        movement_date=movement_date or date.today(),
        direction='وارد',
        movement_type=MOVEMENT_OPENING,
        quantity=qty,
        unit_price=price,
        reason='رصيد أول المدة',
        notes=notes,
    )
    if price > 0 and not float(item.buy_price or 0):
        item.buy_price = price
    return movement


def record_purchase_receipt_movements(order) -> bool:
    """تسجيل حركات استلام PO — مرة واحدة لكل أمر (reference)."""
    if po_receipt_already_recorded(order.id):
        return False

    from supplier_prices import upsert_supplier_price

    created = False
    supplier_row = None
    if order.supplier_id:
        supplier_row = db.session.get(Supplier, order.supplier_id)

    mv_date = order.order_date or date.today()
    for line in order.lines or []:
        item = db.session.get(InventoryItem, line.item_id)
        if not item:
            continue
        qty = float(line.quantity or 0)
        if qty <= 0:
            continue
        ref = po_receipt_reference(order.id, item.id)
        if tenant_query(StockMovement).filter_by(reference=ref).first():
            continue
        unit_price = float(line.unit_price or item.buy_price or 0)
        reason = f'{order.code} — {order.supplier or "مورد"}'
        create_stock_movement(
            item=item,
            movement_date=mv_date,
            direction='وارد',
            movement_type=MOVEMENT_PURCHASE,
            quantity=qty,
            unit_price=unit_price,
            reason=reason[:300],
            reference=ref,
            notes=(order.notes or '')[:500] or None,
        )
        if unit_price > 0:
            item.buy_price = unit_price
            if order.supplier:
                item.supplier = order.supplier
        if supplier_row and unit_price > 0:
            upsert_supplier_price(
                supplier_row.id,
                item.id,
                unit_price,
                source='po',
                source_ref=order.code,
                assign_org_fn=assign_organization,
                sync_inventory=False,
            )
        created = True
    return created


def record_issue_authorization(
    *,
    item_id: int,
    quantity: float,
    target: str,
    movement_date: date | None = None,
    technician_id: int | None = None,
    contract_id: int | None = None,
    install_contract_id: int | None = None,
    reason: str = '',
    notes: str = '',
) -> StockMovement:
    """إذن صرف — عميل / مشروع / عهدة / مستhlكات."""
    from inventory_custody import item_eligible_for_custody

    item = tenant_get_or_404(InventoryItem, item_id)
    validate_outbound_stock(item, quantity)

    target = (target or '').strip().lower()
    if target not in ISSUE_TARGETS:
        raise ValueError('نوع إذن الصرف غير صالح')

    qty = float(quantity or 0)
    mv_date = movement_date or date.today()
    elev_id = None
    movement_type = MOVEMENT_ISSUE_SITE
    issue_reason = (reason or '').strip()

    if target == ISSUE_TARGET_CUSTODY:
        if not technician_id:
            raise ValueError('اختر الفني لصرف العهدة')
        if not item_eligible_for_custody(item):
            movement_type = MOVEMENT_ISSUE_TECH
            issue_reason = issue_reason or 'مستهلكات — صرف مباشر'
        else:
            movement_type = MOVEMENT_ISSUE_CUSTODY
            issue_reason = issue_reason or 'عهدة فني'
    elif target == ISSUE_TARGET_CONSUMABLE:
        movement_type = MOVEMENT_ISSUE_TECH
        issue_reason = issue_reason or 'مستهلكات صيانة'
    elif target == ISSUE_TARGET_CLIENT:
        from models import Contract
        from operations import _is_maintenance_contract
        from inventory_custody import _first_elevator_id_for_contract

        if not contract_id:
            raise ValueError('اختر عقد الصيانة')
        contract = tenant_get_or_404(Contract, int(contract_id))
        if not _is_maintenance_contract(contract):
            raise ValueError('العقد المختار ليس عقد صيانة')
        cust = contract.customer.name if contract.customer else '—'
        issue_reason = issue_reason or f'{contract.code} — {cust}'
        elev_id = _first_elevator_id_for_contract(contract.id)
    elif target == ISSUE_TARGET_PROJECT:
        from installation.models import InstallContract

        if not install_contract_id:
            raise ValueError('اختر عقد التركيب / المشروع')
        ic = tenant_get_or_404(InstallContract, int(install_contract_id))
        proj = ic.project
        proj_label = (proj.title or '').strip() if proj and proj.title else ic.client_display
        issue_reason = issue_reason or f'{ic.code} — {proj_label}'

    return create_stock_movement(
        item=item,
        movement_date=mv_date,
        direction='صادر',
        movement_type=movement_type,
        quantity=qty,
        unit_price=item.buy_price or 0,
        technician_id=technician_id,
        elevator_id=elev_id,
        reason=issue_reason,
        notes=notes,
    )


def item_card_payload(item_id: int) -> dict:
    from inventory_custody import build_technician_custody_snapshot, item_custody_fields
    from sqlalchemy.orm import joinedload

    item = tenant_get_or_404(InventoryItem, item_id)
    custody_snapshot = build_technician_custody_snapshot()
    custody = item_custody_fields(item.id, custody_snapshot)

    movements = (
        tenant_query(StockMovement)
        .options(joinedload(StockMovement.item))
        .filter_by(item_id=item.id)
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
        .limit(200)
        .all()
    )
    tech_names = {t.id: t.name for t in tenant_query(Technician).all()}

    movement_rows = []
    for m in movements:
        movement_rows.append({
            'id': m.id,
            'code': m.code or '',
            'movement_date': str(m.movement_date or ''),
            'direction': m.direction or '',
            'movement_type': m.movement_type or '',
            'quantity': float(m.quantity or 0),
            'unit_price': float(m.unit_price or 0),
            'total_value': float(m.total_value or 0),
            'technician': tech_names.get(m.technician_id, '—') if m.technician_id else '—',
            'reason': m.reason or '',
            'notes': m.notes or '',
            'reference': m.reference or '',
        })

    opening_qty = round(
        sum(
            float(m.quantity or 0)
            for m in movements
            if (m.movement_type or '').strip() == MOVEMENT_OPENING and (m.direction or '') == 'وارد'
        ),
        4,
    )

    return {
        'item': {
            'id': item.id,
            'code': item.code or '',
            'name': item.name or '',
            'category': item.category or '',
            'unit': item.unit or 'قطعة',
            'current_qty': float(item.current_qty or 0),
            'min_qty': float(item.min_qty or 0),
            'buy_price': float(item.buy_price or 0),
            'sell_price': float(item.sell_price or 0),
            'stock_value': float(item.stock_value or 0),
            'order_status': item.order_status,
            'supplier': item.supplier or '',
            'location': item.location or '',
            'notes': item.notes or '',
        },
        'custody': custody,
        'opening_qty': opening_qty,
        'movements': movement_rows,
        'movement_count': len(movement_rows),
    }
