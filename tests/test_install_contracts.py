"""اختبارات عقود التركيب المنفصلة."""
import json

from installation.contracts_service import (
    build_install_contract_summary,
    contract_for_project,
    create_install_contract_for_project,
    ensure_install_contract_schema,
    sync_install_contract_from_project,
)
from installation.models import InstallContract, InstallProject, InstallProjectReceipt, InstallQuotation
from installation.project_card import build_project_card, ensure_project_card_schema
from models import Customer, Organization, db
from tests.conftest import login_as


def _next_code(model, prefix, digits=5):
    existing = db.session.query(model.code).filter(model.code.like(f'{prefix}%')).all()
    max_num = 0
    for (code,) in existing:
        tail = str(code or '').replace(prefix, '')
        try:
            max_num = max(max_num, int(tail))
        except ValueError:
            pass
    return f'{prefix}{str(max_num + 1).zfill(digits)}'


def test_quote_approve_creates_install_contract(client):
    login_as(client, role='admin')
    with client.application.app_context():
        ensure_project_card_schema()
        ensure_install_contract_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-IC1',
            name='عميل عقد تركيب',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-IC1',
            title='مشروع عقد',
            status='عرض سعر',
            customer_id=cust.id,
        )
        db.session.add(project)
        db.session.flush()
        q = InstallQuotation(
            organization_id=org.id,
            code='QT-IC1',
            project_id=project.id,
            customer_id=cust.id,
            quote_type='new',
            status='مُرسل',
            grand_total=120000,
            before_tax=104348,
            vat_amount=15652,
            pay_advance_pct=50,
            pay_supply_pct=40,
            pay_final_pct=10,
        )
        db.session.add(q)
        db.session.commit()
        pid, qid = project.id, q.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        f'/installation/projects/{pid}/quotes/{qid}/approve',
        data={'csrf_token': 'test-csrf'},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        p = db.session.get(InstallProject, pid)
        contract = contract_for_project(p)
        assert contract is not None
        assert contract.code.startswith('CI-')
        assert float(contract.total) == 120000
        assert len(contract.installments) == 3
        sync_install_contract_from_project(p)
        assert float(contract.remaining_amount) == 120000


def test_install_contract_syncs_receipts(client):
    login_as(client, role='admin')
    with client.application.app_context():
        ensure_install_contract_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(organization_id=org.id, code='C-IC2', name='عميل تحصيل', status='نشط')
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-IC2',
            title='مشروع تحصيل',
            status='عقد',
            customer_id=cust.id,
        )
        db.session.add_all([cust, project])
        db.session.flush()
        q = InstallQuotation(
            organization_id=org.id,
            code='QT-IC2',
            project_id=project.id,
            customer_id=cust.id,
            status='مقبول',
            grand_total=100000,
            before_tax=86957,
            vat_amount=13043,
        )
        db.session.add(q)
        db.session.flush()
        project.accepted_quotation_id = q.id
        db.session.commit()
        project = db.session.get(InstallProject, project.id)
        q = db.session.get(InstallQuotation, q.id)
        contract = create_install_contract_for_project(project, q, next_code_fn=_next_code)
        db.session.commit()
        db.session.add(InstallProjectReceipt(
            organization_id=org.id,
            project_id=project.id,
            installment_no=1,
            label='دفعة مقدمة',
            amount=50000,
            status='مستلمة',
        ))
        db.session.commit()
        sync_install_contract_from_project(project)
        db.session.commit()
        assert float(contract.collected_amount) == 50000
        assert float(contract.remaining_amount) == 50000
        summary = build_install_contract_summary(contract, project)
        assert summary['installments'][0]['collected_amount'] == 50000


def test_install_contracts_list_page(client):
    login_as(client, role='admin')
    with client.application.app_context():
        ensure_install_contract_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(organization_id=org.id, code='C-IC3', name='عميل قائمة', status='نشط')
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-IC3',
            title='مشروع قائمة',
            status='عقد',
            customer_id=cust.id,
        )
        db.session.add_all([cust, project])
        db.session.flush()
        q = InstallQuotation(
            organization_id=org.id,
            code='QT-IC3',
            project_id=project.id,
            customer_id=cust.id,
            status='مقبول',
            grand_total=80000,
        )
        db.session.add(q)
        db.session.flush()
        create_install_contract_for_project(project, q, next_code_fn=_next_code)
        db.session.commit()

    resp = client.get('/installation/contracts')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8', errors='ignore')
    assert 'عقود التركيب' in body
    assert 'search-input' in body
    assert '__INSTALL_CONTRACTS__' in body
    assert 'PRJ-IC3' in body or 'CI-' in body


