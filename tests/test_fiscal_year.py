"""إقفال السنة المالية: الأرباح المبقاة، قائمة الدخل، والقفل."""
from datetime import date

import pytest
from flask import g

from accounting_journals import (
    balance_sheet,
    create_manual_journal,
    ensure_journal_schema,
    income_statement,
    post_expense_journal,
    post_revenue_journal,
)
from chart_of_accounts import ensure_chart_for_org
from fiscal_years import ClosedFiscalYearError, close_fiscal_year, reopen_fiscal_year
from models import Account, Expense, JournalEntry, JournalLine, Organization, Revenue, db


def _org(slug):
    org = Organization(slug=slug, name='سنة', status='active')
    db.session.add(org)
    db.session.commit()
    ensure_chart_for_org(org.id)
    g.organization_id = org.id
    g.organization = org
    ensure_journal_schema()
    return org


def _revenue(org, day, amount=1000, tax=150):
    rev = Revenue(
        organization_id=org.id,
        code=f'REV-{day.isoformat()}',
        revenue_date=day,
        revenue_type='تجديد عقد',
        amount=amount,
        tax_amount=tax,
        total=amount + tax,
        status='محصّل',
    )
    db.session.add(rev)
    db.session.flush()
    renew = Account.query.execution_options(skip_tenant=True).filter_by(
        organization_id=org.id, map_key='revenue:تجديد عقد'
    ).first()
    rev.account_id = renew.id
    db.session.commit()
    return post_revenue_journal(db.session.get(Revenue, rev.id))


def _expense(org, day, amount=200):
    exp = Expense(
        organization_id=org.id,
        code=f'EXP-{day.isoformat()}',
        expense_date=day,
        expense_type='محروقات',
        amount=amount,
    )
    db.session.add(exp)
    db.session.flush()
    fuel = Account.query.execution_options(skip_tenant=True).filter_by(
        organization_id=org.id, map_key='expense:محروقات'
    ).first()
    exp.account_id = fuel.id
    db.session.commit()
    return post_expense_journal(db.session.get(Expense, exp.id))


def test_close_moves_net_to_retained_and_keeps_pnl(client):
    with client.application.app_context():
        org = _org('fy-close')
        _revenue(org, date(2025, 3, 1))
        _expense(org, date(2025, 4, 1))
        db.session.commit()

        year = close_fiscal_year(date(2025, 1, 1), date(2025, 12, 31))
        db.session.commit()
        assert year.status == 'closed'
        assert year.net_income == 800

        re_acc = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, code='3300'
        ).first()
        lines = JournalLine.query.execution_options(skip_tenant=True).filter_by(
            journal_id=year.journal_id, account_id=re_acc.id
        ).all()
        assert sum(l.credit or 0 for l in lines) == 800

        pnl = income_statement(date_from=date(2025, 1, 1), date_to=date(2025, 12, 31))
        assert pnl['revenue'] == 1000
        assert pnl['expense'] == 200
        assert pnl['net'] == 800

        bs = balance_sheet(as_of=date(2025, 12, 31))
        names = [row['name'] for row in bs['equity']]
        assert 'صافي الدخل (الفترة)' not in names
        assert bs['total_assets'] == pytest.approx(bs['total_liab_equity'])
        re_row = next(row for row in bs['equity'] if row['code'] == '3300')
        assert re_row['amount'] == 800


def test_closed_year_rejects_new_journal_until_reopen(client):
    with client.application.app_context():
        org = _org('fy-lock')
        _revenue(org, date(2025, 6, 1), amount=400, tax=0)
        db.session.commit()
        close_fiscal_year(date(2025, 1, 1), date(2025, 12, 31))
        db.session.commit()

        cash = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, map_key='cash'
        ).first()
        bank = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, map_key='bank'
        ).first()
        with pytest.raises(ClosedFiscalYearError):
            create_manual_journal(
                entry_date=date(2025, 2, 1),
                memo='داخل سنة مقفلة',
                lines=[(cash.id, 10, 0, None), (bank.id, 0, 10, None)],
            )

        years = JournalEntry.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, source_type='year_close', status='posted'
        ).all()
        assert len(years) == 1
        year_id = years[0].source_id
        reopen_fiscal_year(year_id)
        db.session.commit()
        posted = JournalEntry.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, source_type='year_close', status='posted'
        ).count()
        assert posted == 0
        je = create_manual_journal(
            entry_date=date(2025, 2, 1),
            memo='بعد إعادة الفتح',
            lines=[(cash.id, 10, 0, None), (bank.id, 0, 10, None)],
        )
        assert je is not None
        assert je.status == 'posted'
