"""مرحلة 1 — مخزن: رصيد افتتاحي، صرف، PO حركة، كارت صنف."""
from datetime import date

from inventory_warehouse import (
    MOVEMENT_OPENING,
    MOVEMENT_PURCHASE,
    record_issue_authorization,
    record_opening_stock,
    record_opening_stock_batch,
    record_purchase_invoice_batch,
    validate_outbound_stock,
)
from models import InventoryItem, StockMovement, db


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
        assert 'OS-' in (m.reason or '')
        assert (m.reference or '').startswith('opening:OS-')


def test_opening_stock_batch_single_document(client):
    with client.application.app_context():
        item1 = _item(code='#WH-B1', qty=0)
        item2 = _item(code='#WH-B2', qty=0)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    with client.application.app_context():
        doc_code, movements = record_opening_stock_batch(
            lines=[
                {'item_id': id1, 'quantity': 3, 'unit_price': 4, 'invoice_no': 'INV-100'},
                {'item_id': id2, 'quantity': 5, 'unit_price': 2, 'invoice_no': 'INV-200'},
            ],
        )
        db.session.commit()
        assert doc_code.startswith('OS-')
        assert len(movements) == 2
        refs = {(m.reference or '') for m in movements}
        assert len(refs) == 2
        assert all(r.startswith(f'opening:{doc_code}:item:') for r in refs)
        assert any(':inv:INV-100' in r for r in refs)
        assert any(':inv:INV-200' in r for r in refs)
        item1 = db.session.get(InventoryItem, id1)
        item2 = db.session.get(InventoryItem, id2)
        assert float(item1.current_qty or 0) == 3
        assert float(item2.current_qty or 0) == 5


def test_opening_stock_batch_rejects_duplicate_item(client):
    with client.application.app_context():
        item = _item(qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        with __import__('pytest').raises(ValueError, match='مكرر'):
            record_opening_stock_batch(
                lines=[
                    {'item_id': item_id, 'quantity': 1},
                    {'item_id': item_id, 'quantity': 2},
                ],
            )


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


def test_purchase_invoice_batch_single_document(client):
    with client.application.app_context():
        item1 = _item(code='#WH-PUR1', qty=0)
        item2 = _item(code='#WH-PUR2', qty=0)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    with client.application.app_context():
        doc_code, movements = record_purchase_invoice_batch(
            invoice_no='SUP-INV-100',
            supplier='مورد تجريبي',
            lines=[
                {'item_id': id1, 'quantity': 3, 'unit_price': 10},
                {'item_id': id2, 'quantity': 2, 'unit_price': 5},
            ],
        )
        db.session.commit()
        assert doc_code.startswith('PI-')
        assert len(movements) == 2
        assert all(m.movement_type == MOVEMENT_PURCHASE for m in movements)
        assert all('SUP-INV-100' in (m.reason or '') for m in movements)
        item1 = db.session.get(InventoryItem, id1)
        item2 = db.session.get(InventoryItem, id2)
        assert float(item1.current_qty or 0) == 3
        assert float(item2.current_qty or 0) == 2


def test_purchase_invoice_rejects_duplicate_invoice_no(client):
    with client.application.app_context():
        item = _item(code='#WH-PUR3', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        record_purchase_invoice_batch(
            invoice_no='DUP-1',
            lines=[{'item_id': item_id, 'quantity': 1, 'unit_price': 1}],
        )
        db.session.commit()

    with client.application.app_context():
        with __import__('pytest').raises(ValueError, match='مسجّلة'):
            record_purchase_invoice_batch(
                invoice_no='DUP-1',
                lines=[{'item_id': item_id, 'quantity': 2, 'unit_price': 1}],
            )


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
        ('/warehouse/opening', 'ابحث بالكود أو اسم الصنف'),
        ('/warehouse/issue', 'إذن صرف'),
        ('/warehouse/purchases', 'إدخال فاتورة شراء'),
        ('/inventory', 'الأصناف'),
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        assert needle in r.get_data(as_text=True), path


def test_opening_stock_post_batch(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item1 = _item(code='#WH-P1', qty=0)
        item2 = _item(code='#WH-P2', qty=0)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    r = client.post('/inventory/opening-stock', data={
        'movement_date': date.today().isoformat(),
        'notes': 'افتتاحي مجمّع',
        'item_id': [str(id1), str(id2)],
        'quantity': ['2', '4'],
        'unit_price': ['10', '5'],
        'invoice_no': ['FAT-1', 'FAT-2'],
    }, follow_redirects=True)
    assert r.status_code == 200
    assert 'OS-' in r.get_data(as_text=True)
    with client.application.app_context():
        item1 = db.session.get(InventoryItem, id1)
        item2 = db.session.get(InventoryItem, id2)
        assert float(item1.current_qty or 0) == 2
        assert float(item2.current_qty or 0) == 4
        assert StockMovement.query.filter_by(item_id=id1).count() == 1


def test_purchase_invoice_post(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item1 = _item(code='#WH-PI1', qty=0)
        item2 = _item(code='#WH-PI2', qty=0)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    r = client.post('/inventory/purchase-invoice', data={
        'movement_date': date.today().isoformat(),
        'invoice_no': 'VENDOR-555',
        'supplier': 'مورد أ',
        'notes': 'فاتورة تجريبية',
        'item_id': [str(id1), str(id2)],
        'quantity': ['3', '1'],
        'unit_price': ['20', '15'],
    }, follow_redirects=True)
    assert r.status_code == 200
    assert 'PI-' in r.get_data(as_text=True)
    assert 'VENDOR-555' in r.get_data(as_text=True)
    with client.application.app_context():
        item1 = db.session.get(InventoryItem, id1)
        item2 = db.session.get(InventoryItem, id2)
        assert float(item1.current_qty or 0) == 3
        assert float(item2.current_qty or 0) == 1
