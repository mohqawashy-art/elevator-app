"""مرحلة 1 — مخزن: رصيد افتتاحي، صرف، PO حركة، كارت صنف."""
from datetime import date

from inventory_warehouse import (
    MOVEMENT_OPENING,
    record_issue_authorization,
    record_opening_stock,
    record_purchase_receipt_movements,
    validate_outbound_stock,
)
from models import Contract, Customer, InventoryItem, PurchaseOrder, PurchaseOrderLine, StockMovement, db


def _item(code='#WH1', qty=10.0, category='قطع غيار'):
    item = InventoryItem(code=code, name='صنف مخزن', category=category, current_qty=qty, buy_price=5)
    db.session.add(item)
    db.session.flush()
    return item


def test_opening_stock_creates_movement(client):
    with client.application.app_context():
        item = _item(qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        item = db.session.get(InventoryItem, item_id)
        m = record_opening_stock(item_id=item.id, quantity=7, unit_price=5)
        db.session.commit()
        db.session.refresh(item)
        assert m.movement_type == MOVEMENT_OPENING
        assert item.current_qty == 7


def test_issue_rejects_insufficient_stock(client):
    with client.application.app_context():
        item = _item(qty=1)
        with __import__('pytest').raises(ValueError, match='غير كاف'):
            validate_outbound_stock(item, 2)


def test_issue_consumable_reduces_stock(client):
    with client.application.app_context():
        item = _item(qty=5, category='مستهلكات')
        m = record_issue_authorization(
            item_id=item.id,
            quantity=2,
            target='consumable',
        )
        db.session.commit()
        db.session.refresh(item)
        assert item.current_qty == 3
        assert m.direction == 'صادر'


def test_po_receipt_creates_movement_once(client):
    with client.application.app_context():
        item = _item(qty=1)
        order = PurchaseOrder(
            code='PO-WH1',
            supplier='مورد',
            order_date=date.today(),
            status='مستلم',
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(PurchaseOrderLine(
            order_id=order.id,
            item_id=item.id,
            quantity=4,
            unit_price=6,
        ))
        db.session.commit()
        order_id = order.id
        item_id = item.id

    with client.application.app_context():
        order = db.session.get(PurchaseOrder, order_id)
        item = db.session.get(InventoryItem, item_id)
        assert record_purchase_receipt_movements(order) is True
        db.session.commit()
        db.session.refresh(item)
        assert item.current_qty == 5
        mv_count = StockMovement.query.filter_by(item_id=item_id).count()
        assert mv_count == 1
        assert record_purchase_receipt_movements(order) is False


def test_inventory_item_card_page(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item = _item()
        db.session.commit()
        item_id = item.id

    r = client.get(f'/inventory/item/{item_id}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'كارت صنف' in html or item.code in html
    assert 'حركة الصنف' in html


def test_stock_add_blocks_over_issue(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item = _item(qty=1)
        db.session.commit()
        item_id = item.id

    r = client.post('/stock-movements/add', data={
        'item_id': item_id,
        'quantity': 3,
        'direction': 'صادر',
        'movement_type': 'صرف لفني',
        'movement_date': date.today().isoformat(),
        'unit_price': 5,
    }, follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        item = db.session.get(InventoryItem, item_id)
        assert float(item.current_qty or 0) == 1


def test_warehouse_department_pages(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    for path, needle in (
        ('/warehouse/opening', 'رصيد أول المدة'),
        ('/warehouse/issue', 'إذن صرف'),
        ('/warehouse/purchases', 'المشتريات'),
        ('/inventory', 'الأصناف'),
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        assert needle in r.get_data(as_text=True), path
