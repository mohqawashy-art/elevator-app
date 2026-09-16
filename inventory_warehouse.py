"""مرحلة 1 — إدارة المخزن (بدون تغيير مخطط قاعدة البيانات)."""

from __future__ import annotations

from datetime import date

from models import InventoryItem, StockMovement, Supplier, Technician, db
from inventory_stock import adjust_inventory_qty
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query

MOVEMENT_OPENING = 'رصيد افتتاحي'
MOVEMENT_PURCHASE = 'فاتورة شراء'
MOVEMENT_PURCHASE_LEGACY = 'اضافة مخزنية (شراء)'
MOVEMENT_ISSUE_TECH = 'صرف لفني'
MOVEMENT_ISSUE_CUSTODY = 'صرف عهدة للفني'
MOVEMENT_ISSUE_SITE = 'صرف لمشروع / عميل'

OPENING_DOC_PREFIX = 'OS-'
OPENING_DOC_REF_PREFIX = 'opening:'

PURCHASE_DOC_PREFIX = 'PI-'
PURCHASE_DOC_REF_PREFIX = 'purchase:'

ISSUE_DOC_PREFIX = 'IS-'
ISSUE_DOC_REF_PREFIX = 'issue:'


def opening_doc_reference(doc_code: str, item_id: int, invoice_no: str = '') -> str:
    ref = f'{OPENING_DOC_REF_PREFIX}{doc_code}:item:{int(item_id)}'
    inv = (invoice_no or '').strip()
    if inv:
        ref = f'{ref}:inv:{inv[:40]}'
    return ref[:100]


def parse_opening_invoice(reference: str | None) -> str:
    ref = (reference or '').strip()
    if ':inv:' not in ref:
        return ''
    return ref.split(':inv:', 1)[1].strip()


def parse_movement_invoice(reference: str | None, reason: str | None = None) -> str:
    """رقم فاتورة من مرجع رصيد افتتاحي أو سبب فاتورة شراء."""
    inv = parse_opening_invoice(reference)
    if inv:
        return inv
    text = (reason or '').strip()
    marker = '| فاتورة:'
    if marker in text:
        return text.split(marker, 1)[1].split('|', 1)[0].strip()
    return ''


def purchase_doc_reference(doc_code: str, item_id: int, invoice_no: str) -> str:
    inv = (invoice_no or '').strip()
    ref = f'{PURCHASE_DOC_REF_PREFIX}{doc_code}:inv:{inv[:40]}:item:{int(item_id)}'
    return ref[:100]


def purchase_reason(doc_code: str, invoice_no: str, supplier: str = '') -> str:
    inv = (invoice_no or '').strip()
    reason = f'فاتورة شراء — {doc_code} | فاتورة: {inv[:80]}'
    sup = (supplier or '').strip()
    if sup:
        reason = f'{reason} | مورد: {sup[:60]}'
    return reason[:300]


def next_purchase_doc_code() -> str:
    import re

    max_num = 0
    pattern = re.compile(
        r'^' + re.escape(PURCHASE_DOC_REF_PREFIX) + re.escape(PURCHASE_DOC_PREFIX) + r'(\d+):inv:'
    )
    for row in tenant_query(StockMovement).with_entities(StockMovement.reference).all():
        ref = (row[0] or '').strip()
        match = pattern.match(ref)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f'{PURCHASE_DOC_PREFIX}{str(max_num + 1).zfill(4)}'


def purchase_invoice_no_taken(invoice_no: str) -> bool:
    inv = (invoice_no or '').strip()
    if not inv:
        return False
    needle = f':inv:{inv[:40]}:item:'
    return (
        tenant_query(StockMovement)
        .filter(
            StockMovement.movement_type == MOVEMENT_PURCHASE,
            StockMovement.reference.like(f'{PURCHASE_DOC_REF_PREFIX}%{needle}%'),
        )
        .first()
        is not None
    )


