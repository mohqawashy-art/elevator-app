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

INVENTORY_PRICE_DECIMALS = 6
INVENTORY_MONEY_DECIMALS = 4
PURCHASE_NOTES_DISCOUNT_MARKER = '| إجمالي قبل الخصم:'
PURCHASE_ATTACH_MARKER = '\n---LC-PI-ATTACH---\n'
DEFAULT_PURCHASE_TAX_PCT = 15.0


def round_inventory_price(value: float) -> float:
    return round(float(value or 0), INVENTORY_PRICE_DECIMALS)


def round_inventory_money(value: float) -> float:
    return round(float(value or 0), INVENTORY_MONEY_DECIMALS)

ISSUE_DOC_PREFIX = 'IS-'
ISSUE_DOC_REF_PREFIX = 'issue:'
ISSUE_META_SEP = '---LC-IS-META---'


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


def purchase_reason(
    doc_code: str,
    invoice_no: str,
    supplier: str = '',
    discount_approx: float = 0,
    tax_pct: float = DEFAULT_PURCHASE_TAX_PCT,
) -> str:
    inv = (invoice_no or '').strip()
    reason = f'فاتورة شراء — {doc_code} | فاتورة: {inv[:80]}'
    sup = (supplier or '').strip()
    if sup:
        reason = f'{reason} | مورد: {sup[:60]}'
    disc = round(float(discount_approx or 0), 2)
    if disc > 0:
        reason = f'{reason} | خصم: {disc:.2f}'
    pct = round(float(tax_pct if tax_pct is not None else DEFAULT_PURCHASE_TAX_PCT), 2)
    if pct > 0:
        reason = f'{reason} | ضريبة: {pct:.0f}%'
    return reason[:300]


def parse_purchase_user_notes(notes: str | None) -> str:
    text = (notes or '').strip()
    if PURCHASE_ATTACH_MARKER in text:
        text = text.split(PURCHASE_ATTACH_MARKER, 1)[0].strip()
    if PURCHASE_NOTES_DISCOUNT_MARKER in text:
        return text.split(PURCHASE_NOTES_DISCOUNT_MARKER, 1)[0].strip(' |')
    return text


def parse_purchase_attachment_paths(notes: str | None) -> list[str]:
    from attachment_paths import parse_attachment_paths

    text = notes or ''
    if PURCHASE_ATTACH_MARKER not in text:
        return []
    blob = text.split(PURCHASE_ATTACH_MARKER, 1)[1].strip()
    return parse_attachment_paths(blob)


def build_purchase_document_notes(
    user_notes: str,
    discount_extra: str | None,
    attachment_paths: list[str] | None,
) -> str | None:
    from attachment_paths import serialize_attachment_paths

    base = (user_notes or '').strip()
    extra = (discount_extra or '').strip()
    if extra:
        base = f'{base} | {extra}'.strip(' |') if base else extra
    paths = [p for p in (attachment_paths or []) if (p or '').strip()]
    if paths:
        serialized = serialize_attachment_paths(paths)
        if serialized:
            base = (base or '') + PURCHASE_ATTACH_MARKER + serialized
    return base or None


def purchase_invoice_attachment_paths(doc_code: str) -> list[str]:
    movements = purchase_invoice_movements(doc_code)
    if not movements:
        return []
    return parse_purchase_attachment_paths(movements[0].notes)


def refresh_purchase_invoice_notes(
    doc_code: str,
    *,
    user_notes: str = '',
    discount_approx: float = 0,
    attachment_paths: list[str] | None = None,
) -> None:
    movements = purchase_invoice_movements(doc_code)
    if not movements:
        return
    paths = (
        list(attachment_paths)
        if attachment_paths is not None
        else purchase_invoice_attachment_paths(doc_code)
    )
    discount = round(max(0.0, float(discount_approx or 0)), 2)
    net = round_inventory_money(sum(float(m.total_value or 0) for m in movements))
    gross = round_inventory_money(net + discount)
    discount_extra = None
    if discount > 0:
        discount_extra = (
            f'إجمالي قبل الخصم: {gross:.2f} | '
            f'خصم تقريبي: {discount:.2f} | '
            f'صافي: {net:.2f}'
        )
    final_notes = build_purchase_document_notes(user_notes, discount_extra, paths)
    for movement in movements:
        movement.notes = final_notes


