"""حذف الأصناف — اختبارات."""
from models import InventoryItem, Supplier, SupplierPrice
from tests.conftest import login_as


def _ensure_item(app):
    with app.app_context():
        item = InventoryItem.query.filter_by(code='#DEL-TEST').first()
        if not item:
            item = InventoryItem(code='#DEL-TEST', name='صنف للحذف', buy_price=10, sell_price=15)
            from tenant_scope import assign_organization
            assign_organization(item)
            from models import db
            db.session.add(item)
            db.session.commit()
        return item.id


def test_inventory_delete_with_supplier_price(client):
    login_as(client, role='admin')
    app = client.application
    item_id = _ensure_item(app)

    with app.app_context():
        sup = Supplier.query.filter_by(name='مورد حذف صنف').first()
        if not sup:
            sup = Supplier(name='مورد حذف صنف', active=True)
            from tenant_scope import assign_organization
            assign_organization(sup)
            from models import db
            db.session.add(sup)
            db.session.commit()
        supplier_id = sup.id
        if not SupplierPrice.query.filter_by(supplier_id=supplier_id, item_id=item_id).first():
            row = SupplierPrice(supplier_id=supplier_id, item_id=item_id, unit_price=99)
            from tenant_scope import assign_organization
            assign_organization(row)
            from models import db
            db.session.add(row)
            db.session.commit()

    r = client.post(
        f'/inventory/delete/{item_id}',
        json={'admin_password': 'TestPass123!'},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 200
    assert r.get_json().get('ok') is True

    with app.app_context():
        assert InventoryItem.query.get(item_id) is None
        assert SupplierPrice.query.filter_by(item_id=item_id).count() == 0