def opening_reason(doc_code: str, invoice_no: str = '') -> str:
    reason = f'رصيد أول المدة — {doc_code}'
    inv = (invoice_no or '').strip()
    if inv:
        reason = f'{reason} | فاتورة: {inv[:80]}'
    return reason[:300]


def next_opening_doc_code() -> str:
    import re

    max_num = 0
    pattern = re.compile(r'^' + re.escape(OPENING_DOC_REF_PREFIX) + re.escape(OPENING_DOC_PREFIX) + r'(\d+):item:')
    for row in tenant_query(StockMovement).with_entities(StockMovement.reference).all():
        ref = (row[0] or '').strip()
        match = pattern.match(ref)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f'{OPENING_DOC_PREFIX}{str(max_num + 1).zfill(4)}'

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
    from inventory_units import normalize_inventory_qty

    qty = normalize_inventory_qty(qty, item.unit)
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
    invoice_no: str = '',
) -> StockMovement:
    doc_code, movements = record_opening_stock_batch(
        lines=[{
            'item_id': item_id,
            'quantity': quantity,
            'unit_price': unit_price,
            'invoice_no': invoice_no,
        }],
        movement_date=movement_date,
        notes=notes,
    )
    return movements[0]


def record_opening_stock_batch(
    *,
    lines: list[dict],
    movement_date: date | None = None,
    notes: str = '',
) -> tuple[str, list[StockMovement]]:
    """تسجيل مستند رصيد أول المدة — عدة أصناف برقم مستند واحد OS-xxxx."""
    if not lines:
        raise ValueError('أضف صنفاً واحداً على الأقل')

    mv_date = movement_date or date.today()
    doc_notes = (notes or '').strip()
    doc_code = next_opening_doc_code()
    movements: list[StockMovement] = []
    seen_items: set[int] = set()

    for raw in lines:
        try:
            item_id = int(raw.get('item_id') or 0)
            quantity = float(raw.get('quantity') or 0)
        except (TypeError, ValueError):
            raise ValueError('بيانات السطر غير صالحة') from None
        if item_id <= 0 or quantity <= 0:
            continue
        if item_id in seen_items:
            item = tenant_get_or_404(InventoryItem, item_id)
            name = (item.name or item.code or 'الصنف').strip()
            raise ValueError(f'الصنف «{name}» مكرر في المستند')
        seen_items.add(item_id)

        unit_price = raw.get('unit_price')
        if unit_price not in (None, ''):
            try:
                unit_price = float(unit_price)
            except (TypeError, ValueError):
                unit_price = None

        item = tenant_get_or_404(InventoryItem, item_id)
        price = float(unit_price if unit_price is not None else (item.buy_price or 0))
        invoice_no = (raw.get('invoice_no') or '').strip()
        movement = create_stock_movement(
            item=item,
            movement_date=mv_date,
            direction='وارد',
            movement_type=MOVEMENT_OPENING,
            quantity=quantity,
            unit_price=price,
            reason=opening_reason(doc_code, invoice_no),
            reference=opening_doc_reference(doc_code, item_id, invoice_no),
            notes=doc_notes or None,
        )
        if price > 0 and not float(item.buy_price or 0):
            item.buy_price = price
        movements.append(movement)

    if not movements:
        raise ValueError('أضف صنفاً واحداً على الأقل بكمية أكبر من صفر')

    return doc_code, movements


