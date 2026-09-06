"""اختبارات كارت مشروع التركيب."""
from datetime import date

from sqlalchemy import text

from installation.models import InstallLead, InstallProject, InstallProjectCostItem, InstallProjectReceipt
from installation.project_card import build_project_card, ensure_project_card_schema
from models import Organization, db
from tests.conftest import login_as


def test_leads_list_recovers_missing_contract_value(client):
    """قائمة الفرص كانت تفشل 500 إذا غاب contract_value عن installation_projects."""
    login_as(client, role='admin')
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        lead = InstallLead(
            organization_id=org.id,
            code='LD-MISSCOL',
            client_name='عميل اختبار',
            status='جديد',
        )
        db.session.add(lead)
        db.session.commit()
        # محاكاة إنتاج بلا عمود القيمة
        try:
            db.session.execute(text('ALTER TABLE installation_projects DROP COLUMN contract_value'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        import installation.routes as install_routes
        install_routes._schema_ensured = False

    resp = client.get('/installation/leads')
    assert resp.status_code == 200
    assert 'فرص البيع' in resp.data.decode('utf-8', errors='ignore')


def test_leads_add_creates_opportunity(client):
    login_as(client, role='admin')
    with client.application.app_context():
        from models import Customer
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-LEADADD',
            name='عميل فرصة',
            status='نشط',
            phone='0500000000',
        )
        db.session.add(cust)
        db.session.commit()
        cid = cust.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    resp = client.post('/installation/leads/add', data={
        'csrf_token': 'test-csrf',
        'customer_id': cid,
        'source': 'اتصال',
        'status': 'جديد',
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode('utf-8', errors='ignore')
    assert 'تم إنشاء الفرصة' in body or 'LD-' in body


def test_two_orgs_can_reuse_lead_code(client):
    """قيود code العالمية كانت تمنع LD-0001 لمستأجر ثانٍ."""
    from installation.schema import ensure_install_tenant_uniques

    login_as(client, role='admin')
    with client.application.app_context():
        ensure_install_tenant_uniques()
        org_a = Organization.query.filter_by(slug='default').first()
        org_b = Organization.query.filter_by(slug='beta').first()
        if not org_b:
            org_b = Organization(slug='beta', name='Beta', status='active')
            db.session.add(org_b)
            db.session.commit()

        for org in (org_a, org_b):
            existing = (
                InstallLead.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=org.id, code='LD-0001')
                .first()
            )
            if existing:
                db.session.delete(existing)
        db.session.commit()

        db.session.add(InstallLead(
            organization_id=org_a.id,
            code='LD-0001',
            client_name='عميل أ',
            status='جديد',
        ))
        db.session.commit()
        db.session.add(InstallLead(
            organization_id=org_b.id,
            code='LD-0001',
            client_name='عميل مستأجر آخر',
            status='جديد',
        ))
        db.session.commit()
        total = (
            InstallLead.query.execution_options(skip_tenant=True)
            .filter_by(code='LD-0001')
            .count()
        )
        assert total >= 2


def test_project_card_costs_and_receipts(client):
    login_as(client, role='admin')
    with client.application.app_context():
        ensure_project_card_schema()
        org = Organization.query.filter_by(slug='default').first()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-CARD1',
            title='مشروع كارت',
            status='عقد',
            contract_value=40000,
        )
        db.session.add(project)
        db.session.flush()
        db.session.add(InstallProjectCostItem(
            organization_id=org.id,
            project_id=project.id,
            category='السكك والأبواب',
            title='سكك وأبواب',
            amount=23000,
            cost_date=date.today(),
        ))
        db.session.add(InstallProjectCostItem(
            organization_id=org.id,
            project_id=project.id,
            category='السكك والأبواب',
            title='دفعة أولى',
            amount=2000,
            installment_no=1,
            payment_status='مدفوعة',
            cost_date=date.today(),
            notes='تحويل بنكي — مرجع 123',
        ))
        db.session.add(InstallProjectCostItem(
            organization_id=org.id,
            project_id=project.id,
            category='الماكينة والشاسيه',
            title='دفعة ثانية',
            amount=2000,
            installment_no=2,
            payment_status='غير مدفوعة',
            cost_date=date.today(),
        ))
        db.session.add(InstallProjectCostItem(
            organization_id=org.id,
            project_id=project.id,
            category='الكابينة والكنترول',
            title='دفعة ثالثة',
            amount=1600,
            installment_no=3,
            payment_status='غير مدفوعة',
            cost_date=date.today(),
        ))
        db.session.add(InstallProjectReceipt(
            organization_id=org.id,
            project_id=project.id,
            installment_no=1,
            label='دفعة رقم 1',
            amount=10000,
            status='مستلمة',
            received_date=date.today(),
        ))
        db.session.commit()
        pid = project.id

        card = build_project_card(db.session.get(InstallProject, pid))
        assert card['contract_value'] == 40000
        assert card['total_cost'] == 28600
        assert card['received'] == 10000
        assert card['profit'] == 11400
        labels = [r['label'] for r in card['sheet_rows']]
        assert 'قيمة المشروع' in labels
        assert 'تكاليف المشروع' in labels
        assert 'مرحلة 1 — السكك والأبواب' in labels
        assert 'مرحلة 2 — الماكينة والشاسيه' in labels
        assert 'مرحلة 3 — الكابينة والكنترول' in labels
        assert 'دفعة أولى' in labels
        assert 'دفعة ثانية' in labels
        assert 'دفعة ثالثة' in labels
        line_notes = [r['note'] for r in card['sheet_rows'] if r['kind'] == 'line']
        assert 'تحويل بنكي — مرجع 123' in line_notes

    resp = client.get(f'/installation/projects/{pid}')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8', errors='ignore')
    assert 'كارت المشروع' in body
    assert 'دفعة أولى' in body
    assert 'تحويل بنكي — مرجع 123' in body
    assert 'مدفوعة' in body
    assert 'مرحلة 1 — السكك والأبواب' in body
    assert 'تعديل' in body
    assert 'pc-sheet' in body
    assert 'طباعة الكارت' in body
    assert 'ربط بعقد' in body

    resp_print = client.get(f'/installation/projects/{pid}/card/print')
    assert resp_print.status_code == 200
    print_body = resp_print.data.decode('utf-8', errors='ignore')
    assert 'كارت مشروع' in print_body
    assert 'دفعة أولى' in print_body
    assert 'window.print' in print_body


def test_project_card_cost_edit(client):
    login_as(client, role='admin')
    with client.application.app_context():
        ensure_project_card_schema()
        org = Organization.query.filter_by(slug='default').first()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-EDIT1',
            title='مشروع تعديل',
            status='عقد',
            contract_value=10000,
        )
        db.session.add(project)
        db.session.flush()
        item = InstallProjectCostItem(
            organization_id=org.id,
            project_id=project.id,
            category='السكك والأبواب',
            title='سكك',
            amount=500,
            cost_date=date.today(),
        )
        db.session.add(item)
        db.session.commit()
        pid, iid = project.id, item.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        f'/installation/projects/{pid}/card/costs/{iid}/edit',
        data={
            'csrf_token': 'test-csrf',
            'category': 'الماكينة والشاسيه',
            'title': 'ماكينة محدّثة',
            'amount': '750',
            'cost_date': date.today().isoformat(),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert 'تم تحديث بند التكلفة' in resp.data.decode('utf-8', errors='ignore')
    with client.application.app_context():
        updated = db.session.get(InstallProjectCostItem, iid)
        assert updated.category == 'الماكينة والشاسيه'
        assert updated.title == 'ماكينة محدّثة'
        assert float(updated.amount) == 750


def test_legacy_cost_category_migration(client):
    login_as(client, role='admin')
    with client.application.app_context():
        from installation.project_card import build_project_card
        import installation.project_card as pc_mod
        pc_mod._cost_phases_migrated = False
        ensure_project_card_schema()
        org = Organization.query.filter_by(slug='default').first()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-MIG1',
            title='ترقية فئات',
            status='عقد',
        )
        db.session.add(project)
        db.session.flush()
        db.session.add(InstallProjectCostItem(
            organization_id=org.id,
            project_id=project.id,
            category='قطع غيار',
            title='قطع',
            amount=100,
            cost_date=date.today(),
        ))
        db.session.add(InstallProjectCostItem(
            organization_id=org.id,
            project_id=project.id,
            category='عمالة',
            title='دفعة 2',
            amount=200,
            installment_no=2,
            cost_date=date.today(),
        ))
        db.session.commit()
        pid = project.id
        ensure_project_card_schema()
        card = build_project_card(db.session.get(InstallProject, pid))
        labels = [r['label'] for r in card['sheet_rows']]
        assert 'مرحلة 1 — السكك والأبواب' in labels
        assert 'مرحلة 2 — الماكينة والشاسيه' in labels


