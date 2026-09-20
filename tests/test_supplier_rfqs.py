"""طلبات عرض السعر من الموردين — الصفحة والحفظ والطباعة."""
from models import SupplierQuoteRequest
from tests.conftest import login_as


def test_supplier_rfq_routes_registered():
    from app import app

    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert 'supplier_rfqs' in endpoints
    assert 'supplier_rfqs_save' in endpoints
    assert 'supplier_rfq_print' in endpoints


def test_supplier_rfq_page_loads(client):
    login_as(client, role='admin')
    r = client.get('/supplier-rfqs')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'طلب عرض سعر من مورد' in body
    assert 'rfq-form' in body
    assert 'ابحث بالكود أو اسم الصنف' in body


def test_supplier_rfq_save_and_print(client):
    from models import InventoryItem, db

    login_as(client, role='admin')
    with client.application.app_context():
        item = InventoryItem(code='RFQ-T01', name='ماكينة جيرلس', category='تركيب', unit='قطعة')
        db.session.add(item)
        db.session.commit()
        item_id = item.id
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'
    r = client.post(
        '/supplier-rfqs/save',
        data={
            'csrf_token': 'test-csrf',
            'supplier': 'مورد الاختبار',
            'supplier_phone': '0566299626',
            'status': 'مسودة',
            'subject': 'تسعير ماكينة',
            'description': 'ماكينة جيرلس',
            'item_id': str(item_id),
            'quantity': '1',
            'unit': 'قطعة',
            'specs': '1000 كجم',
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    loc = r.headers.get('Location') or ''
    assert '/supplier-rfqs/' in loc
    assert '/print' in loc

    with client.application.app_context():
        rfq = SupplierQuoteRequest.query.order_by(SupplierQuoteRequest.id.desc()).first()
        assert rfq is not None
        assert rfq.supplier == 'مورد الاختبار'
        assert len(rfq.lines) == 1
        assert rfq.lines[0].description == 'ماكينة جيرلس'
        assert rfq.lines[0].item_id == item_id
        rfq_id = rfq.id

    pr = client.get(f'/supplier-rfqs/{rfq_id}/print')
    assert pr.status_code == 200
    body = pr.get_data(as_text=True)
    assert 'طلب عرض سعر' in body
    assert 'ماكينة جيرلس' in body
    assert 'مورد الاختبار' in body