def record_purchase_invoice_batch(
    *,
    lines: list[dict],
    invoice_no: str,
    movement_date: date | None = None,
    supplier: str = '',
    notes: str = '',
) -> tuple[str, list[StockMovement]]:
    """تسجيل فاتورة شراء — عدة أصniaف برقم مستند PI-xxxx وفاتورة واحدة."""
    inv = (invoice_no or '').strip()
    if not inv:
        raise ValueError('أدخل رقم فاتورة الشراء')
    if not lines:
        raise ValueError('أضف صنفاً واحداً على الأقل')
    if purchase_invoice_no_taken(inv):
        raise ValueError(f'فاتورة الشراء «{inv}» مسجّلة مسبقاً')

    sup = (supplier or '').strip()
    mv_date = movement_date or date.today()
    doc_notes = (notes or '').strip()
    doc_code = next_purchase_doc_code()
    movements: list[StockMovement] = []
    seen_items: set[int] = set()

    for raw in lines:
        try:
            item_id = int(raw.get('item_id') or 0)
            quantity = float(raw.get('quantity') or 0)
        except (TypeError, ValueError):
            raise ValueError('بيانات السطر غير صالحة') from None
        if item_id <= 0 or quantity <= 0:
            continue
        if item_id in seen_items:
            item = tenant_get_or_404(InventoryItem, item_id)
            name = (item.name or item.code or 'الصنف').strip()
            raise ValueError(f'الصنف «{name}» مكرر في الفاتورة')
        seen_items.add(item_id)

        unit_price = raw.get('unit_price')
        if unit_price not in (None, ''):
            try:
                unit_price = float(unit_price)
            except (TypeError, ValueError):
                unit_price = None

        item = tenant_get_or_404(InventoryItem, item_id)
        price = float(unit_price if unit_price is not None else (item.buy_price or 0))
        movement = create_stock_movement(
            item=item,
            movement_date=mv_date,
            direction='وارد',
            movement_type=MOVEMENT_PURCHASE,
            quantity=quantity,
            unit_price=price,
            reason=purchase_reason(doc_code, inv, sup),
            reference=purchase_doc_reference(doc_code, item_id, inv),
            notes=doc_notes or None,
        )
        if price > 0:
            item.buy_price = price
            if sup:
                item.supplier = sup
        movements.append(movement)

    if not movements:
        raise ValueError('أضف صنفاً واحداً على الأقل بكمية أكبر من صفر')

    return doc_code, movements


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
            movement_type=MOVEMENT_PURCHASE_LEGACY,
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


def issue_doc_reference(doc_code: str, item_id: int) -> str:
    return f'{ISSUE_DOC_REF_PREFIX}{doc_code}:item:{int(item_id)}'[:100]


def issue_doc_reason(doc_code: str, detail: str) -> str:
    detail = (detail or '').strip() or '—'
    return f'إذن صرف — {doc_code} | {detail}'[:300]


def next_issue_doc_code() -> str:
    import re

    max_num = 0
    pattern = re.compile(
        r'^' + re.escape(ISSUE_DOC_REF_PREFIX) + re.escape(ISSUE_DOC_PREFIX) + r'(\d+):item:'
    )
    for row in tenant_query(StockMovement).with_entities(StockMovement.reference).all():
        ref = (row[0] or '').strip()
        match = pattern.match(ref)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f'{ISSUE_DOC_PREFIX}{str(max_num + 1).zfill(4)}'


def _resolve_issue_context(
    *,
    target: str,
    item: InventoryItem | None = None,
    technician_id: int | None = None,
    contract_id: int | None = None,
    install_contract_id: int | None = None,
    reason: str = '',
) -> dict:
    """تحديد نوع الحركة والسبب والفني/المصعد حسب نوع الصرف."""
    from inventory_custody import item_eligible_for_custody

    target = (target or '').strip().lower()
    if target not in ISSUE_TARGETS:
        raise ValueError('نوع إذن الصرف غير صالح')

    elev_id = None
    movement_type = MOVEMENT_ISSUE_SITE
    issue_reason = (reason or '').strip()
    tech_id = technician_id

    if target == ISSUE_TARGET_CUSTODY:
        if not tech_id:
            raise ValueError('اختر الفني لصرف العهدة')
        if item and not item_eligible_for_custody(item):
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

    return {
        'movement_type': movement_type,
        'issue_reason': issue_reason,
        'technician_id': tech_id,
        'elevator_id': elev_id,
        'target': target,
    }


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
    """إذن صرف — صنف واحد (كارت الصنف)."""
    item = tenant_get_or_404(InventoryItem, item_id)
    validate_outbound_stock(item, quantity)

    ctx = _resolve_issue_context(
        target=target,
        item=item,
        technician_id=technician_id,
        contract_id=contract_id,
        install_contract_id=install_contract_id,
        reason=reason,
    )
    qty = float(quantity or 0)
    mv_date = movement_date or date.today()

    return create_stock_movement(
        item=item,
        movement_date=mv_date,
        direction='صادر',
        movement_type=ctx['movement_type'],
        quantity=qty,
        unit_price=item.buy_price or 0,
        technician_id=ctx['technician_id'],
        elevator_id=ctx['elevator_id'],
        reason=ctx['issue_reason'],
        notes=notes,
    )


