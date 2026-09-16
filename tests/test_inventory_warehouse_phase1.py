"""مرحلة 1 — مخزن: رصيد افتتاحي، صرف، PO حركة، كارت صنف."""
from datetime import date

from inventory_warehouse import (
    MOVEMENT_OPENING,
    MOVEMENT_PURCHASE,
    DEFAULT_PURCHASE_TAX_PCT,
    issue_document_for_edit,
    issue_documents,
    issue_print_payload,
    parse_issue_user_notes,
    parse_stock_movement_user_notes,
    purchase_invoice_for_edit,
    record_issue_authorization,
    record_issue_batch,
    opening_document_for_edit,
    opening_print_payload,
    record_opening_stock,
    record_opening_stock_batch,
    record_purchase_invoice_batch,
    update_issue_batch,
    update_opening_batch,
    update_purchase_invoice_batch,
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


def test_purchase_invoice_applies_approx_discount(client):
    with client.application.app_context():
        item1 = _item(code='#WH-D1', qty=0)
        item2 = _item(code='#WH-D2', qty=0)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    with client.application.app_context():
        doc_code, movements = record_purchase_invoice_batch(
            invoice_no='DISC-100',
            discount_approx=10,
            lines=[
                {'item_id': id1, 'quantity': 2, 'unit_price': 10},
                {'item_id': id2, 'quantity': 1, 'unit_price': 20},
            ],
        )
        db.session.commit()
        assert doc_code.startswith('PI-')
        total_value = round(sum(float(m.total_value or 0) for m in movements), 2)
        assert total_value == 30.0
        assert 'خصم: 10.00' in (movements[0].reason or '')
        item1 = db.session.get(InventoryItem, id1)
        assert float(item1.buy_price or 0) == 7.5


def test_purchase_invoice_rejects_discount_over_gross(client):
    with client.application.app_context():
        item = _item(code='#WH-D3', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        with __import__('pytest').raises(ValueError, match='أكبر'):
            record_purchase_invoice_batch(
                invoice_no='DISC-BAD',
                discount_approx=100,
                lines=[{'item_id': item_id, 'quantity': 1, 'unit_price': 10}],
            )


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


def test_issue_batch_single_document(client):
    with client.application.app_context():
        item1 = _item(code='#WH-I1', qty=10)
        item2 = _item(code='#WH-I2', qty=8)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    with client.application.app_context():
        doc_code, movements = record_issue_batch(
            target='consumable',
            lines=[
                {'item_id': id1, 'quantity': 2},
                {'item_id': id2, 'quantity': 3},
            ],
        )
        db.session.commit()
        assert doc_code.startswith('IS-')
        assert len(movements) == 2
        refs = {(m.reference or '') for m in movements}
        assert all(r.startswith(f'issue:{doc_code}:item:') for r in refs)
        item1 = db.session.get(InventoryItem, id1)
        item2 = db.session.get(InventoryItem, id2)
        assert float(item1.current_qty or 0) == 8
        assert float(item2.current_qty or 0) == 5


def test_issue_post_batch(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item1 = _item(code='#WH-IP1', qty=6)
        item2 = _item(code='#WH-IP2', qty=4)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    r = client.post('/inventory/issue', data={
        'batch': '1',
        'movement_date': date.today().isoformat(),
        'target': 'consumable',
        'notes': 'صرف مجمّع',
        'item_id': [str(id1), str(id2)],
        'quantity': ['2', '1'],
    }, follow_redirects=True)
    assert r.status_code == 200
    assert 'IS-' in r.get_data(as_text=True)
    with client.application.app_context():
        item1 = db.session.get(InventoryItem, id1)
        item2 = db.session.get(InventoryItem, id2)
        assert float(item1.current_qty or 0) == 4
        assert float(item2.current_qty or 0) == 3


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
        ('/warehouse/issue', 'إذن صرف بضاعة'),
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


def test_opening_stock_update(client):
    with client.application.app_context():
        item1 = _item(code='#WH-OSU1', qty=0)
        item2 = _item(code='#WH-OSU2', qty=0)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    with client.application.app_context():
        doc_code, _ = record_opening_stock_batch(
            notes='افتتاحي',
            lines=[
                {'item_id': id1, 'quantity': 2, 'unit_price': 10, 'invoice_no': 'INV-A'},
            ],
        )
        db.session.commit()

    with client.application.app_context():
        update_opening_batch(
            doc_code,
            notes='محدّث',
            lines=[
                {'item_id': id1, 'quantity': 5, 'unit_price': 12, 'invoice_no': 'INV-A'},
                {'item_id': id2, 'quantity': 1, 'unit_price': 8, 'invoice_no': 'INV-B'},
            ],
        )
        db.session.commit()
        item1 = db.session.get(InventoryItem, id1)
        item2 = db.session.get(InventoryItem, id2)
        assert float(item1.current_qty or 0) == 5
        assert float(item2.current_qty or 0) == 1
        edit = opening_document_for_edit(doc_code)
        assert edit is not None
        assert edit['notes'] == 'محدّث'
        assert len(edit['lines']) == 2


def test_opening_stock_edit_post(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item = _item(code='#WH-OSEDIT', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_opening_stock_batch(
            lines=[{'item_id': item_id, 'quantity': 1, 'unit_price': 5}],
        )
        db.session.commit()

    r = client.post('/inventory/opening-stock', data={
        'edit_doc_code': doc_code,
        'movement_date': date.today().isoformat(),
        'notes': 'بعد التعديل',
        'item_id': [str(item_id)],
        'quantity': ['4'],
        'unit_price': ['7.25'],
        'invoice_no': ['FAT-99'],
    }, follow_redirects=True)
    assert r.status_code == 200
    assert 'تحديث' in r.get_data(as_text=True)
    with client.application.app_context():
        item = db.session.get(InventoryItem, item_id)
        assert float(item.current_qty or 0) == 4


def test_opening_print_payload(client):
    with client.application.app_context():
        item = _item(code='#WH-OSPR', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_opening_stock_batch(
            lines=[{'item_id': item_id, 'quantity': 3, 'unit_price': 10, 'invoice_no': 'OS-INV'}],
        )
        db.session.commit()
        payload = opening_print_payload(doc_code)
        assert payload is not None
        assert payload['doc_code'] == doc_code
        assert payload['line_count'] == 1
        assert payload['invoice_summary'] == 'OS-INV'


def test_opening_print_route(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item = _item(code='#WH-OSPRT', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_opening_stock_batch(
            lines=[{'item_id': item_id, 'quantity': 2, 'unit_price': 5}],
        )
        db.session.commit()

    r = client.get(f'/warehouse/opening/print/{doc_code}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert doc_code in html
    assert 'مستند رصيد أول المدة' in html


def test_opening_view_route(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item = _item(code='#WH-OSVIEW', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_opening_stock_batch(
            lines=[{'item_id': item_id, 'quantity': 2, 'unit_price': 5, 'invoice_no': 'V-1'}],
        )
        db.session.commit()

    r = client.get(f'/warehouse/opening?view={doc_code}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert f'عرض مستند {doc_code}' in html
    assert 'V-1' in html


def test_opening_edit_requires_admin(client):
    from tests.conftest import login_as

    with client.application.app_context():
        item = _item(code='#WH-OSADM', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_opening_stock_batch(
            lines=[{'item_id': item_id, 'quantity': 1, 'unit_price': 5}],
        )
        db.session.commit()

    login_as(client, 'viewer')
    r = client.get(f'/warehouse/opening?edit={doc_code}', follow_redirects=True)
    assert r.status_code == 200
    assert 'مدير النظام' in r.get_data(as_text=True)

    login_as(client, 'admin')
    r = client.get(f'/warehouse/opening?edit={doc_code}')
    assert r.status_code == 200
    assert 'تعديل مستند' in r.get_data(as_text=True)


def test_opening_delete_requires_admin(client):
    from tests.conftest import login_as

    with client.application.app_context():
        item = _item(code='#WH-OSDEL', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_opening_stock_batch(
            lines=[{'item_id': item_id, 'quantity': 2, 'unit_price': 5}],
        )
        db.session.commit()

    login_as(client, 'viewer')
    r = client.post(
        f'/inventory/opening-stock/delete/{doc_code}',
        json={'admin_password': 'wrong'},
        headers={'X-LC-Admin-Delete': '1'},
    )
    assert r.status_code in (403, 401)

    with client.application.app_context():
        item = db.session.get(InventoryItem, item_id)
        assert float(item.current_qty or 0) == 2


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


def test_purchase_invoice_high_precision_price(client):
    with client.application.app_context():
        item = _item(code='#WH-PREC', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, movements = record_purchase_invoice_batch(
            invoice_no='PREC-1',
            lines=[{'item_id': item_id, 'quantity': 3, 'unit_price': 10.123456}],
        )
        db.session.commit()
        assert len(movements) == 1
        assert float(movements[0].unit_price or 0) == 10.123456
        item = db.session.get(InventoryItem, item_id)
        assert float(item.buy_price or 0) == 10.123456


def test_purchase_invoice_update(client):
    with client.application.app_context():
        item1 = _item(code='#WH-ED1', qty=0)
        item2 = _item(code='#WH-ED2', qty=0)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    with client.application.app_context():
        doc_code, _ = record_purchase_invoice_batch(
            invoice_no='EDIT-INV',
            supplier='مورد 1',
            lines=[{'item_id': id1, 'quantity': 2, 'unit_price': 10}],
        )
        db.session.commit()

    with client.application.app_context():
        update_purchase_invoice_batch(
            doc_code,
            invoice_no='EDIT-INV',
            supplier='مورد 2',
            lines=[
                {'item_id': id1, 'quantity': 5, 'unit_price': 12},
                {'item_id': id2, 'quantity': 1, 'unit_price': 8},
            ],
        )
        db.session.commit()
        item1 = db.session.get(InventoryItem, id1)
        item2 = db.session.get(InventoryItem, id2)
        assert float(item1.current_qty or 0) == 5
        assert float(item2.current_qty or 0) == 1
        edit = purchase_invoice_for_edit(doc_code)
        assert edit is not None
        assert edit['supplier'] == 'مورد 2'
        assert len(edit['lines']) == 2
        assert edit['tax_pct'] == DEFAULT_PURCHASE_TAX_PCT


def test_purchase_invoice_edit_post(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item = _item(code='#WH-EDITPOST', qty=0)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_purchase_invoice_batch(
            invoice_no='POST-EDIT',
            lines=[{'item_id': item_id, 'quantity': 1, 'unit_price': 5}],
        )
        db.session.commit()

    r = client.post('/inventory/purchase-invoice', data={
        'edit_doc_code': doc_code,
        'movement_date': date.today().isoformat(),
        'invoice_no': 'POST-EDIT',
        'supplier': 'مورد',
        'item_id': [str(item_id)],
        'quantity': ['4'],
        'unit_price': ['7.25'],
    }, follow_redirects=True)
    assert r.status_code == 200
    assert 'تحديث' in r.get_data(as_text=True)
    with client.application.app_context():
        item = db.session.get(InventoryItem, item_id)
        assert float(item.current_qty or 0) == 4


def test_issue_batch_update(client):
    with client.application.app_context():
        item1 = _item(code='#WH-IU1', qty=10)
        item2 = _item(code='#WH-IU2', qty=8)
        db.session.commit()
        id1, id2 = item1.id, item2.id

    with client.application.app_context():
        doc_code, _ = record_issue_batch(
            target='consumable',
            lines=[{'item_id': id1, 'quantity': 2}],
        )
        db.session.commit()

    with client.application.app_context():
        update_issue_batch(
            doc_code,
            target='consumable',
            lines=[
                {'item_id': id1, 'quantity': 3},
                {'item_id': id2, 'quantity': 1},
            ],
        )
        db.session.commit()
        item1 = db.session.get(InventoryItem, id1)
        item2 = db.session.get(InventoryItem, id2)
        assert float(item1.current_qty or 0) == 7
        assert float(item2.current_qty or 0) == 7
        edit = issue_document_for_edit(doc_code)
        assert edit is not None
        assert len(edit['lines']) == 2


def test_issue_print_payload(client):
    with client.application.app_context():
        item = _item(code='#WH-IPR', qty=5)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_issue_batch(
            target='consumable',
            lines=[{'item_id': item_id, 'quantity': 2}],
        )
        db.session.commit()
        payload = issue_print_payload(doc_code)
        assert payload is not None
        assert payload['doc_code'] == doc_code
        assert payload['line_count'] == 1


def test_issue_edit_requires_admin(client):
    from tests.conftest import login_as

    with client.application.app_context():
        item = _item(code='#WH-ADM', qty=4)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_issue_batch(
            target='consumable',
            lines=[{'item_id': item_id, 'quantity': 1}],
        )
        db.session.commit()

    login_as(client, 'viewer')
    r = client.get(f'/warehouse/issue?edit={doc_code}', follow_redirects=True)
    assert r.status_code == 200
    assert 'مدير النظام' in r.get_data(as_text=True)

    login_as(client, 'admin')
    r = client.get(f'/warehouse/issue?edit={doc_code}')
    assert r.status_code == 200
    assert 'تعديل إذن صرف' in r.get_data(as_text=True)


def test_issue_print_route(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item = _item(code='#WH-PRT', qty=3)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, _ = record_issue_batch(
            target='consumable',
            lines=[{'item_id': item_id, 'quantity': 1}],
        )
        db.session.commit()

    r = client.get(f'/warehouse/issue/print/{doc_code}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert doc_code in html
    assert 'إذن صرف بضاعة' in html


def test_issue_notes_hide_internal_meta(client):
    with client.application.app_context():
        item = _item(code='#WH-NMETA', qty=5)
        db.session.commit()
        item_id = item.id

    with client.application.app_context():
        doc_code, movements = record_issue_batch(
            target='consumable',
            notes='',
            lines=[{'item_id': item_id, 'quantity': 1}],
        )
        db.session.commit()
        stored = movements[0].notes or ''
        assert '---LC-IS-META---' in stored
        assert parse_issue_user_notes(stored) == ''
        docs = issue_documents()
        row = next(d for d in docs if d['code'] == doc_code)
        assert row['notes'] == ''
        assert 'LC-IS-META' not in (row['notes'] or '')

    # سجلات قديمة أُفسدت بسبب strip سابق
    legacy = '---LC-IS-META---\n{"target": "custody", "technician_id": 15}'
    assert parse_issue_user_notes(legacy) == ''
    assert parse_issue_user_notes(f'ملاحظة{legacy}') == 'ملاحظة'


def test_stock_movement_notes_hide_internal_meta():
    legacy = '---LC-IS-META---\n{"target": "custody", "technician_id": 16}'
    assert parse_stock_movement_user_notes(legacy, 'issue:IS-0015:item:42') == ''
    assert parse_stock_movement_user_notes(legacy) == ''
    assert parse_stock_movement_user_notes('ملاحظة عامة') == 'ملاحظة عامة'
