"""اختبارات شجرة الحسابات — المرحلة 1."""
from chart_of_accounts import (
    DEFAULT_CHART,
    ROOT_GROUPS,
    create_custom_account,
    delete_account,
    ensure_chart_for_org,
    ensure_chart_schema,
    resolve_expense_account_id,
    resolve_revenue_account_id,
    seed_root_groups_for_org,
    update_account,
)
from models import Account, Organization, db
from sqlalchemy import inspect


def test_ensure_chart_schema_is_idempotent(client):
    with client.application.app_context():
        ensure_chart_schema()
        ensure_chart_schema()
        insp = inspect(db.engine)
        assert 'accounts' in insp.get_table_names()
        rev_cols = {c['name'] for c in insp.get_columns('revenues')}
        exp_cols = {c['name'] for c in insp.get_columns('expenses')}
        assert 'account_id' in rev_cols
        assert 'account_id' in exp_cols


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
        box = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='1110')
            .first()
        )
        bank = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='1120')
            .first()
        )
        assert box.map_key == 'cash'
        assert bank.map_key == 'bank'
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
        assert acc and acc.code == '4120'

        due_id = resolve_revenue_account_id('الدفعات المستحقة')
        assert due_id == renew_id

        install_id = resolve_revenue_account_id('عقد تركيب')
        assert install_id == resolve_revenue_account_id('عقد جديد')

        upgrade_id = resolve_revenue_account_id('عقد تحديث')
        upgrade = db.session.get(Account, upgrade_id)
        assert upgrade and upgrade.code == '4220'

        prior_id = resolve_revenue_account_id('عقد صيانة', 'تحصيل مالك سابق — قبل استلام جما')
        prior = db.session.get(Account, prior_id)
        assert prior and prior.code == '4910'

        fuel_id = resolve_expense_account_id('محروقات')
        fuel = db.session.get(Account, fuel_id)
        assert fuel and fuel.code == '6210'

        misc_id = resolve_expense_account_id('مصروفات متنوعة')
        misc = db.session.get(Account, misc_id)
        assert misc and misc.code == '6910'
        assert resolve_expense_account_id('ضيافة') == misc_id
        assert resolve_expense_account_id('متنوعة') == misc_id

        salary_id = resolve_expense_account_id('رواتب')
        salary = db.session.get(Account, salary_id)
        assert salary and salary.code == '6110'

        other_rev_id = resolve_revenue_account_id('أخرى')
        other_rev = db.session.get(Account, other_rev_id)
        assert other_rev and other_rev.code == '4920'


def test_create_custom_account_under_parent(client):
    with client.application.app_context():
        org = Organization(slug='coa-add', name='حساب جديد', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)
        from flask import g
        g.organization_id = org.id
        g.organization = org

        parent = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='5000')
            .first()
        )
        acc = create_custom_account(
            code='5310',
            name='صيانة معدات',
            account_type='expense',
            parent_id=parent.id,
            is_postable=True,
        )
        db.session.commit()
        assert acc.id
        assert not acc.is_system
        assert acc.parent_id == parent.id

        try:
            create_custom_account(
                code='5310',
                name='مكرر',
                account_type='expense',
                parent_id=parent.id,
            )
            assert False, 'expected duplicate code'
        except ValueError as exc:
            assert 'مستخدم' in str(exc)


def test_relocate_cash_map_key_from_bank_to_cashbox(client):
    with client.application.app_context():
        org = Organization(slug='coa-reloc', name='نقل كاش', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)
        box = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='1110')
            .first()
        )
        bank = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='1120')
            .first()
        )
        box.map_key = None
        bank.map_key = 'cash'
        db.session.commit()
        from flask import g
        g.organization_id = org.id
        g.organization = org
        ensure_chart_for_org(org.id)
        db.session.refresh(box)
        db.session.refresh(bank)
        assert box.map_key == 'cash'
        assert bank.map_key == 'bank'


def test_accounts_add_route_creates_account(client):
    from tests.conftest import ensure_test_organization, login_as

    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        ensure_chart_for_org(oid)
        parent = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid, code='4000')
            .first()
        )
        parent_id = parent.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'
    resp = client.post('/accounts/add', data={
        'csrf_token': 'test-csrf',
        'code': '4400',
        'name': 'إيراد تدريب',
        'account_type': 'revenue',
        'parent_id': str(parent_id),
        'is_postable': '1',
    })
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        acc = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid, code='4400')
            .first()
        )
        assert acc is not None
        assert acc.name == 'إيراد تدريب'
        assert acc.account_type == 'revenue'


def test_accounts_page_does_not_auto_seed(client):
    from tests.conftest import ensure_test_organization, login_as

    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        before = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid)
            .count()
        )
        assert before == 0

    resp = client.get('/accounts')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'ابدأ شجرة حسابات مؤسستك' in html
    assert 'أنشئ شجرتك' in html

    with client.application.app_context():
        after = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid)
            .count()
        )
        assert after == 0


def test_seed_root_groups_only(client):
    with client.application.app_context():
        org = Organization(slug='coa-roots', name='مجموعات فقط', status='active')
        db.session.add(org)
        db.session.commit()
        added = seed_root_groups_for_org(org.id)
        assert added == len(ROOT_GROUPS)
        rows = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .order_by(Account.code.asc())
            .all()
        )
        assert [a.code for a in rows] == ['1000', '2000', '3000', '4000', '5000', '6000']
        assert all(not a.is_postable and a.parent_id is None for a in rows)
        assert seed_root_groups_for_org(org.id) == 0