def record_issue_batch(
    *,
    lines: list[dict],
    target: str,
    movement_date: date | None = None,
    technician_id: int | None = None,
    contract_id: int | None = None,
    install_contract_id: int | None = None,
    notes: str = '',
) -> tuple[str, list[StockMovement]]:
    """مستند إذن صرف — عدة أصniaف برقم IS-xxxx."""
    if not lines:
        raise ValueError('أضف صنفاً واحداً على الأقل')

    ctx = _resolve_issue_context(
        target=target,
        item=None,
        technician_id=technician_id,
        contract_id=contract_id,
        install_contract_id=install_contract_id,
    )
    mv_date = movement_date or date.today()
    doc_notes = (notes or '').strip()
    doc_code = next_issue_doc_code()
    doc_reason = issue_doc_reason(doc_code, ctx['issue_reason'])
    movements: list[StockMovement] = []
    seen_items: set[int] = set()
    qty_by_item: dict[int, float] = {}

    for raw in lines:
        try:
            item_id = int(raw.get('item_id') or 0)
            quantity = float(raw.get('quantity') or 0)
        except (TypeError, ValueError):
            raise ValueError('بيانات السطر غير صالحة') from None
        if item_id <= 0 or quantity <= 0:
            continue
        if item_id in seen_items:
            item = tenant_get_or_404(InventoryItem, item_id)
            name = (item.name or item.code or 'الصنف').strip()
            raise ValueError(f'الصنف «{name}» مكرر في الإذن')
        seen_items.add(item_id)
        qty_by_item[item_id] = qty_by_item.get(item_id, 0.0) + quantity

    for item_id, total_qty in qty_by_item.items():
        item = tenant_get_or_404(InventoryItem, item_id)
        validate_outbound_stock(item, total_qty)

    for raw in lines:
        try:
            item_id = int(raw.get('item_id') or 0)
            quantity = float(raw.get('quantity') or 0)
        except (TypeError, ValueError):
            continue
        if item_id <= 0 or quantity <= 0:
            continue

        item = tenant_get_or_404(InventoryItem, item_id)
        line_ctx = _resolve_issue_context(
            target=target,
            item=item,
            technician_id=technician_id,
            contract_id=contract_id,
            install_contract_id=install_contract_id,
        )
        movement = create_stock_movement(
            item=item,
            movement_date=mv_date,
            direction='صادر',
            movement_type=line_ctx['movement_type'],
            quantity=quantity,
            unit_price=item.buy_price or 0,
            technician_id=line_ctx['technician_id'],
            elevator_id=line_ctx['elevator_id'],
            reason=doc_reason,
            reference=issue_doc_reference(doc_code, item_id),
            notes=doc_notes or None,
        )
        movements.append(movement)

    if not movements:
        raise ValueError('أضف صنفاً واحداً على الأقل بكمية أكبر من صفر')

    return doc_code, movements


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
            'invoice_no': parse_movement_invoice(m.reference, m.reason),
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


