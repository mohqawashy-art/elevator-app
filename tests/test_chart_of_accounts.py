"""اختبارات شجرة الحسابات — المرحلة 1."""
from chart_of_accounts import (
    DEFAULT_CHART,
    ensure_chart_for_org,
    resolve_expense_account_id,
    resolve_revenue_account_id,
)
from models import Account, Organization, db


def test_ensure_chart_creates_default_accounts(client):
    with client.application.app_context():
        org = Organization(slug='coa-test', name='اختبار محاسبة', status='active')
        db.session.add(org)
        db.session.commit()
        added = ensure_chart_for_org(org.id)
        assert added == len(DEFAULT_CHART)
        count = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .count()
        )
        assert count == len(DEFAULT_CHART)
        # ثانية لا تكرر
        assert ensure_chart_for_org(org.id) == 0


def test_resolve_revenue_and_expense_map_keys(client):
    with client.application.app_context():
        org = Organization(slug='coa-map', name='اختبار ربط', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)

        from flask import g
        g.organization_id = org.id
        g.organization = org

        renew_id = resolve_revenue_account_id('تجديد عقد')
        acc = db.session.get(Account, renew_id)
        assert acc and acc.code == '4110'

        prior_id = resolve_revenue_account_id('عقد صيانة', 'تحصيل مالك سابق — قبل استلام جما')
        prior = db.session.get(Account, prior_id)
        assert prior and prior.code == '4900'

        fuel_id = resolve_expense_account_id('محروقات')
        fuel = db.session.get(Account, fuel_id)
        assert fuel and fuel.code == '5300'
