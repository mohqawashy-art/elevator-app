"""استيراد عقد بمبلغ مسدد 0 يُحفظ غير مدفوع حتى لو العقد موجود مسبقاً."""
from datetime import date, timedelta

from app import db
from models import Contract, Customer

from tests.conftest import ensure_test_organization, login_as


def _payload(customer_id, *, code='CN-88001', paid='0'):
    start = date.today()
    end = start + timedelta(days=365)
    data = {
        'customer_id': str(customer_id),
        'code': code,
        'contract_type': 'عقد صيانة',
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
        'maint_frequency': 'سنوي',
        'visits_per_month': '1',
        'value': '1800',
        'tax_pct': '15',
        'total': '2070',
        'payment_terms': 'دفعة واحدة',
        'status': 'نشط',
        'paid_amount': paid,
    }
    return data


def _headers():
    return {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}


def test_import_paid_zero_marks_unpaid(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-8801', name='عميل استيراد', status='نشط')
        db.session.add(cust)
        db.session.commit()
        cid = cust.id
    r = client.post('/contracts/add', data=_payload(cid, paid='0'), headers=_headers())
    assert r.status_code == 200
    with client.application.app_context():
        c = Contract.query.filter_by(code='CN-88001').first()
        assert c is not None
        assert (c.paid_amount or 0) == 0
        assert c.invoice_status == 'غير مدفوع'


def test_reimport_paid_zero_overwrites_existing_paid(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-8802', name='عميل إعادة استيراد', status='نشط')
        db.session.add(cust)
        db.session.flush()
        c = Contract(
            organization_id=oid,
            code='CN-88002',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            value=1800,
            tax_pct=15,
            tax_amount=270,
            total=2070,
            paid_amount=1800,
            invoice_status='مدفوع',
            status='نشط',
        )
        db.session.add(c)
        db.session.commit()
        cid = cust.id
    r = client.post(
        '/contracts/add',
        data=_payload(cid, code='CN-88002', paid='0'),
        headers=_headers(),
    )
    assert r.status_code == 200
    with client.application.app_context():
        c = Contract.query.filter_by(code='CN-88002').first()
        assert (c.paid_amount or 0) == 0
        assert c.invoice_status == 'غير مدفوع'
