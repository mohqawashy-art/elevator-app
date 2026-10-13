"""أعمار الذمم: جاري ثم 30 و60 و90 وأكثر، بدون تكرار العقد مع فاتورته."""
from datetime import date

from flask import g

from customer_billing import build_ar_aging
from models import Contract, Customer, Invoice, Organization, PartsBilling, db
from tests.conftest import login_as


def test_aging_buckets_and_invoice_replaces_contract(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        g.organization_id = org.id
        g.organization = org

        late = Customer(code='C-AGE1', name='متأخر', phone='500000001', status='نشط', organization_id=org.id)
        fresh = Customer(code='C-AGE2', name='جاري', phone='500000002', status='نشط', organization_id=org.id)
        db.session.add_all([late, fresh])
        db.session.flush()

        db.session.add(Contract(
            code='CN-AGE1',
            customer_id=late.id,
            contract_type='صيانة',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            due_date=date(2025, 6, 1),
            total=1000,
            status='نشط',
            organization_id=org.id,
        ))
        covered = Contract(
            code='CN-AGE2',
            customer_id=fresh.id,
            contract_type='صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            due_date=date(2026, 1, 1),
            total=5000,
            status='نشط',
            organization_id=org.id,
        )
        db.session.add(covered)
        db.session.flush()
        db.session.add(Invoice(
            code='INV-AGE2',
            invoice_type='فاتورة ضريبية',
            customer_id=fresh.id,
            contract_id=covered.id,
            invoice_date=date(2026, 8, 1),
            due_date=date(2026, 9, 1),
            amount=200,
            tax_amount=0,
            total=230,
            paid_amount=0,
            status='غير مدفوعة',
            organization_id=org.id,
        ))
        db.session.add(PartsBilling(
            code='PB-AGE1',
            customer_id=late.id,
            billing_date=date(2026, 8, 20),
            sell_price=50,
            paid_amount=0,
            status='غير محصل',
            organization_id=org.id,
        ))
        db.session.commit()

        report = build_ar_aging(date(2026, 10, 13))
        by_name = {row['customer']: row for row in report['customers']}
        assert by_name['متأخر']['over'] == 1000
        assert by_name['متأخر']['d60'] == 50
        assert by_name['متأخر']['total'] == 1050
        assert by_name['جاري']['d60'] == 230
        assert by_name['جاري']['total'] == 230
        assert report['totals']['total'] == 1280
        codes = {doc['code'] for doc in report['documents']}
        assert 'CN-AGE2' not in codes
        assert 'INV-AGE2' in codes

        current = build_ar_aging(date(2025, 5, 1))
        early = {row['customer']: row for row in current['customers']}
        assert early['متأخر']['current'] == 1000
        assert early['متأخر']['over'] == 0

    login_as(client, 'admin')
    page = client.get('/reports/ar-aging?as_of=2026-10-13')
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'أعمار الذمم' in body
    assert '1,050.00' in body or '1050.00' in body