def parse_purchase_tax_pct(reason: str | None) -> float:
    text = (reason or '').strip()
    marker = '| ضريبة:'
    if marker not in text:
        return DEFAULT_PURCHASE_TAX_PCT
    raw = text.split(marker, 1)[1].split('|', 1)[0].strip().replace('%', '')
    try:
        return max(0.0, round(float(raw), 2))
    except (TypeError, ValueError):
        return DEFAULT_PURCHASE_TAX_PCT


def purchase_invoice_totals(doc: dict) -> dict:
    """ملخص فاتورة — إجمالي، خصم، صافي، ضريبة، شامل."""
    gross = round_inventory_money(float(doc.get('gross_total') or 0))
    discount = round_inventory_money(float(doc.get('discount_approx') or 0))
    net = round_inventory_money(float(doc.get('total_value') or 0))
    tax_pct = round(float(doc.get('tax_pct') or DEFAULT_PURCHASE_TAX_PCT), 2)
    tax_amount = round_inventory_money(net * tax_pct / 100.0) if tax_pct > 0 else 0.0
    grand_total = round_inventory_money(net + tax_amount)
    return {
        'gross_total': gross,
        'discount_approx': discount,
        'net_total': net,
        'tax_pct': tax_pct,
        'tax_amount': tax_amount,
        'grand_total': grand_total,
    }


def parse_purchase_supplier(reason: str | None) -> str:
    text = (reason or '').strip()
    marker = '| مورد:'
    if marker not in text:
        return ''
    return text.split(marker, 1)[1].split('|', 1)[0].strip()


def purchase_doc_code_from_reference(reference: str | None) -> str:
    ref = (reference or '').strip()
    if not ref.startswith(PURCHASE_DOC_REF_PREFIX):
        return ''
    parts = ref.split(':')
    return parts[1] if len(parts) >= 2 else ''


def parse_purchase_discount(reason: str | None) -> float:
    text = (reason or '').strip()
    marker = '| خصم:'
    if marker not in text:
        return 0.0
    raw = text.split(marker, 1)[1].split('|', 1)[0].strip()
    try:
        return max(0.0, round(float(raw), 2))
    except (TypeError, ValueError):
        return 0.0


def distribute_purchase_discount(
    lines: list[dict],
    discount_approx: float,
) -> tuple[float, float, list[dict]]:
    """توزيع الخصم التقريبي على أسطر الفاتورة — (إجمالي قبل، خصم، أسطر بسعر صافٍ)."""
    prepared: list[dict] = []
    gross_total = 0.0
    for raw in lines:
        qty = float(raw['quantity'])
        price = float(raw['unit_price'])
        line_gross = round_inventory_money(qty * price)
        gross_total += line_gross
        prepared.append({**raw, 'line_gross': line_gross})

    gross_total = round_inventory_money(gross_total)
    discount = round(max(0.0, float(discount_approx or 0)), 2)
    if discount > gross_total + 1e-9:
        raise ValueError('الخصم أكبر من إجمالي الفاتورة')
    if discount <= 0 or gross_total <= 0:
        for row in prepared:
            row['net_unit_price'] = float(row['unit_price'])
            row['net_total'] = row['line_gross']
        return gross_total, 0.0, prepared

    allocated = 0.0
    for idx, row in enumerate(prepared):
        if idx == len(prepared) - 1:
            line_discount = round(discount - allocated, 2)
        else:
            share = row['line_gross'] / gross_total if gross_total else 0.0
            line_discount = round(discount * share, 2)
            allocated += line_discount
        net_total = round(max(0.0, row['line_gross'] - line_discount), 2)
        qty = float(row['quantity'])
        row['net_total'] = net_total
        row['net_unit_price'] = round_inventory_price(net_total / qty) if qty else 0.0
    return gross_total, discount, prepared


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


