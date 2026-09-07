"""قائمة أسعار الموردين — اختبارات."""
from models import InventoryItem, Supplier, SupplierPrice
from tests.conftest import login_as


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

    r = client.post(
        '/supplier-price-list/save',
        data={
            'csrf_token': 'test-csrf',
            'supplier_name': 'مورد قائمة الأسعار',
            'supplier_phone': '0500000001',
            'item_id': str(item_id),
            'unit_price': '250.5',
            'lead_days': '7',
            'price_notes': 'اختبار',
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with client.application.app_context():
        sup = Supplier.query.filter_by(name='مورد قائمة الأسعار').first()
        assert sup is not None
        price = SupplierPrice.query.filter_by(supplier_id=sup.id, item_id=item_id).first()
        assert price is not None
        assert float(price.unit_price) == 250.5
        item = InventoryItem.query.get(item_id)
        assert float(item.buy_price) == 250.5

    api = client.get(f'/api/supplier-prices/lookup?supplier_id={sup.id}&item_id={item_id}')
    assert api.status_code == 200
    data = api.get_json()
    assert data['ok'] is True
    assert float(data['unit_price']) == 250.5