def test_manual_install_contract_with_installments(client):
    from installation.models import InstallContract

    login_as(client, role='admin')
    with client.application.app_context():
        ensure_install_contract_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(organization_id=org.id, code='C-IC5', name='عميل دفعات', status='نشط')
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-IC5',
            title='مشروع دفعات',
            status='عرض سعر',
            customer_id=cust.id,
        )
        db.session.add_all([cust, project])
        db.session.flush()
        q = InstallQuotation(
            organization_id=org.id,
            code='QT-IC5',
            project_id=project.id,
            customer_id=cust.id,
            status='مُرسل',
            grand_total=100000,
            before_tax=86957,
            vat_amount=13043,
            pay_advance_pct=50,
            pay_supply_pct=40,
            pay_final_pct=10,
        )
        db.session.add(q)
        db.session.commit()
        cid, pid, qid = cust.id, project.id, q.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    installments = json.dumps([
        {'label': 'دفعة مقدمة', 'pct': 50, 'amount': 50000},
        {'label': 'عند التوريد', 'pct': 40, 'amount': 40000},
        {'label': 'دفعة نهائية', 'pct': 10, 'amount': 10000},
    ])
    resp = client.post(
        '/installation/contracts/add',
        data={
            'csrf_token': 'test-csrf',
            'customer_id': str(cid),
            'quotation_id': str(qid),
            'contract_type': 'عقد تركيب',
            'status': 'نشط',
            'start_date': '2026-01-01',
            'duration_months': '12',
            'value': '86957',
            'tax_pct': '15',
            'total': '100000',
            'installments_json': installments,
        },
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data and data.get('ok') is True

    with client.application.app_context():
        contract = InstallContract.query.filter_by(code=data['code']).first()
        assert contract is not None
        assert contract.quotation_id == qid
        assert len(contract.installments) == 3
        labels = [i.label for i in contract.installments]
        assert 'دفعة مقدمة' in labels[0]
        assert float(contract.installments[0].amount) == 50000


def test_manual_install_contract_add(client):
    from installation.contracts_service import contract_for_project
    from installation.models import InstallContract

    login_as(client, role='admin')
    with client.application.app_context():
        ensure_install_contract_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(organization_id=org.id, code='C-IC4', name='عميل عقد يدوي', status='نشط')
        db.session.add(cust)
        db.session.commit()
        cid = cust.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        '/installation/contracts/add',
        data={
            'csrf_token': 'test-csrf',
            'customer_id': str(cid),
            'contract_type': 'عقد تركيب',
            'status': 'نشط',
            'start_date': '2026-01-01',
            'duration_months': '12',
            'value': '100000',
            'tax_pct': '15',
            'total': '115000',
        },
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data and data.get('ok') is True

    with client.application.app_context():
        contract = InstallContract.query.filter_by(code=data['code']).first()
        assert contract is not None
        assert float(contract.total) == 115000
        project = contract.project
        assert project is not None
        assert project.customer_id == cid
        assert contract_for_project(project) is not None


def test_contract_installment_pay(client):
    login_as(client, role='admin')
    with client.application.app_context():
        ensure_install_contract_schema()
        ensure_project_card_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(organization_id=org.id, code='C-IC5', name='عميل سداد', status='نشط')
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-IC5',
            title='مشروع سداد',
            status='عقد',
            customer_id=cust.id,
        )
        db.session.add_all([cust, project])
        db.session.flush()
        q = InstallQuotation(
            organization_id=org.id,
            code='QT-IC5',
            project_id=project.id,
            customer_id=cust.id,
            status='مقبول',
            grand_total=100000,
            before_tax=86957,
            vat_amount=13043,
            pay_advance_pct=50,
            pay_supply_pct=50,
        )
        db.session.add(q)
        db.session.flush()
        project.accepted_quotation_id = q.id
        db.session.commit()
        project = db.session.get(InstallProject, project.id)
        q = db.session.get(InstallQuotation, q.id)
        contract = create_install_contract_for_project(project, q, next_code_fn=_next_code)
        db.session.commit()
        contract_id = contract.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        f'/installation/contracts/{contract_id}/installments/1/pay',
        data={'csrf_token': 'test-csrf', 'amount': '50000', 'received_date': '2026-03-01'},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        contract = db.session.get(InstallContract, contract_id)
        sync_install_contract_from_project(contract.project)
        summary = build_install_contract_summary(contract, contract.project)
        assert summary['installments_paid'] == 1
        assert summary['installments_total'] >= 1
        assert float(contract.collected_amount) == 50000
        first = sorted(contract.installments, key=lambda x: x.seq or 0)[0]
        assert first.status == 'محصّلة'