def purchase_invoice_no_taken(invoice_no: str, exclude_doc_code: str | None = None) -> bool:
    inv = (invoice_no or '').strip()
    if not inv:
        return False
    needle = f':inv:{inv[:40]}:item:'
    rows = (
        tenant_query(StockMovement)
        .filter(
            StockMovement.movement_type == MOVEMENT_PURCHASE,
            StockMovement.reference.like(f'{PURCHASE_DOC_REF_PREFIX}%{needle}%'),
        )
        .all()
    )
    exclude = (exclude_doc_code or '').strip()
    for row in rows:
        doc = purchase_doc_code_from_reference(row.reference)
        if exclude and doc == exclude:
            continue
        return True
    return False


def purchase_invoice_movements(doc_code: str) -> list[StockMovement]:
    code = (doc_code or '').strip()
    if not code.startswith(PURCHASE_DOC_PREFIX):
        return []
    prefix = f'{PURCHASE_DOC_REF_PREFIX}{code}:inv:'
    return (
        tenant_query(StockMovement)
        .filter(
            StockMovement.movement_type == MOVEMENT_PURCHASE,
            StockMovement.reference.like(f'{prefix}%'),
        )
        .order_by(StockMovement.id)
        .all()
    )


def reverse_purchase_invoice_document(doc_code: str) -> int:
    movements = purchase_invoice_movements(doc_code)
    if not movements:
        raise ValueError(f'فاتورة الشراء «{doc_code}» غير موجودة')
    for movement in movements:
        item = db.session.get(InventoryItem, movement.item_id)
        if item:
            adjust_inventory_qty(item, movement.direction, movement.quantity, reverse=True)
        db.session.delete(movement)
    return len(movements)


def purchase_invoice_for_edit(doc_code: str) -> dict | None:
    movements = purchase_invoice_movements(doc_code)
    if not movements:
        return None
    first = movements[0]
    reason = first.reason or ''
    discount = parse_purchase_discount(reason)
    net_doc = round_inventory_money(sum(float(m.total_value or 0) for m in movements))
    gross_doc = round_inventory_money(net_doc + discount)
    lines: list[dict] = []
    for movement in movements:
        qty = float(movement.quantity or 0)
        line_net = float(movement.total_value or 0)
        if discount > 0 and net_doc > 0:
            line_gross = round_inventory_money(line_net * gross_doc / net_doc)
        else:
            line_gross = round_inventory_money(line_net)
        gross_unit = round_inventory_price(line_gross / qty) if qty else 0.0
        lines.append({
            'item_id': movement.item_id,
            'quantity': qty,
            'unit_price': gross_unit,
        })
    return {
        'code': doc_code,
        'invoice_no': parse_movement_invoice(first.reference, reason),
        'supplier': parse_purchase_supplier(reason),
        'movement_date': str(first.movement_date or ''),
        'discount_approx': discount,
        'tax_pct': parse_purchase_tax_pct(reason),
        'notes': parse_purchase_user_notes(first.notes),
        'attachments': purchase_invoice_attachment_paths(doc_code),
        'lines': lines,
    }


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

