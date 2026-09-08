"""عقود الصيانة — منفصلة عن التركيب."""
from datetime import date, timedelta

from contract_codes import CONTRACT_PREFIX_INSTALLATION
from models import Contract, Customer, Organization, db
from tests.conftest import login_as


def test_contracts_page_excludes_installation_contracts(client):
    login_as(client, role='admin')
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-MSCOPE',
            name='عميل نطاق',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        install = Contract(
            organization_id=org.id,
            code=f'{CONTRACT_PREFIX_INSTALLATION}88888',
            customer_id=cust.id,
            contract_type='عقد تركيب',
            status='نشط',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
        )
        maint = Contract(
            organization_id=org.id,
            code='CN-88887',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            status='نشط',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
        )
        db.session.add_all([install, maint])
        db.session.commit()

    resp = client.get('/contracts?scope=maintenance&z=4')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'CN-88887' in body
    assert 'CI-88888' not in body


def test_contract_add_rejects_installation_type(client):
    login_as(client, role='admin')
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-MSCOPE2',
            name='عميل رفض',
            status='نشط',
        )
        db.session.add(cust)
        db.session.commit()
        cid = cust.id

    resp = client.post(
        '/contracts/add',
        data={
            'customer_id': str(cid),
            'contract_type': 'عقد تركيب',
            'start_date': '2026-01-01',
            'end_date': '2027-01-01',
            'value': '10000',
            'tax_pct': '15',
            'total': '11500',
            'status': 'نشط',
        },
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data and data.get('ok') is False
    assert 'التركيب' in (data.get('message') or '')


def test_contracts_installation_scope_redirects(client):
    login_as(client, role='admin')
    resp = client.get('/contracts?scope=installation&z=4', follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert '/installation/contracts' in (resp.location or '')
