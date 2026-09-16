"""تصفير رصيد أول المدة — مستندات OS فقط."""
from inventory_warehouse import MOVEMENT_OPENING, record_opening_stock_batch
from models import InventoryItem, StockMovement, db


def _item(code='#OS1', qty=0.0):
    item = InventoryItem(code=code, name='صنف', category='قطع غيار', current_qty=qty, buy_price=5)
    db.session.add(item)
    db.session.flush()
    return item


def test_reset_opening_stock_recalculates_qty(client):
    from scripts.reset_tenant_opening_stock import recalculate_qty_from_movements

    with client.application.app_context():
        item = _item(qty=0)
        db.session.commit()
        item_id = item.id
        org_id = item.organization_id

        record_opening_stock_batch(
            lines=[{'item_id': item_id, 'quantity': 10, 'unit_price': 5}],
        )
        db.session.commit()
        item = db.session.get(InventoryItem, item_id)
        assert float(item.current_qty or 0) == 10
        assert StockMovement.query.filter_by(item_id=item_id, movement_type=MOVEMENT_OPENING).count() == 1

        StockMovement.query.filter_by(
            item_id=item_id,
            movement_type=MOVEMENT_OPENING,
        ).delete(synchronize_session=False)
        projected = recalculate_qty_from_movements(org_id)
        item.current_qty = projected.get(item_id, 0.0)
        db.session.commit()
        db.session.refresh(item)
        assert float(item.current_qty or 0) == 0