ISSUE_TARGET_LABELS = {
    ISSUE_TARGET_CLIENT: 'تحميل على عميل — عقد صيانة',
    ISSUE_TARGET_PROJECT: 'تحميل على مشروع — عقد تركيب',
    ISSUE_TARGET_CUSTODY: 'عهدة فني (قطع غيار)',
    ISSUE_TARGET_CONSUMABLE: 'مستهلكات صيانة',
}


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

    price = round_inventory_price(unit_price if unit_price is not None else (item.buy_price or 0))
    movement = StockMovement(
        code=next_code(StockMovement, 'MV-', digits=3),
        item_id=int(item.id),
        movement_date=movement_date or date.today(),
        direction=direction,
        movement_type=(movement_type or '').strip() or '—',
        quantity=qty,
        unit_price=price,
        total_value=round_inventory_money(qty * price),
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


def opening_document_movements(doc_code: str) -> list[StockMovement]:
    code = (doc_code or '').strip()
    if not code.startswith(OPENING_DOC_PREFIX):
        return []
    prefix = f'{OPENING_DOC_REF_PREFIX}{code}:item:'
    return (
        tenant_query(StockMovement)
        .filter(
            StockMovement.movement_type == MOVEMENT_OPENING,
            StockMovement.reference.like(f'{prefix}%'),
        )
        .order_by(StockMovement.id)
        .all()
    )


def reverse_opening_document(doc_code: str) -> int:
    movements = opening_document_movements(doc_code)
    if not movements:
        raise ValueError(f'مستند رصيد أول المدة «{doc_code}» غير موجود')
    for movement in movements:
        item = db.session.get(InventoryItem, movement.item_id)
        if item:
            adjust_inventory_qty(item, movement.direction, movement.quantity, reverse=True)
        db.session.delete(movement)
    return len(movements)


def record_opening_stock_batch(
    *,
    lines: list[dict],
    movement_date: date | None = None,
    notes: str = '',
    doc_code: str | None = None,
) -> tuple[str, list[StockMovement]]:
    """تسجيل مستند رصيد أول المدة — عدة أصناف برقم مستند واحد OS-xxxx."""
    if not lines:
        raise ValueError('أضف صنفاً واحداً على الأقل')

    mv_date = movement_date or date.today()
    doc_notes = (notes or '').strip()
    resolved_doc = (doc_code or '').strip()
    if resolved_doc:
        if not resolved_doc.startswith(OPENING_DOC_PREFIX):
            raise ValueError('رقم المستند غير صالح')
        doc_code = resolved_doc
    else:
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


def update_opening_batch(
    doc_code: str,
    *,
    lines: list[dict],
    movement_date: date | None = None,
    notes: str = '',
) -> tuple[str, list[StockMovement]]:
    """تعديل مستند رصيد أول المدة — عكس المخزون القديم ثم إعادة التسجيل بنفس OS."""
    code = (doc_code or '').strip()
    if not code.startswith(OPENING_DOC_PREFIX):
        raise ValueError('رقم المستند غير صالح')
    reverse_opening_document(code)
    return record_opening_stock_batch(
        lines=lines,
        movement_date=movement_date,
        notes=notes,
        doc_code=code,
    )


def record_purchase_invoice_batch(
    *,
    lines: list[dict],
    invoice_no: str,
    movement_date: date | None = None,
    supplier: str = '',
    notes: str = '',
    discount_approx: float = 0,
    doc_code: str | None = None,
    exclude_doc_code: str | None = None,
    tax_pct: float = DEFAULT_PURCHASE_TAX_PCT,
    attachment_paths: list[str] | None = None,
) -> tuple[str, list[StockMovement]]:
    """تسجيل فاتورة شراء — عدة أصniaف برقم مستند PI-xxxx وفاتورة واحدة."""
    inv = (invoice_no or '').strip()
    if not inv:
        raise ValueError('أدخل رقم فاتورة الشراء')
    if not lines:
        raise ValueError('أضف صنفاً واحداً على الأقل')

    resolved_doc = (doc_code or '').strip()
    skip_doc = exclude_doc_code or resolved_doc or None
    if purchase_invoice_no_taken(inv, exclude_doc_code=skip_doc):
        raise ValueError(f'فاتورة الشراء «{inv}» مسجّلة مسبقاً')

    if resolved_doc:
        if not resolved_doc.startswith(PURCHASE_DOC_PREFIX):
            raise ValueError('رقم المستند غير صالح')
        doc_code = resolved_doc
    else:
        doc_code = next_purchase_doc_code()

    sup = (supplier or '').strip()
    mv_date = movement_date or date.today()
    doc_notes = (notes or '').strip()
    movements: list[StockMovement] = []
    seen_items: set[int] = set()
    parsed_lines: list[dict] = []

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
        parsed_lines.append({
            'item_id': item_id,
            'item': item,
            'quantity': quantity,
            'unit_price': price,
        })

    if not parsed_lines:
        raise ValueError('أضف صنفاً واحداً على الأقل بكمية أكبر من صفر')

    gross_total, discount, priced_lines = distribute_purchase_discount(
        parsed_lines,
        discount_approx,
    )
    pct = round(float(tax_pct if tax_pct is not None else DEFAULT_PURCHASE_TAX_PCT), 2)
    doc_reason = purchase_reason(doc_code, inv, sup, discount, tax_pct=pct)
    discount_extra = None
    if discount > 0:
        discount_extra = (
            f'إجمالي قبل الخصم: {gross_total:.2f} | '
            f'خصم تقريبي: {discount:.2f} | '
            f'صافي: {round(gross_total - discount, 2):.2f}'
        )
    doc_notes = build_purchase_document_notes(doc_notes, discount_extra, attachment_paths)

    for row in priced_lines:
        item = row['item']
        quantity = float(row['quantity'])
        net_price = float(row['net_unit_price'])
        movement = create_stock_movement(
            item=item,
            movement_date=mv_date,
            direction='وارد',
            movement_type=MOVEMENT_PURCHASE,
            quantity=quantity,
            unit_price=net_price,
            reason=doc_reason,
            reference=purchase_doc_reference(doc_code, item.id, inv),
            notes=doc_notes or None,
        )
        if net_price > 0:
            item.buy_price = net_price
            if sup:
                item.supplier = sup
        movements.append(movement)

    return doc_code, movements


def update_purchase_invoice_batch(
    doc_code: str,
    *,
    lines: list[dict],
    invoice_no: str,
    movement_date: date | None = None,
    supplier: str = '',
    notes: str = '',
    discount_approx: float = 0,
    tax_pct: float = DEFAULT_PURCHASE_TAX_PCT,
    attachment_paths: list[str] | None = None,
) -> tuple[str, list[StockMovement]]:
    """تعديل فاتورة شراء — عكس المخزون القديم ثم إعادة التسجيل بنفس PI."""
    code = (doc_code or '').strip()
    if not code.startswith(PURCHASE_DOC_PREFIX):
        raise ValueError('رقم المستند غير صالح')
    preserved_attachments = (
        list(attachment_paths)
        if attachment_paths is not None
        else purchase_invoice_attachment_paths(code)
    )
    reverse_purchase_invoice_document(code)
    return record_purchase_invoice_batch(
        lines=lines,
        invoice_no=invoice_no,
        movement_date=movement_date,
        supplier=supplier,
        notes=notes,
        discount_approx=discount_approx,
        doc_code=code,
        exclude_doc_code=code,
        tax_pct=tax_pct,
        attachment_paths=preserved_attachments,
    )


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


def issue_doc_code_from_reference(reference: str | None) -> str:
    ref = (reference or '').strip()
    if not ref.startswith(ISSUE_DOC_REF_PREFIX):
        return ''
    parts = ref.split(':')
    return parts[1] if len(parts) >= 2 else ''


def _split_issue_notes(notes: str | None) -> tuple[str, str]:
    text = notes or ''
    idx = text.find(ISSUE_META_SEP)
    if idx < 0:
        return text.strip(), ''
    return text[:idx].strip(), text[idx + len(ISSUE_META_SEP):].strip()


def parse_issue_user_notes(notes: str | None) -> str:
    user, _ = _split_issue_notes(notes)
    return user


def parse_stock_movement_user_notes(notes: str | None, reference: str | None = None) -> str:
    """ملاحظات ظاهرة للمستخدم — بدون بيانات IS/PI الداخلية."""
    ref = (reference or '').strip()
    if ref.startswith(ISSUE_DOC_REF_PREFIX) or ISSUE_META_SEP in (notes or ''):
        return parse_issue_user_notes(notes)
    if ref.startswith(PURCHASE_DOC_REF_PREFIX):
        return parse_purchase_user_notes(notes)
    text = notes or ''
    if PURCHASE_ATTACH_MARKER in text or PURCHASE_NOTES_DISCOUNT_MARKER in text:
        return parse_purchase_user_notes(notes)
    return text.strip()


def parse_issue_meta(notes: str | None) -> dict:
    import json

    _, raw = _split_issue_notes(notes)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def build_issue_document_notes(user_notes: str, meta: dict | None) -> str | None:
    import json

    base = (user_notes or '').strip()
    if meta:
        clean_meta = {
            key: meta[key]
            for key in ('target', 'technician_id', 'contract_id', 'install_contract_id')
            if key in meta and meta[key] not in (None, '')
        }
        if clean_meta:
            meta_blob = json.dumps(clean_meta, ensure_ascii=False)
            base = f'{base}{ISSUE_META_SEP}{meta_blob}' if base else f'{ISSUE_META_SEP}{meta_blob}'
    return base or None


def issue_document_movements(doc_code: str) -> list[StockMovement]:
    code = (doc_code or '').strip()
    if not code.startswith(ISSUE_DOC_PREFIX):
        return []
    prefix = f'{ISSUE_DOC_REF_PREFIX}{code}:item:'
    return (
        tenant_query(StockMovement)
        .filter(
            StockMovement.direction == 'صادر',
            StockMovement.reference.like(f'{prefix}%'),
        )
        .order_by(StockMovement.id)
        .all()
    )


def reverse_issue_document(doc_code: str) -> int:
    movements = issue_document_movements(doc_code)
    if not movements:
        raise ValueError(f'إذن الصرف «{doc_code}» غير موجود')
    for movement in movements:
        item = db.session.get(InventoryItem, movement.item_id)
        if item:
            adjust_inventory_qty(item, movement.direction, movement.quantity, reverse=True)
        db.session.delete(movement)
    return len(movements)


def _match_contract_id_from_detail(detail: str) -> int | None:
    from models import Contract

    code = (detail or '').split('—', 1)[0].strip()
    if not code:
        return None
    row = tenant_query(Contract).filter(Contract.code == code).first()
    return int(row.id) if row else None


def _match_install_contract_id_from_detail(detail: str) -> int | None:
    from installation.models import InstallContract

    code = (detail or '').split('—', 1)[0].strip()
    if not code:
        return None
    row = tenant_query(InstallContract).filter(InstallContract.code == code).first()
    return int(row.id) if row else None


def infer_issue_edit_context(movements: list[StockMovement]) -> dict:
    first = movements[0]
    meta = parse_issue_meta(first.notes)
    if meta.get('target'):
        return meta
    reason = first.reason or ''
    detail = reason.split('|', 1)[1].strip() if '|' in reason else reason
    target = ISSUE_TARGET_CONSUMABLE
    contract_id = None
    install_contract_id = None
    movement_type = (first.movement_type or '').strip()
    if movement_type == MOVEMENT_ISSUE_CUSTODY:
        target = ISSUE_TARGET_CUSTODY
    elif movement_type == MOVEMENT_ISSUE_SITE:
        contract_id = _match_contract_id_from_detail(detail)
        if contract_id:
            target = ISSUE_TARGET_CLIENT
        else:
            install_contract_id = _match_install_contract_id_from_detail(detail)
            target = ISSUE_TARGET_PROJECT if install_contract_id else ISSUE_TARGET_CONSUMABLE
    return {
        'target': target,
        'technician_id': first.technician_id,
        'contract_id': contract_id,
        'install_contract_id': install_contract_id,
    }


def issue_document_for_edit(doc_code: str) -> dict | None:
    movements = issue_document_movements(doc_code)
    if not movements:
        return None
    first = movements[0]
    ctx = infer_issue_edit_context(movements)
    reason = first.reason or ''
    detail = reason.split('|', 1)[1].strip() if '|' in reason else reason
    lines = [
        {
            'item_id': movement.item_id,
            'quantity': float(movement.quantity or 0),
        }
        for movement in movements
    ]
    return {
        'code': doc_code,
        'movement_date': str(first.movement_date or ''),
        'target': ctx.get('target') or ISSUE_TARGET_CONSUMABLE,
        'technician_id': ctx.get('technician_id'),
        'contract_id': ctx.get('contract_id'),
        'install_contract_id': ctx.get('install_contract_id'),
        'notes': parse_issue_user_notes(first.notes),
        'detail': detail or '—',
        'movement_type': first.movement_type or '—',
        'lines': lines,
    }


def issue_print_payload(doc_code: str) -> dict | None:
    from sqlalchemy.orm import joinedload

    movements = (
        tenant_query(StockMovement)
        .options(joinedload(StockMovement.item))
        .filter(
            StockMovement.direction == 'صادر',
            StockMovement.reference.like(f'{ISSUE_DOC_REF_PREFIX}{doc_code}:item:%'),
        )
        .order_by(StockMovement.id)
        .all()
    )
    if not movements:
        return None
    first = movements[0]
    ctx = infer_issue_edit_context(movements)
    reason = first.reason or ''
    detail = reason.split('|', 1)[1].strip() if '|' in reason else reason
    tech_names = {t.id: t.name for t in tenant_query(Technician).all()}
    lines = []
    total_qty = 0.0
    total_value = 0.0
    for movement in movements:
        item = movement.item
        qty = float(movement.quantity or 0)
        unit_price = float(movement.unit_price or 0)
        line_total = float(movement.total_value or 0)
        total_qty += qty
        total_value += line_total
        lines.append({
            'code': item.code if item else '—',
            'name': item.name if item else '—',
            'unit': (item.unit if item else '') or 'قطعة',
            'quantity': qty,
            'unit_price': unit_price,
            'total_value': line_total,
        })
    target = ctx.get('target') or ISSUE_TARGET_CONSUMABLE
    return {
        'doc_code': doc_code,
        'movement_date': str(first.movement_date or ''),
        'target': target,
        'target_label': ISSUE_TARGET_LABELS.get(target, target),
        'detail': detail or '—',
        'movement_type': first.movement_type or '—',
        'technician': tech_names.get(first.technician_id, '—') if first.technician_id else '—',
        'notes': parse_issue_user_notes(first.notes) or '—',
        'lines': lines,
        'line_count': len(lines),
        'total_qty': round(total_qty, 4),
        'total_value': round(total_value, 2),
    }


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
    doc_code: str | None = None,
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
    user_notes = (notes or '').strip()
    resolved_doc = (doc_code or '').strip()
    if resolved_doc:
        if not resolved_doc.startswith(ISSUE_DOC_PREFIX):
            raise ValueError('رقم الإذن غير صالح')
        doc_code = resolved_doc
    else:
        doc_code = next_issue_doc_code()
    meta = {
        'target': target,
        'technician_id': technician_id,
        'contract_id': contract_id,
        'install_contract_id': install_contract_id,
    }
    doc_notes = build_issue_document_notes(user_notes, meta)
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


def update_issue_batch(
    doc_code: str,
    *,
    lines: list[dict],
    target: str,
    movement_date: date | None = None,
    technician_id: int | None = None,
    contract_id: int | None = None,
    install_contract_id: int | None = None,
    notes: str = '',
) -> tuple[str, list[StockMovement]]:
    """تعديل إذن صرف — عكس المخزون القديم ثم إعادة التسجيل بنفس IS."""
    code = (doc_code or '').strip()
    if not code.startswith(ISSUE_DOC_PREFIX):
        raise ValueError('رقم الإذن غير صالح')
    reverse_issue_document(code)
    return record_issue_batch(
        lines=lines,
        target=target,
        movement_date=movement_date,
        technician_id=technician_id,
        contract_id=contract_id,
        install_contract_id=install_contract_id,
        notes=notes,
        doc_code=code,
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
            'notes': parse_stock_movement_user_notes(m.notes, m.reference),
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
                'notes': parse_stock_movement_user_notes(m.notes, m.reference),
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


def opening_document_for_edit(doc_code: str) -> dict | None:
    movements = opening_document_movements(doc_code)
    if not movements:
        return None
    first = movements[0]
    lines: list[dict] = []
    for movement in movements:
        item = movement.item
        lines.append({
            'item_id': movement.item_id,
            'item_code': item.code if item else '',
            'item_name': item.name if item else '',
            'quantity': float(movement.quantity or 0),
            'unit_price': float(movement.unit_price or 0),
            'invoice_no': parse_opening_invoice(movement.reference),
        })
    return {
        'code': doc_code,
        'movement_date': str(first.movement_date or ''),
        'notes': parse_stock_movement_user_notes(first.notes, first.reference),
        'lines': lines,
        'line_count': len(lines),
        'total_qty': round(sum(float(m.quantity or 0) for m in movements), 4),
        'total_value': round(sum(float(m.total_value or 0) for m in movements), 2),
    }


def opening_print_payload(doc_code: str) -> dict | None:
    movements = opening_document_movements(doc_code)
    if not movements:
        return None
    first = movements[0]
    lines = []
    total_qty = 0.0
    total_value = 0.0
    invoice_numbers: list[str] = []
    for movement in movements:
        item = movement.item
        qty = float(movement.quantity or 0)
        unit_price = float(movement.unit_price or 0)
        line_total = float(movement.total_value or 0)
        total_qty += qty
        total_value += line_total
        inv = parse_opening_invoice(movement.reference)
        if inv and inv not in invoice_numbers:
            invoice_numbers.append(inv)
        lines.append({
            'code': item.code if item else '—',
            'name': item.name if item else '—',
            'unit': (item.unit if item else '') or 'قطعة',
            'quantity': qty,
            'unit_price': unit_price,
            'total_value': line_total,
            'invoice_no': inv or '—',
        })
    return {
        'doc_code': doc_code,
        'movement_date': str(first.movement_date or ''),
        'notes': parse_stock_movement_user_notes(first.notes, first.reference) or '—',
        'lines': lines,
        'line_count': len(lines),
        'total_qty': round(total_qty, 4),
        'total_value': round(total_value, 2),
        'invoice_summary': '، '.join(invoice_numbers) or '—',
    }


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
                'notes': parse_issue_user_notes(m.notes),
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
            docs[doc_code] = {
                'code': doc_code,
                'movement_date': str(m.movement_date or ''),
                'invoice_no': parse_movement_invoice(ref, reason),
                'supplier': parse_purchase_supplier(reason) or '—',
                'discount_approx': parse_purchase_discount(reason),
                'tax_pct': parse_purchase_tax_pct(reason),
                'attachment_count': len(parse_purchase_attachment_paths(m.notes)),
                'gross_total': 0.0,
                'line_count': 0,
                'total_qty': 0.0,
                'total_value': 0.0,
                'notes': parse_purchase_user_notes(m.notes),
            }
        entry = docs[doc_code]
        entry['line_count'] += 1
        entry['total_qty'] = round(entry['total_qty'] + float(m.quantity or 0), 4)
        entry['total_value'] = round(entry['total_value'] + float(m.total_value or 0), 2)
    out = []
    for doc in docs.values():
        disc = float(doc.pop('discount_approx', 0) or 0)
        net = float(doc['total_value'] or 0)
        doc['gross_total'] = round(net + disc, 2)
        doc['discount_approx'] = disc
        totals = purchase_invoice_totals(doc)
        doc.update(totals)
        out.append(doc)
    return out[:limit]


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