def test_create_root_account_without_parent(client):
    with client.application.app_context():
        org = Organization(slug='coa-root-acc', name='جذر مخصص', status='active')
        db.session.add(org)
        db.session.commit()
        from flask import g
        g.organization_id = org.id
        g.organization = org

        acc = create_custom_account(
            code='100',
            name='أصول الشركة',
            account_type='asset',
            parent_id=None,
            is_postable=False,
        )
        db.session.commit()
        assert acc.parent_id is None
        assert not acc.is_postable
        assert not acc.is_system


def test_accounts_seed_roots_route(client):
    from tests.conftest import ensure_test_organization, login_as

    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'
    resp = client.post('/accounts/seed-roots', data={'csrf_token': 'test-csrf'})
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        codes = {
            a.code
            for a in Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid)
            .all()
        }
        assert codes == {'1000', '2000', '3000', '4000', '5000', '6000'}


def test_update_account_renames_and_moves(client):
    with client.application.app_context():
        org = Organization(slug='coa-edit', name='تعديل حساب', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)
        from flask import g
        g.organization_id = org.id
        g.organization = org

        fuel = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='5300')
            .first()
        )
        other = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='5000')
            .first()
        )
        updated = update_account(
            fuel.id,
            code='5350',
            name='وقود وزيوت',
            account_type='expense',
            parent_id=other.id,
            is_postable=True,
            is_active=True,
        )
        db.session.commit()
        assert updated.code == '5350'
        assert updated.name == 'وقود وزيوت'

        assets = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='1000')
            .first()
        )
        try:
            update_account(
                fuel.id,
                code='5350',
                name='وقود وزيوت',
                account_type='expense',
                parent_id=assets.id,
                is_postable=True,
            )
            assert False, 'expected parent type mismatch'
        except ValueError as exc:
            db.session.rollback()
            assert 'الأب' in str(exc)

        try:
            update_account(
                other.id,
                code='5000',
                name=other.name,
                account_type='expense',
                parent_id=fuel.id,
                is_postable=False,
            )
            assert False, 'expected cycle'
        except ValueError as exc:
            assert 'فروع' in str(exc) or 'نفسه' in str(exc)


def test_accounts_edit_route(client):
    from tests.conftest import ensure_test_organization, login_as

    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        ensure_chart_for_org(oid)
        acc = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid, code='4100')
            .first()
        )
        acc_id = acc.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'
    resp = client.post(f'/accounts/{acc_id}/edit', data={
        'csrf_token': 'test-csrf',
        'code': '4100',
        'name': 'إيراد صيانة معدّل',
        'account_type': 'revenue',
        'parent_id': '',
        'is_postable': '1',
        'is_active': '1',
    })
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        acc = db.session.get(Account, acc_id)
        assert acc.name == 'إيراد صيانة معدّل'
        assert acc.parent_id is None


def test_wipe_chart_for_org_clears_accounts_only(client):
    from models import JournalEntry, JournalLine, Revenue

    with client.application.app_context():
        from chart_of_accounts import wipe_chart_for_org

        org = Organization(slug='coa-wipe', name='مسح شجرة', status='active')
        other = Organization(slug='coa-keep', name='لا تُمسح', status='active')
        db.session.add_all([org, other])
        db.session.commit()
        ensure_chart_for_org(org.id)
        ensure_chart_for_org(other.id)

        rev = Revenue(
            code='REV-W1',
            revenue_date=__import__('datetime').date.today(),
            amount=100,
            total=100,
            organization_id=org.id,
        )
        db.session.add(rev)
        db.session.flush()
        cash = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='1120')
            .first()
        )
        rev.account_id = cash.id
        je = JournalEntry(
            code='JE-W1',
            entry_date=__import__('datetime').date.today(),
            memo='قيد اختبار',
            source_type='manual',
            status='posted',
            organization_id=org.id,
        )
        db.session.add(je)
        db.session.flush()
        db.session.add(JournalLine(
            journal_id=je.id,
            account_id=cash.id,
            debit=100,
            credit=0,
            organization_id=org.id,
        ))
        db.session.commit()

        stats = wipe_chart_for_org(org.id)
        assert stats['accounts'] > 0
        assert (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .count()
        ) == 0
        assert (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=other.id)
            .count()
        ) == len(DEFAULT_CHART)
        assert (
            JournalEntry.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .count()
        ) == 0
        leftover = db.session.get(Revenue, rev.id)
        assert leftover is not None
        assert leftover.account_id is None


def test_accounts_wipe_route(client):
    from tests.conftest import ensure_test_organization, login_as

    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        ensure_chart_for_org(oid)
        assert (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid)
            .count()
        ) > 0

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'
    resp = client.post('/accounts/wipe', data={'csrf_token': 'test-csrf'})
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        assert (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid)
            .count()
        ) == 0


def test_delete_account_leaf_and_reject_parent(client):
    with client.application.app_context():
        org = Organization(slug='coa-del', name='حذف حساب', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)
        from flask import g
        g.organization_id = org.id
        g.organization = org

        parent = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='5000')
            .first()
        )
        try:
            delete_account(parent.id)
            assert False, 'expected parent reject'
        except ValueError as exc:
            assert 'فروع' in str(exc)

        fuel = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='5300')
            .first()
        )
        code, name = delete_account(fuel.id)
        db.session.commit()
        assert code == '5300'
        assert (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, code='5300')
            .first()
        ) is None


def test_accounts_delete_route(client):
    from tests.conftest import ensure_test_organization, login_as

    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        ensure_chart_for_org(oid)
        acc = (
            Account.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid, code='6910')
            .first()
        )
        acc_id = acc.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'
    resp = client.post(f'/accounts/{acc_id}/delete', data={'csrf_token': 'test-csrf'})
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        assert db.session.get(Account, acc_id) is None
