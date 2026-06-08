"""تحميل كاتالوج قطع الغيار إلى inventory_items."""

from models import InventoryItem, db

try:
    from inventory_parts_data import CATEGORIES, ITEMS
except ImportError:
    CATEGORIES = []
    ITEMS = []

CAT_BY_CODE = {code: name for code, name, _sort in CATEGORIES}


def ensure_inventory_catalog():
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
                category=CAT_BY_CODE.get(cat_code, "قطع غيار"),
                unit=unit or "قطعة",
                notes=" — ".join(note_parts) if note_parts else None,
            )
        )
        existing.add(item_code)
        added += 1

    if added:
        db.session.commit()
    return added
