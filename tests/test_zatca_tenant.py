"""اختبارات زاتكا per-tenant — أسبوع 6."""
from datetime import date

import pytest

from app import app, db
from models import Organization, ZatcaCredentials
from tests.conftest import login_as


@pytest.fixture
def org_b():
    with app.app_context():
        o = Organization(slug='beta', name='Beta Co', status='active')
        db.session.add(o)
        db.session.commit()
        return o.id


def test_tax_invoice_blocked_without_zatca(client):
    with app.app_context():
        ZatcaCredentials.query.delete()
        db.session.commit()

    login_as(client, 'admin')
    r = client.post(
        '/invoices/add',
        data={
            'invoice_type': 'فاتورة ضريبية',
            'amount': '100',
            'invoice_date': date.today().isoformat(),
            'status': 'غير مدفوعة',
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert 'الفوترة الإلكترونية' in r.get_data(as_text=True)


def test_tax_invoice_allowed_with_active_zatca(client):
    login_as(client, 'admin')
    r = client.post(
        '/invoices/add',
        data={
            'invoice_type': 'فاتورة ضريبية',
            'amount': '100',
            'invoice_date': date.today().isoformat(),
            'status': 'غير مدفوعة',
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert 'الفوترة الإلكترونية' not in r.get_data(as_text=True)


def test_zatca_credentials_isolated_by_tenant(client, org_b):
    with app.app_context():
        db.session.add(ZatcaCredentials(
            organization_id=org_b,
            vat_number='399999999900003',
            status='active',
        ))
        db.session.commit()

    with app.test_request_context('/', base_url='https://beta.liftcoreapp.com'):
        from tenant_scope import resolve_tenant, tenant_query

        resolve_tenant()
        creds = tenant_query(ZatcaCredentials).filter_by(status='active').first()
        assert creds is not None
        assert creds.vat_number == '399999999900003'

    with app.test_request_context('/', base_url='https://app.liftcoreapp.com'):
        from tenant_scope import resolve_tenant, tenant_query

        resolve_tenant()
        creds = tenant_query(ZatcaCredentials).filter_by(status='active').first()
        assert creds is not None
        assert creds.vat_number == '300000000000003'
        assert creds.organization_id != org_b
