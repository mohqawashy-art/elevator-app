"""قيد افتتاحي متوازن، وربح العقد من الإيراد والمصروف المربوطين به."""
from datetime import date

from flask import g

from chart_of_accounts import ensure_chart_for_org
from customer_billing import build_ar_aging, build_customer_statement
from models import Account, Contract, Customer, Expense, Organization, Revenue, db
from opening_balances import contract_profit_report, post_opening_balance
from tests.conftest import login_as


def test_opening_journal_balances_and_ages_customer(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        g.organization_id = org.id
        g.organization = org
        ensure_chart_for_org(org.id)
        customer = Customer(
            code='C-OB1', name='عميل افتتاحي', phone='500111222',
            status='نشط', organization_id=org.id,
        )
        db.session.add(customer)
        db.session.commit()
        ar = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, map_key='ar'
        ).first()
        equity = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, code='3300'
        ).first()
        je = post_opening_balance(
            date(2026, 1, 1),
            [(ar.id, 400, 0, None), (equity.id, 0, 400, None)],
            [(customer.id, 400)],
            'قيد افتتاحي',
        )
        db.session.commit()
        assert je.source_type == 'opening'
        assert je.status == 'posted'
        stmt = build_customer_statement(customer.id)
        assert any(row['type'] == 'رصيد افتتاحي' and row['debit'] == 400 for row in stmt['debits'])
        aging = build_ar_aging(date(2026, 4, 15))
        row = next(r for r in aging['customers'] if r['customer'] == 'عميل افتتاحي')
        assert row['over'] == 400

    login_as(client, 'admin')
    page = client.get('/opening-balances')
    assert page.status_code == 200
    assert 'قيد افتتاحي' in page.get_data(as_text=True)


def test_contract_profit_uses_linked_expense(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        g.organization_id = org.id
        customer = Customer(
            code='C-CP1', name='عميل عقد', phone='500333444',
            status='نشط', organization_id=org.id,
        )
        db.session.add(customer)
        db.session.flush()
        contract = Contract(
            code='CN-CP1', customer_id=customer.id, contract_type='صيانة',
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            total=2000, status='نشط', organization_id=org.id,
        )
        db.session.add(contract)
        db.session.flush()
        db.session.add(Revenue(
            code='REV-CP1', customer_id=customer.id, contract_id=contract.id,
            revenue_date=date(2026, 3, 1), revenue_type='دفعة عقد',
            amount=1000, tax_amount=150, total=1150, status='محصّل',
            organization_id=org.id,
        ))
        db.session.add(Expense(
            code='EXP-CP1', expense_date=date(2026, 3, 2), expense_type='محروقات',
            amount=200, contract_id=contract.id, organization_id=org.id,
        ))
        db.session.add(Expense(
            code='EXP-CP2', expense_date=date(2026, 3, 3), expense_type='رواتب',
            amount=50, organization_id=org.id,
        ))
        db.session.commit()
        report = contract_profit_report(date(2026, 1, 1), date(2026, 12, 31))
        by_code = {row['code']: row for row in report['rows']}
        assert by_code['CN-CP1']['revenue'] == 1000
        assert by_code['CN-CP1']['expense'] == 200
        assert by_code['CN-CP1']['profit'] == 800
        assert by_code['بدون عقد']['expense'] == 50

    login_as(client, 'admin')
    page = client.get('/reports/contract-profit?from=2026-01-01&to=2026-12-31')
    assert page.status_code == 200
    assert '800.00' in page.get_data(as_text=True)
