"""اختبارات القيود اليومية — المرحلة 2."""
from datetime import date

from accounting_journals import (
    backfill_journals,
    create_manual_journal,
    income_statement,
    post_expense_journal,
    post_revenue_journal,
    trial_balance_rows,
    void_manual_journal,
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


def test_create_and_void_manual_journal_updates_trial_balance(client):
    with client.application.app_context():
        org = Organization(slug='je-man', name='يدوي', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)
        from flask import g
        g.organization_id = org.id
        g.organization = org

        from accounting_journals import ensure_journal_schema
        ensure_journal_schema()
        cash = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, map_key='cash'
        ).first()
        capital = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, map_key='capital'
        ).first()
        je = create_manual_journal(
            entry_date=date(2026, 1, 1),
            memo='رصيد افتتاحي',
            kind='opening',
            lines=[
                (cash.id, 10000, 0, 'صندوق'),
                (capital.id, 0, 10000, 'رأس مال'),
            ],
        )
        assert je is not None
        assert je.source_type == 'opening'
        db.session.commit()
        je_id = je.id

        je2 = create_manual_journal(
            entry_date=date(2026, 1, 2),
            memo='تحويل',
            kind='manual',
            lines=[
                (capital.id, 500, 0, None),
                (cash.id, 0, 500, None),
            ],
        )
        assert je2 is not None
        db.session.commit()
        posted = JournalEntry.query.execution_options(skip_tenant=True).filter_by(
            organization_id=org.id, status='posted'
        ).count()
        assert posted == 2

        rows, td, tc = trial_balance_rows()
        assert round(td, 2) == round(tc, 2)
        assert round(td, 2) == 10500

        assert void_manual_journal(je_id) is True
        db.session.commit()
        rows2, td2, tc2 = trial_balance_rows()
        assert round(td2, 2) == round(tc2, 2)
        assert round(td2, 2) == 500

        assert void_manual_journal(je_id) is False


def test_void_manual_does_not_void_auto_revenue_journal(client):
    with client.application.app_context():
        org = Organization(slug='je-novoid', name='تلقائي', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)
        from flask import g
        g.organization_id = org.id
        g.organization = org
        from accounting_journals import ensure_journal_schema
        ensure_journal_schema()

        rev = Revenue(
            organization_id=org.id,
            code='REV-902',
            revenue_date=date(2026, 3, 1),
            revenue_type='عقد صيانة',
            amount=300,
            tax_amount=0,
            total=300,
            status='محصّل',
        )
        db.session.add(rev)
        db.session.commit()
        je = post_revenue_journal(rev)
        assert je is not None
        db.session.commit()
        assert void_manual_journal(je.id) is False
        db.session.refresh(je)
        assert je.status == 'posted'


def test_journal_new_page_posts_balanced_entry(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        from tests.conftest import ensure_test_organization
        oid = ensure_test_organization()
        ensure_chart_for_org(oid)
        from accounting_journals import ensure_journal_schema
        ensure_journal_schema()
        cash = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=oid, map_key='cash'
        ).first()
        capital = Account.query.execution_options(skip_tenant=True).filter_by(
            organization_id=oid, map_key='capital'
        ).first()
        cash_id, cap_id = cash.id, capital.id

    page = client.get('/journals/new')
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'قيد يدوي' in body

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'
    resp = client.post('/journals/new', data={
        'csrf_token': 'test-csrf',
        'entry_date': '2026-01-01',
        'kind': 'opening',
        'memo': 'افتتاح اختبار',
        'account_id': [str(cash_id), str(cap_id)],
        'debit': ['2500', '0'],
        'credit': ['0', '2500'],
        'line_memo': ['نقد', 'رأس مال'],
    })
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        je = JournalEntry.query.execution_options(skip_tenant=True).filter_by(
            organization_id=oid, source_type='opening', status='posted'
        ).first()
        assert je is not None
        assert round(sum(l.debit or 0 for l in je.lines), 2) == 2500
        assert round(sum(l.credit or 0 for l in je.lines), 2) == 2500
