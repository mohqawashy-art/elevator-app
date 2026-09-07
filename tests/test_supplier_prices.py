"""الموردون وقائمة الأسعار — اختبارات."""
from models import InventoryItem, Supplier, SupplierPrice
from tests.conftest import login_as


def test_suppliers_page(client):
    login_as(client, role='admin')
    r = client.get('/suppliers')
    assert r.status_code == 200
    assert 'الموردون' in r.get_data(as_text=True)


def test_supplier_create_and_edit(client):
    login_as(client, role='admin')
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    r = client.post(
        '/suppliers/save',
        data={
            'csrf_token': 'test-csrf',
            'name': 'مورد اختبار LiftCore',
            'phone': '0501112233',
            'email': 'test-supplier@example.com',
            'active': '1',
            'notes': 'ملاحظة',
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with client.application.app_context():
        sup = Supplier.query.filter_by(name='مورد اختبار LiftCore').first()
        assert sup is not None
        assert sup.phone == '0501112233'
        sup_id = sup.id

    api = client.get('/api/suppliers')
    assert api.status_code == 200
    data = api.get_json()
    assert data['ok'] is True
    assert any(s['id'] == sup_id for s in data['suppliers'])

    r2 = client.post(
        '/suppliers/save',
        data={
            'csrf_token': 'test-csrf',
            'supplier_id': str(sup_id),
            'name': 'مورد اختبار LiftCore',
            'phone': '0509998877',
            'email': 'test-supplier@example.com',
            'active': '1',
        },
        follow_redirects=True,
    )
    assert r2.status_code == 200

    with client.application.app_context():
        sup = Supplier.query.get(sup_id)
        assert sup.phone == '0509998877'


def test_supplier_price_list_page(client):
    login_as(client, role='admin')
    r = client.get('/supplier-price-list')
    assert r.status_code == 200
    assert 'قائمة أسعار الموردين' in r.get_data(as_text=True)


def test_supplier_price_save_and_lookup(client):
    login_as(client, role='admin')
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    with client.application.app_context():
        item = InventoryItem.query.filter_by(code='#001').first()
        if not item:
            item = InventoryItem(code='#001', name='بند اختبار', buy_price=10, sell_price=15)
            from tenant_scope import assign_organization
            assign_organization(item)
            from models import db
            db.session.add(item)
            db.session.commit()
        item_id = item.id

        sup = Supplier.query.filter_by(name='مورد قائمة الأسعار').first()
        if not sup:
            sup = Supplier(name='مورد قائمة الأسعار', phone='0500000001', active=True)
            from tenant_scope import assign_organization
            assign_organization(sup)
            from models import db
            db.session.add(sup)
            db.session.commit()
        supplier_id = sup.id

    r = client.post(
        '/supplier-price-list/save',
        data={
            'csrf_token': 'test-csrf',
            'supplier_id': str(supplier_id),
            'item_id': str(item_id),
            'unit_price': '250.5',
            'lead_days': '7',
            'price_notes': 'اختبار',
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with client.application.app_context():
        price = SupplierPrice.query.filter_by(supplier_id=supplier_id, item_id=item_id).first()
        assert price is not None
        assert float(price.unit_price) == 250.5
        item = InventoryItem.query.get(item_id)
        assert float(item.buy_price) == 250.5

    api = client.get(f'/api/supplier-prices/lookup?supplier_id={supplier_id}&item_id={item_id}')
    assert api.status_code == 200
    data = api.get_json()
    assert data['ok'] is True
    assert float(data['unit_price']) == 250.5
