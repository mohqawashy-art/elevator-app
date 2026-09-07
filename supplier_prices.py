"""منطق قوائم أسعار الموردين — ربط RFQ / PO / المخزن."""
from __future__ import annotations

from datetime import date, datetime

from models import InventoryItem, Supplier, SupplierPrice, db
from tenant_scope import tenant_query


def find_supplier_by_name(name: str):
    name = (name or '').strip()
    if not name:
        return None
    return tenant_query(Supplier).filter(Supplier.name == name).first()


def find_or_create_supplier(name: str, phone: str | None = None, email: str | None = None, assign_org_fn=None):
    """إنشاء مورد أو إرجاع الموجود — assign_org_fn من app.assign_organization."""
    name = (name or '').strip()
    if not name:
        return None
    existing = find_supplier_by_name(name)
    if existing:
        if phone and not existing.phone:
            existing.phone = phone.strip() or None
        if email and not existing.email:
            existing.email = email.strip() or None
        return existing
    sup = Supplier(name=name, phone=(phone or '').strip() or None, email=(email or '').strip() or None, active=True)
    if assign_org_fn:
        assign_org_fn(sup)
    db.session.add(sup)
    db.session.flush()
    return sup


def upsert_supplier_price(
    supplier_id: int,
    item_id: int,
    unit_price: float,
    *,
    source: str = 'manual',
    source_ref: str | None = None,
    notes: str | None = None,
    lead_days: int | None = None,
    assign_org_fn=None,
    sync_inventory: bool = True,
) -> SupplierPrice:
    unit_price = float(unit_price or 0)
    if unit_price < 0:
        unit_price = 0
    row = tenant_query(SupplierPrice).filter_by(supplier_id=supplier_id, item_id=item_id).first()
    if not row:
        row = SupplierPrice(
            supplier_id=supplier_id,
            item_id=item_id,
            unit_price=unit_price,
            source=source,
            source_ref=source_ref,
            notes=notes,
            lead_days=lead_days,
            valid_from=date.today(),
        )
        if assign_org_fn:
            assign_org_fn(row)
        db.session.add(row)
    else:
        row.unit_price = unit_price
        row.source = source
        row.source_ref = source_ref
        if notes:
            row.notes = notes
        if lead_days is not None:
            row.lead_days = lead_days
        row.updated_at = datetime.utcnow()
    if sync_inventory:
        sync_item_buy_price(item_id, unit_price, supplier_id)
    return row


def sync_item_buy_price(item_id: int, unit_price: float, supplier_id: int | None = None) -> None:
    item = db.session.get(InventoryItem, item_id)
    if not item:
        return
    item.buy_price = float(unit_price or 0)
    if supplier_id:
        sup = db.session.get(Supplier, supplier_id)
        if sup:
            item.supplier = sup.name


def lookup_price(supplier_id: int | None, item_id: int, supplier_name: str | None = None) -> float | None:
    if supplier_id:
        row = tenant_query(SupplierPrice).filter_by(supplier_id=supplier_id, item_id=item_id).first()
        if row:
            return float(row.unit_price or 0)
    if supplier_name:
        sup = find_supplier_by_name(supplier_name.strip())
        if sup:
            row = tenant_query(SupplierPrice).filter_by(supplier_id=sup.id, item_id=item_id).first()
            if row:
                return float(row.unit_price or 0)
    item = db.session.get(InventoryItem, item_id)
    if item and item.buy_price:
        return float(item.buy_price)
    return None


def prices_for_item(item_id: int) -> list[dict]:
    rows = (
        tenant_query(SupplierPrice).filter_by(item_id=item_id)
        .join(Supplier)
        .order_by(Supplier.name)
        .all()
    )
    out = []
    for r in rows:
        out.append({
            'supplier_id': r.supplier_id,
            'supplier_name': r.supplier.name if r.supplier else '',
            'unit_price': float(r.unit_price or 0),
            'lead_days': r.lead_days,
            'updated_at': r.updated_at.isoformat() if r.updated_at else None,
            'source': r.source,
        })
    return out


def apply_rfq_quoted_prices(rfq, assign_org_fn=None) -> int:
    """تحديث قائمة الأسعار من بنود RFQ ذات سعر معتمد."""
    if not rfq or not rfq.supplier_id:
        return 0
    count = 0
    for line in rfq.lines or []:
        if not line.item_id:
            continue
        price = line.quoted_unit_price
        if price is None or float(price) <= 0:
            continue
        upsert_supplier_price(
            rfq.supplier_id,
            line.item_id,
            float(price),
            source='rfq',
            source_ref=rfq.code,
            assign_org_fn=assign_org_fn,
        )
        count += 1
    return count
