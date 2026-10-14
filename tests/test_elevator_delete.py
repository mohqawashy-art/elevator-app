"""حذف المصعد يوضح العائق ويفك الربط الاختياري."""
from datetime import date

from models import (
    Contract,
    ContractElevator,
    Customer,
    Elevator,
    MaintenanceVisit,
    PartsBilling,
    db,
)
from tests.conftest import ensure_test_organization, login_as


def _site(code='ED'):
    oid = ensure_test_organization()
    cust = Customer(
        organization_id=oid,
        code=f'C-{code}',
        name=f'عميل {code}',
        status='نشط',
    )
    db.session.add(cust)
    db.session.flush()
    elev = Elevator(
        organization_id=oid,
        code=f'EL-{code}',
        customer_id=cust.id,
        status='خارج الخدمة',
    )
    db.session.add(elev)
    db.session.flush()
    return oid, cust, elev


def test_elevator_delete_blocked_when_visit_exists(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid, _cust, elev = _site('VIS')
        db.session.add(MaintenanceVisit(
            organization_id=oid,
            code='V-ED1',
            elevator_id=elev.id,
            visit_type='صيانة دورية',
            visit_date=date(2026, 10, 1),
            status='مكتملة',
        ))
        db.session.commit()
        elev_id = elev.id

    r = client.post(
        f'/elevators/delete/{elev_id}',
        json={'admin_password': 'TestPass123!'},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 409
    assert 'زيارة' in (r.get_json().get('message') or '')
    with client.application.app_context():
        assert db.session.get(Elevator, elev_id) is not None


def test_elevator_delete_clears_optional_links(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid, cust, elev = _site('OLD')
        contract = Contract(
            organization_id=oid,
            code='CN-ED01',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status='ملغي',
        )
        db.session.add(contract)
        db.session.flush()
        db.session.add(ContractElevator(
            organization_id=oid,
            contract_id=contract.id,
            elevator_id=elev.id,
        ))
        db.session.add(PartsBilling(
            organization_id=oid,
            code='PB-ED01',
            customer_id=cust.id,
            elevator_id=elev.id,
            billing_date=date(2026, 3, 1),
            description='بيان قديم',
        ))
        db.session.commit()
        elev_id = elev.id
        contract_id = contract.id

    r = client.post(
        f'/elevators/delete/{elev_id}',
        json={'admin_password': 'TestPass123!'},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 200
    assert r.get_json().get('ok') is True
    with client.application.app_context():
        assert db.session.get(Elevator, elev_id) is None
        assert ContractElevator.query.filter_by(elevator_id=elev_id).count() == 0
        leftover = PartsBilling.query.filter_by(code='PB-ED01').first()
        assert leftover is not None
        assert leftover.elevator_id is None
        assert db.session.get(Contract, contract_id) is not None
