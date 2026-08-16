"""حفظ دبوس خريطة العقد على العميل حتى لا يبقى على إحداثيات الحرم."""
from datetime import date, timedelta

from app import db
from models import Contract, Customer

from tests.conftest import ensure_test_organization, login_as


def test_contract_edit_saves_customer_map_pin(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(
            organization_id=oid,
            code='C-MAP1',
            name='عميل خريطة',
            status='نشط',
            city='مكة',
            lat='21.4225',
            lng='39.8262',
        )
        db.session.add(cust)
        db.session.flush()
        c = Contract(
            organization_id=oid,
            code='CN-00098',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            duration_months=12,
            value=1000,
            tax_pct=15,
            tax_amount=150,
            total=1150,
            status='نشط',
            city='مكة',
            address='حي العوالي',
        )
        db.session.add(c)
        db.session.commit()
        cid, cust_id = c.id, cust.id

    r = client.post(
        f'/contracts/edit/{cid}',
        data={
            'customer_id': str(cust_id),
            'contract_type': 'عقد صيانة',
            'start_date': date.today().isoformat(),
            'end_date': (date.today() + timedelta(days=365)).isoformat(),
            'maint_frequency': 'شهري',
            'visits_per_month': '1',
            'value': '1000',
            'tax_pct': '15',
            'total': '1150',
            'payment_terms': 'دفعة واحدة',
            'status': 'نشط',
            'city': 'مكة',
            'address': 'حي العوالي',
            'lat': '21.3890',
            'lng': '39.8570',
            'maps_url': 'https://www.google.com/maps?q=21.3890,39.8570',
        },
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302)

    with client.application.app_context():
        saved = db.session.get(Customer, cust_id)
        assert saved.lat == '21.389'
        assert saved.lng == '39.857'
        assert '21.389' in (saved.maps_url or '')


def test_contract_edit_ignores_haram_default_pin(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(
            organization_id=oid,
            code='C-MAP2',
            name='عميل حرم',
            status='نشط',
            lat='21.4',
            lng='39.8',
        )
        db.session.add(cust)
        db.session.flush()
        c = Contract(
            organization_id=oid,
            code='CN-MAP2',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            status='نشط',
            value=0,
            tax_pct=15,
            tax_amount=0,
            total=0,
        )
        db.session.add(c)
        db.session.commit()
        cid, cust_id = c.id, cust.id

    r = client.post(
        f'/contracts/edit/{cid}',
        data={
            'customer_id': str(cust_id),
            'contract_type': 'عقد صيانة',
            'start_date': date.today().isoformat(),
            'end_date': (date.today() + timedelta(days=365)).isoformat(),
            'value': '0',
            'tax_pct': '15',
            'total': '0',
            'status': 'نشط',
            'lat': '21.4225',
            'lng': '39.8262',
        },
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302)
    with client.application.app_context():
        saved = db.session.get(Customer, cust_id)
        assert saved.lat == '21.4'
        assert saved.lng == '39.8'
