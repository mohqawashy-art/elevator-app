"""ربط بنود عرض التركيب بأصناف المخزن."""
from installation.models import InstallProject, InstallQuotation, InstallQuotationLine
from models import Customer, InventoryItem, Organization, db
from tests.conftest import login_as


def test_quote_save_stores_inventory_item_id_and_price(client):
    login_as(client, role='admin')
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-INVQ',
            name='عميل تسعير مخزن',
            status='نشط',
        )
        item = InventoryItem(
            organization_id=org.id,
            code='SP-100',
            name='سكة دليل',
            unit='متر',
            buy_price=40,
            sell_price=75,
        )
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-INVQ',
            title='مشروع تسعير مخزن',
            status='تسعير',
            customer_id=None,
        )
        db.session.add_all([cust, item, project])
        db.session.commit()
        pid, cid, iid = project.id, cust.id, item.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        f'/installation/projects/{pid}/quote/save',
        json={
            'csrf_token': 'test-csrf',
            'customer_id': cid,
            'quote_type': 'new',
            'valid_days': 30,
            'labor': 0,
            'transport': 0,
            'other_costs': 0,
            'profit_pct': 0,
            'pay_count': 3,
            'pay_installments': [
                {'label': 'مقدمة', 'pct': 50},
                {'label': 'توريد', 'pct': 40},
                {'label': 'نهائية', 'pct': 10},
            ],
            'spec': {},
            'lines': [{
                'stage': 'مرحلة 1 — سكك وأبواب',
                'name': 'سكة دليل',
                'unit': 'متر',
                'qty': 10,
                'price': 75,
                'item_id': iid,
            }],
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data and data.get('ok')

    with client.application.app_context():
        q = InstallQuotation.query.filter_by(project_id=pid).first()
        assert q is not None
        line = InstallQuotationLine.query.filter_by(quotation_id=q.id).one()
        assert line.item_id == iid
        assert line.qty == 10
        assert line.unit_price == 75
        assert line.line_total == 750
