"""إدارة أصناف المخزن — بدون كاتالوج تلقائي."""

from models import InventoryItem, StockMovement, PurchaseOrderLine, db

try:
    from inventory_parts_data import CATEGORIES, ITEMS
except ImportError:
    CATEGORIES = []
    ITEMS = []

CAT_BY_CODE = {code: name for code, name, _sort in CATEGORIES}


def ensure_inventory_catalog():
    """Legacy: لم يعد يُحمّل كاتالوجاً. يُبقي التوافق مع السكربتات القديمة."""
    if not ITEMS:
        return 0

    existing = {row.code for row in InventoryItem.query.with_entities(InventoryItem.code)}
    added = 0
    for cat_code, item_code, name_ar, name_en, description, unit in ITEMS:
        if item_code in existing:
            continue
        note_parts = [p for p in (name_en, description) if p]
        db.session.add(
            InventoryItem(
                code=item_code,
                name=name_ar,
                category=CAT_BY_CODE.get(cat_code, 'قطع غيار'),
                unit=unit or 'قطعة',
                notes=' — '.join(note_parts) if note_parts else None,
            )
        )
        existing.add(item_code)
        added += 1

    if added:
        db.session.commit()
    return added


def purge_inventory_catalog():
    """حذف أصناف الكاتالوج التلقائي (SP-xxx) وحركاتها المرتبطة.

    للتشغيل اليدوي فقط — مثال:
        flask shell
        >>> from seed_inventory_parts import purge_inventory_catalog
        >>> purge_inventory_catalog()
    """
    items = InventoryItem.query.filter(InventoryItem.code.like('SP-%')).all()
    if not items:
        return 0

    deleted = 0
    for item in items:
        StockMovement.query.filter_by(item_id=item.id).delete(synchronize_session=False)
        PurchaseOrderLine.query.filter_by(item_id=item.id).delete(synchronize_session=False)
        db.session.delete(item)
        deleted += 1
    db.session.commit()
    return deleted
