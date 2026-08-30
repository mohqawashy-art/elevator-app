"""سداد قطع الغيار لا يُنقص المتبقي على عقد الصيانة."""
from datetime import date, timedelta

from billing_consistency import refresh_contract_cache
from customer_billing import contract_paid_amount, contract_remaining, revenue_counts_toward_contract
from models import Contract, Customer, PartsBilling, Revenue, db


def _seed_unpaid_contract_and_parts():
    cust = Customer(code='C-PB01', name='عميل قطع ودين قديم', phone='512222222', status='نشط')
    db.session.add(cust)
    db.session.flush()
    today = date.today()
    contract = Contract(
        code='CN-PB01',
        customer_id=cust.id,
        contract_type='صيانة',
        start_date=today - timedelta(days=200),
        end_date=today + timedelta(days=160),
        total=3000,
        paid_amount=0,
        status='نشط',
        invoice_status='غير مدفوع',
    )
    db.session.add(contract)
    db.session.flush()
    pb = PartsBilling(
        code='PB-PB01',
        customer_id=cust.id,
        contract_id=contract.id,
        billing_date=today,
        description='انتر كوم',
        sell_price=150,
        paid_amount=0,
        status='غير محصل',
    )
    db.session.add(pb)
    db.session.commit()
    return cust.id, contract.id, pb.id


def test_parts_revenue_does_not_count_toward_old_contract(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        cust_id, contract_id, pb_id = _seed_unpaid_contract_and_parts()
        pb = db.session.get(PartsBilling, pb_id)
        rev = Revenue(
            code='REV-PB01',
            customer_id=cust_id,
            contract_id=contract_id,
            parts_billing_id=pb_id,
            revenue_date=date.today(),
            revenue_type='قطع غيار',
            amount=130.43,
            tax_amount=19.57,
            total=150,
            status='محصّل',
            reference=pb.code,
            notes=f'تحصيل قطع {pb.code}',
        )
        db.session.add(rev)
        pb.paid_amount = 150
        pb.status = 'محصل'
        db.session.commit()

        assert revenue_counts_toward_contract(rev) is False
        assert contract_paid_amount(contract_id) == 0
        remaining = contract_remaining(db.session.get(Contract, contract_id))
        assert remaining == 3000

        contract = db.session.get(Contract, contract_id)
        refresh_contract_cache(contract)
        db.session.commit()
        assert (contract.paid_amount or 0) == 0
        assert (db.session.get(PartsBilling, pb_id).paid_amount or 0) == 150


def test_parts_type_without_source_still_excluded_from_contract(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        cust_id, contract_id, _ = _seed_unpaid_contract_and_parts()
        rev = Revenue(
            code='REV-PBX1',
            customer_id=cust_id,
            contract_id=contract_id,
            revenue_date=date.today(),
            revenue_type='قطع غيار',
            amount=130.43,
            tax_amount=19.57,
            total=150,
            status='محصّل',
            notes='تحصيل قطع — عقد CN-PB01',
        )
        db.session.add(rev)
        db.session.commit()
        assert contract_paid_amount(contract_id) == 0
        assert contract_remaining(db.session.get(Contract, contract_id)) == 3000