def test_project_card_link_contract(client):
    login_as(client, role='admin')
    with client.application.app_context():
        from models import Customer, Contract
        ensure_project_card_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-CARD-CN',
            name='عميل عقد',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        contract = Contract(
            organization_id=org.id,
            code='CI-CARD1',
            customer_id=cust.id,
            contract_type='عقد تركيب',
            start_date=date.today(),
            end_date=date.today(),
            value=40000,
            total=40000,
            status='نشط',
        )
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-CARD-CN',
            title='مشروع مربوط بعقد',
            status='عقد',
            customer_id=cust.id,
        )
        db.session.add(contract)
        db.session.add(project)
        db.session.commit()
        pid, cid = project.id, contract.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        f'/installation/projects/{pid}/card/link-contract',
        data={'csrf_token': 'test-csrf', 'contract_id': cid, 'sync_value': '1'},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert 'تم ربط الكارت بالعقد' in resp.data.decode('utf-8', errors='ignore')
    with client.application.app_context():
        p = db.session.get(InstallProject, pid)
        assert p.contract_id == cid
        assert float(p.contract_value or 0) == 40000


def test_project_card_rejects_maintenance_contract_link(client):
    login_as(client, role='admin')
    with client.application.app_context():
        from models import Customer, Contract
        ensure_project_card_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-CARD-MN',
            name='عميل صيانة',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        maint = Contract(
            organization_id=org.id,
            code='CN-CARD-MN',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date.today(),
            end_date=date.today(),
            value=12000,
            total=12000,
            status='نشط',
        )
        install = Contract(
            organization_id=org.id,
            code='CI-CARD-IN',
            customer_id=cust.id,
            contract_type='عقد تركيب',
            start_date=date.today(),
            end_date=date.today(),
            value=50000,
            total=50000,
            status='نشط',
        )
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-CARD-MN',
            title='مشروع بدون صيانة',
            status='عقد',
            customer_id=cust.id,
        )
        db.session.add_all([maint, install, project])
        db.session.commit()
        pid, mid, iid = project.id, maint.id, install.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    detail = client.get(f'/installation/projects/{pid}')
    assert detail.status_code == 200
    body = detail.data.decode('utf-8', errors='ignore')
    assert 'CI-CARD-IN' in body
    assert 'CN-CARD-MN' not in body

    resp = client.post(
        f'/installation/projects/{pid}/card/link-contract',
        data={'csrf_token': 'test-csrf', 'contract_id': mid, 'sync_value': '1'},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert 'عقود التركيب' in resp.data.decode('utf-8', errors='ignore')
    with client.application.app_context():
        p = db.session.get(InstallProject, pid)
        assert p.contract_id is None

    ok = client.post(
        f'/installation/projects/{pid}/card/link-contract',
        data={'csrf_token': 'test-csrf', 'contract_id': iid, 'sync_value': '1'},
        follow_redirects=True,
    )
    assert ok.status_code == 200
    with client.application.app_context():
        p = db.session.get(InstallProject, pid)
        assert p.contract_id == iid


def test_project_delete_from_list(client):
    login_as(client, role='admin')
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-DEL-01',
            title='مشروع للحذف',
            status='تسعير',
        )
        db.session.add(project)
        db.session.commit()
        pid = project.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        f'/installation/projects/{pid}/delete',
        data={'csrf_token': 'test-csrf'},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.data.decode('utf-8', errors='ignore')
    assert 'تم حذف المشروع' in body
    with client.application.app_context():
        assert db.session.get(InstallProject, pid) is None
