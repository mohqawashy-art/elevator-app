"""P2 I5 — QA طباعة المستندات: HTTP 200 + عناصر أساسية."""
from __future__ import annotations

import json
from datetime import date

import pytest

from models import (
    Contract,
    Customer,
    ElevatorEstimate,
    InventoryItem,
    Invoice,
    PurchaseOrder,
    PurchaseOrderLine,
    Settings,
    db,
)

from tests.conftest import login_as


def _seed_print_documents():
    s = Settings.query.first()
    if not s:
        s = Settings(company_name='LiftCore Test', tax_pct=15, vat_number='300000000000003')
        db.session.add(s)
    else:
        s.company_name = s.company_name or 'LiftCore Test'
        s.vat_number = s.vat_number or '300000000000003'

    cust = Customer(code='C-PR01', name='عميل طباعة', phone='512345678', status='نشط')
    db.session.add(cust)
    db.session.flush()
    today = date.today()

    contract = Contract(
        code='CN-PR01',
        customer_id=cust.id,
        contract_type='صيانة',
        start_date=today,
        end_date=today,
        value=10000,
        total=11500,
        status='نشط',
    )
    db.session.add(contract)
    db.session.flush()

    inv = Invoice(
        code='INV-PR01',
        invoice_type='فاتورة ضريبية',
        customer_id=cust.id,
        contract_id=contract.id,
        invoice_date=today,
        amount=10000,
        tax_amount=1500,
        total=11500,
    )
    db.session.add(inv)
    db.session.flush()

    item = InventoryItem(code='IT-PR01', name='بكرة', unit='قطعة')
    db.session.add(item)
    db.session.flush()
    po = PurchaseOrder(code='PO-PR01', supplier='مورد', order_date=today, total_amount=500)
    db.session.add(po)
    db.session.flush()
    db.session.add(PurchaseOrderLine(
        order_id=po.id, item_id=item.id, quantity=2, unit_price=250, line_total=500,
    ))

    est = ElevatorEstimate(
        code='EST-PR01',
        customer_id=cust.id,
        project_name='برج تجريبي',
        total=250000,
        estimate_date=today,
    )
    db.session.add(est)
    db.session.flush()

    install_quote_id = None
    try:
        from installation.models import InstallProject, InstallQuotation

        proj = InstallProject(code='IP-PR01', title='مشروع طباعة', customer_id=cust.id)
        db.session.add(proj)
        db.session.flush()
        quote = InstallQuotation(
            code='IQ-PR01',
            project_id=proj.id,
            customer_id=cust.id,
            spec_json=json.dumps({'machine_brand': 'Kone'}),
            grand_total=120000,
        )
        db.session.add(quote)
        db.session.flush()
        install_quote_id = quote.id
    except Exception:
        pass

    db.session.commit()
    return {
        'contract_id': contract.id,
        'invoice_id': inv.id,
        'po_id': po.id,
        'estimate_id': est.id,
        'install_quote_id': install_quote_id,
    }


def test_all_print_documents_smoke(client):
    login_as(client, 'admin')
    with client.application.app_context():
        ids = _seed_print_documents()

    checks = [
        (f'/contracts/{ids["contract_id"]}/print', ['طباعة', 'CN0001']),
        (f'/invoices/{ids["invoice_id"]}/print', ['INV-PR01', 'فاتورة']),
        (f'/purchase-orders/{ids["po_id"]}/print', ['PO-PR01']),
        (f'/purchase-orders/{ids["po_id"]}/print-en', ['PO-PR01', 'en']),
        (f'/elevator-estimates/print/{ids["estimate_id"]}', ['EST-PR01']),
    ]
    if ids.get('install_quote_id'):
        checks.append(
            (f'/installation/quotes/{ids["install_quote_id"]}/print', ['IQ-PR01']),
        )

    for path, needles in checks:
        r = client.get(path)
        assert r.status_code == 200, f'{path} -> {r.status_code}'
        html = r.get_data(as_text=True)
        for needle in needles:
            assert needle in html, f'{needle} missing in {path}'


@pytest.mark.parametrize('path', [
    '/contracts/99999/print',
    '/invoices/99999/print',
    '/purchase-orders/99999/print',
])
def test_print_missing_document_404(client, path):
    login_as(client, 'admin')
    assert client.get(path).status_code == 404
