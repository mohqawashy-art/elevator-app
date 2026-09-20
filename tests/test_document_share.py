"""روابط عامة للمستندات — بدون تسجيل دخول."""
from models import InventoryItem, SupplierQuoteRequest, db
from tests.conftest import login_as


def test_public_rfq_document_no_login(client):
    login_as(client, role='admin')
    with client.application.app_context():
        item = InventoryItem.query.filter_by(code='PUB-RFQ-01').first()
        if not item:
            item = InventoryItem(code='PUB-RFQ-01', name='صنف عام', category='عام', unit='قطعة')
            db.session.add(item)
            db.session.commit()
        item_id = item.id
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'
    r = client.post(
        '/supplier-rfqs/save',
        data={
            'csrf_token': 'test-csrf',
            'supplier': 'مورد عام',
            'status': 'مسودة',
            'description': 'صنف عام',
            'item_id': str(item_id),
            'quantity': '1',
            'unit': 'قطعة',
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    with client.application.app_context():
        rfq = SupplierQuoteRequest.query.order_by(SupplierQuoteRequest.id.desc()).first()
        assert rfq is not None
        code = rfq.code
        rfq_id = rfq.id
        oid = rfq.organization_id or 1
    from document_share import document_share_path

    path = document_share_path('rfq', rfq_id, oid)
    client.get('/logout', follow_redirects=True)
    pub = client.get(path)
    assert pub.status_code == 200
    body = pub.get_data(as_text=True)
    assert code in body


def test_public_rfq_invalid_token(client):
    r = client.get('/r/d/not-a-valid-token')
    assert r.status_code == 410