def opening_stock_documents(limit: int = 40) -> list[dict]:
    """مستندات رصيد أول المدة المجمّعة برقم OS-xxxx."""
    import re
    from collections import OrderedDict

    pattern = re.compile(
        r'^' + re.escape(OPENING_DOC_REF_PREFIX) + r'(OS-\d+):item:\d+(?::inv:.+)?$'
    )
    rows = (
        tenant_query(StockMovement)
        .filter(
            StockMovement.movement_type == MOVEMENT_OPENING,
            StockMovement.direction == 'وارد',
            StockMovement.reference.isnot(None),
        )
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
        .all()
    )
    docs: OrderedDict[str, dict] = OrderedDict()
    for m in rows:
        ref = (m.reference or '').strip()
        if not pattern.match(ref):
            continue
        doc_code = ref.split(':')[1]
        if doc_code not in docs:
            docs[doc_code] = {
                'code': doc_code,
                'movement_date': str(m.movement_date or ''),
                'line_count': 0,
                'total_qty': 0.0,
                'total_value': 0.0,
                'notes': m.notes or '',
                'invoice_numbers': [],
            }
        entry = docs[doc_code]
        entry['line_count'] += 1
        entry['total_qty'] = round(entry['total_qty'] + float(m.quantity or 0), 4)
        entry['total_value'] = round(entry['total_value'] + float(m.total_value or 0), 2)
        inv = parse_opening_invoice(ref)
        if inv and inv not in entry['invoice_numbers']:
            entry['invoice_numbers'].append(inv)
    out = []
    for doc in docs.values():
        doc['invoice_summary'] = '، '.join(doc.pop('invoice_numbers', [])) or '—'
        out.append(doc)
    return out[:limit]


def warehouse_page_context() -> dict:
    """بيانات مشتركة لصفحات المخزن (رصيد افتتاحي / أذون صرف)."""
    from inventory_custody import installation_contracts_for_custody, maintenance_contracts_for_custody
    from inventory_units import unit_allows_decimals

    items = tenant_query(InventoryItem).order_by(InventoryItem.name).all()
    technicians = (
        tenant_query(Technician)
        .filter(Technician.status.in_(['نشط', 'متاح', 'مشغول']))
        .order_by(Technician.name)
        .all()
    )
    return {
        'items': items,
        'technicians': technicians,
        'technicians_js': [{'id': t.id, 'name': t.name} for t in technicians],
        'maintenance_contracts_js': maintenance_contracts_for_custody(),
        'installation_contracts_js': installation_contracts_for_custody(),
        'today': date.today().isoformat(),
        'opening_documents': opening_stock_documents(),
        'next_opening_doc': next_opening_doc_code(),
        'next_purchase_doc': next_purchase_doc_code(),
        'purchase_documents': purchase_invoice_documents(),
        'next_issue_doc': next_issue_doc_code(),
        'issue_documents': issue_documents(),
        'suppliers': tenant_query(Supplier).filter(Supplier.active.is_(True)).order_by(Supplier.name).all(),
        'items_js': [
            {
                'id': i.id,
                'code': i.code or '',
                'name': i.name or '',
                'unit': i.unit or 'قطعة',
                'qty_decimals': unit_allows_decimals(i.unit),
                'buy_price': float(i.buy_price or 0),
                'current_qty': float(i.current_qty or 0),
            }
            for i in items
        ],
    }


