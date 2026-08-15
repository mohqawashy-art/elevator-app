"""سداد عقد مجدّد لا يُنسب للعقد الأساسي القديم."""
from datetime import date, timedelta

from billing_consistency import refresh_contract_cache
from customer_billing import (
    _extract_contract_code,
    _text_mentions_exact_contract_code,
    contract_paid_amount,
    resolve_contract_id,
)
from models import Contract, Customer, Revenue, db


def _seed_renewal_pair():
    cust = Customer(code='C-RN01', name='عميل تجديد سداد', phone='511111111', status='نشط')
    db.session.add(cust)
    db.session.flush()
    today = date.today()
    old = Contract(
        code='CN-00002',
        customer_id=cust.id,
        contract_type='صيانة',
        start_date=today - timedelta(days=400),
        end_date=today + timedelta(days=30),  # ما زال ظاهرياً ساري بالخطأ
        total=2300,
        paid_amount=0,
        status='تم تجديده',
        invoice_status='غير مدفوع',
    )
    renew = Contract(
        code='CN-00002-2026',
        customer_id=cust.id,
        contract_type='صيانة',
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=355),
        total=2300,
        paid_amount=0,
        status='نشط',
        invoice_status='غير مدفوع',
    )
    db.session.add_all([old, renew])
    db.session.commit()
    return cust.id, old.id, renew.id


def test_extract_prefers_renewal_year_suffix():
    assert _extract_contract_code('تحصيل عقد CN-00002-2026') == 'CN-00002-2026'
    assert _extract_contract_code('CN-00002') == 'CN-00002'
    assert not _text_mentions_exact_contract_code('تحصيل عقد CN-00002-2026', 'CN-00002')
    assert _text_mentions_exact_contract_code('تحصيل عقد CN-00002-2026', 'CN-00002-2026')


def test_resolve_links_to_renewal_not_base(client):
    with client.application.app_context():
        cust_id, old_id, renew_id = _seed_renewal_pair()
        linked = resolve_contract_id(
            cust_id,
            '',
            f'تحصيل عقد CN-00002-2026',
            '',
            'تجديد عقد',
        )
        assert linked == renew_id
        assert linked != old_id


def test_paid_amount_not_attributed_to_superseded_base(client):
    with client.application.app_context():
        cust_id, old_id, renew_id = _seed_renewal_pair()
        rev = Revenue(
            code='REV-RN01',
            customer_id=cust_id,
            contract_id=renew_id,
            revenue_date=date.today(),
            revenue_type='تجديد عقد',
            amount=2000,
            tax_amount=300,
            total=2300,
            status='محصّل',
            notes='تحصيل عقد CN-00002-2026',
            reference='تحصيل عقد CN-00002-2026',
        )
        db.session.add(rev)
        db.session.commit()

        assert contract_paid_amount(renew_id) == 2300
        assert contract_paid_amount(old_id) == 0

        old = db.session.get(Contract, old_id)
        renew = db.session.get(Contract, renew_id)
        refresh_contract_cache(old)
        refresh_contract_cache(renew)
        db.session.commit()

        assert float(renew.paid_amount or 0) == 2300
        assert float(old.paid_amount or 0) == 0


def test_orphan_revenue_mentions_renewal_not_base(client):
    with client.application.app_context():
        cust_id, old_id, renew_id = _seed_renewal_pair()
        rev = Revenue(
            code='REV-RN02',
            customer_id=cust_id,
            contract_id=None,
            revenue_date=date.today(),
            revenue_type='تجديد عقد',
            amount=2000,
            tax_amount=300,
            total=2300,
            status='محصّل',
            notes='تحصيل عقد CN-00002-2026',
        )
        db.session.add(rev)
        db.session.commit()

        assert contract_paid_amount(renew_id) == 2300
        assert contract_paid_amount(old_id) == 0
        assert resolve_contract_id(cust_id, '', rev.notes, '', rev.revenue_type) == renew_id
