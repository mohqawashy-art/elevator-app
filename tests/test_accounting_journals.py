"""اختبارات القيود اليومية — المرحلة 2."""
from datetime import date

from accounting_journals import (
    backfill_journals,
    income_statement,
    post_expense_journal,
    post_revenue_journal,
    trial_balance_rows,
)
from chart_of_accounts import ensure_chart_for_org
from models import Account, Expense, JournalEntry, Organization, Revenue, db


def test_post_revenue_and_expense_journals_balance(client):
    with client.application.app_context():
        org = Organization(slug='je-test', name='قيود', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)

        from flask import g
        g.organization_id = org.id
        g.organization = org

        rev = Revenue(
            organization_id=org.id,
            code='REV-900',
            revenue_date=date(2026, 1, 15),
            revenue_type='تجديد عقد',
            amount=1000,
            tax_amount=150,
            total=1150,
            status='محصّل',
        )
        db.session.add(rev)
        db.session.flush()
        cash = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, map_key='cash'
        ).first()
        renew = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, map_key='revenue:تجديد عقد'
        ).first()
        rev.account_id = renew.id
        db.session.commit()
        rev_id = rev.id
        # إنشاء جداول القيود قبل الترحيل حتى لا تُفسد الجلسة وسط القيد
        from accounting_journals import ensure_journal_schema
        ensure_journal_schema()
        rev = db.session.get(Revenue, rev_id)
        je = post_revenue_journal(rev)
        assert je is not None
        assert je.status == 'posted'
        lines = list(je.lines)
        assert round(sum(l.debit or 0 for l in lines), 2) == 1150
        assert round(sum(l.credit or 0 for l in lines), 2) == 1150
        assert any(l.account_id == cash.id and l.debit == 1150 for l in lines)

        exp = Expense(
            organization_id=org.id,
            code='EXP-900',
            expense_date=date(2026, 1, 16),
            expense_type='محروقات',
            amount=200,
        )
        db.session.add(exp)
        db.session.flush()
        fuel = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, map_key='expense:محروقات'
        ).first()
        exp.account_id = fuel.id
        db.session.commit()
        je2 = post_expense_journal(exp)
        assert je2 is not None
        assert round(sum(l.debit or 0 for l in je2.lines), 2) == 200
        assert round(sum(l.credit or 0 for l in je2.lines), 2) == 200

        db.session.commit()
        rows, td, tc = trial_balance_rows()
        assert round(td, 2) == round(tc, 2)
        assert td > 0

        pnl = income_statement()
        assert pnl['revenue'] == 1000
        assert pnl['expense'] == 200
        assert pnl['net'] == 800


def test_backfill_journals_skips_already_posted(client):
    with client.application.app_context():
        org = Organization(slug='je-bf', name='ترحيل', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)
        from flask import g
        g.organization_id = org.id
        g.organization = org

        rev = Revenue(
            organization_id=org.id,
            code='REV-901',
            revenue_date=date(2026, 2, 1),
            revenue_type='عقد صيانة',
            amount=500,
            tax_amount=0,
            total=500,
            status='محصّل',
        )
        db.session.add(rev)
        db.session.commit()

        stats1 = backfill_journals()
        assert stats1['revenues'] >= 1
        count1 = JournalEntry.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, source_type='revenue', status='posted'
        ).count()
        stats2 = backfill_journals()
        assert stats2['revenues'] == 0
        count2 = JournalEntry.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, source_type='revenue', status='posted'
        ).count()
        assert count2 == count1