def issue_documents(limit: int = 40) -> list[dict]:
    """مستندات إذن الصرف المجمّعة برقم IS-xxxx."""
    import re
    from collections import OrderedDict

    pattern = re.compile(
        r'^' + re.escape(ISSUE_DOC_REF_PREFIX) + r'(IS-\d+):item:\d+$'
    )
    rows = (
        tenant_query(StockMovement)
        .filter(
            StockMovement.direction == 'صادر',
            StockMovement.reference.isnot(None),
        )
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
        .all()
    )
    tech_names = {t.id: t.name for t in tenant_query(Technician).all()}
    docs: OrderedDict[str, dict] = OrderedDict()
    for m in rows:
        ref = (m.reference or '').strip()
        if not pattern.match(ref):
            continue
        doc_code = ref.split(':')[1]
        if doc_code not in docs:
            reason = m.reason or ''
            detail = reason.split('|', 1)[1].strip() if '|' in reason else reason
            docs[doc_code] = {
                'code': doc_code,
                'movement_date': str(m.movement_date or ''),
                'detail': detail or '—',
                'movement_type': m.movement_type or '—',
                'technician': tech_names.get(m.technician_id, '—') if m.technician_id else '—',
                'line_count': 0,
                'total_qty': 0.0,
                'total_value': 0.0,
                'notes': m.notes or '',
            }
        entry = docs[doc_code]
        entry['line_count'] += 1
        entry['total_qty'] = round(entry['total_qty'] + float(m.quantity or 0), 4)
        entry['total_value'] = round(entry['total_value'] + float(m.total_value or 0), 2)
    return list(docs.values())[:limit]


def purchase_invoice_documents(limit: int = 40) -> list[dict]:
    """فواتير الشراء المجمّعة برقم PI-xxxx."""
    import re
    from collections import OrderedDict

    pattern = re.compile(
        r'^' + re.escape(PURCHASE_DOC_REF_PREFIX) + r'(PI-\d+):inv:.+:item:\d+$'
    )
    rows = (
        tenant_query(StockMovement)
        .filter(
            StockMovement.movement_type == MOVEMENT_PURCHASE,
            StockMovement.direction == 'وارد',
            StockMovement.reference.isnot(None),
        )
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
        .all()
    )
    docs: OrderedDict[str, dict] = OrderedDict()
    for m in rows:
        ref = (m.reference or '').strip()
        if not pattern.match(ref):
            continue
        doc_code = ref.split(':')[1]
        if doc_code not in docs:
            reason = m.reason or ''
            supplier = ''
            if '| مورد:' in reason:
                supplier = reason.split('| مورد:', 1)[1].strip()
            docs[doc_code] = {
                'code': doc_code,
                'movement_date': str(m.movement_date or ''),
                'invoice_no': parse_movement_invoice(ref, reason),
                'supplier': supplier or '—',
                'line_count': 0,
                'total_qty': 0.0,
                'total_value': 0.0,
                'notes': m.notes or '',
            }
        entry = docs[doc_code]
        entry['line_count'] += 1
        entry['total_qty'] = round(entry['total_qty'] + float(m.quantity or 0), 4)
        entry['total_value'] = round(entry['total_value'] + float(m.total_value or 0), 2)
    return list(docs.values())[:limit]


def purchase_movements(limit: int = 300) -> list[dict]:
    """حركات المشتريات الواردة — فواتير شراء (ومشتريات قديمة إن وُجدت)."""
    from sqlalchemy.orm import joinedload

    purchase_types = (MOVEMENT_PURCHASE, MOVEMENT_PURCHASE_LEGACY)
    rows = (
        tenant_query(StockMovement)
        .options(joinedload(StockMovement.item))
        .filter(
            StockMovement.direction == 'وارد',
            StockMovement.movement_type.in_(purchase_types),
        )
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
        .limit(limit)
        .all()
    )
    tech_names = {t.id: t.name for t in tenant_query(Technician).all()}
    out = []
    for m in rows:
        out.append({
            'code': m.code or '',
            'movement_date': str(m.movement_date or ''),
            'movement_type': m.movement_type or '',
            'item_code': m.item.code if m.item else '',
            'item_name': m.item.name if m.item else '—',
            'quantity': float(m.quantity or 0),
            'item_unit': (m.item.unit if m.item else '') or 'قطعة',
            'total_value': float(m.total_value or 0),
            'reason': m.reason or '',
            'reference': m.reference or '',
            'invoice_no': parse_movement_invoice(m.reference, m.reason),
            'technician': tech_names.get(m.technician_id, '—') if m.technician_id else '—',
        })
    return out
