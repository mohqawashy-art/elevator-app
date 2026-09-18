"""عهدة قطع الغيار — من حركات المخزون."""
from datetime import date

from inventory_custody import build_technician_custody_snapshot, item_custody_fields
from models import InventoryItem, StockMovement, Technician, db


def _seed_item_and_tech():
    tech = Technician(code='T-C1', name='فني عهدة', status='نشط')
    db.session.add(tech)
    db.session.flush()
    item = InventoryItem(code='#C1', name='بطارية', category='قطع غيار', current_qty=10)
    db.session.add(item)
    db.session.flush()
    return item, tech


def test_custody_from_outbound_movement(client):
    with client.application.app_context():
        item, tech = _seed_item_and_tech()
        m = StockMovement(
            code='MV-C1',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف عهدة للفني',
            quantity=4,
            unit_price=10,
            total_value=40,
            technician_id=tech.id,
        )
        db.session.add(m)
        db.session.commit()

        snap = build_technician_custody_snapshot()
        fields = item_custody_fields(item.id, snap)
        assert fields['custody_qty'] == 4
        assert len(fields['custody_techs']) == 1
        assert fields['custody_techs'][0]['technician_name'] == 'فني عهدة'
        assert 'فني عهدة' in fields['custody_summary']


def test_custody_net_after_return(client):
    with client.application.app_context():
        item, tech = _seed_item_and_tech()
        db.session.add(StockMovement(
            code='MV-C2',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف عهدة للفني',
            quantity=5,
            technician_id=tech.id,
        ))
        db.session.add(StockMovement(
            code='MV-C3',
            item_id=item.id,
            movement_date=date.today(),
            direction='وارد',
            movement_type='إرجاع عهدة للمخزن',
            quantity=2,
            technician_id=tech.id,
        ))
        db.session.commit()

        fields = item_custody_fields(item.id)
        assert fields['custody_qty'] == 3


def test_direct_issue_to_technician_not_custody(client):
    with client.application.app_context():
        item, tech = _seed_item_and_tech()
        db.session.add(StockMovement(
            code='MV-C5',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف لفني',
            quantity=6,
            technician_id=tech.id,
        ))
        db.session.commit()
        assert item_custody_fields(item.id)['custody_qty'] == 0


def test_consumable_custody_issue_ignored(client):
    with client.application.app_context():
        tech = Technician(code='T-C2', name='فني مستهلكات', status='نشط')
        db.session.add(tech)
        db.session.flush()
        item = InventoryItem(
            code='#C2',
            name='زيت تشحيم',
            category='مستهلكات',
            current_qty=10,
        )
        db.session.add(item)
        db.session.flush()
        db.session.add(StockMovement(
            code='MV-C6',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف عهدة للفني',
            quantity=3,
            technician_id=tech.id,
        ))
        db.session.commit()
        assert item_custody_fields(item.id)['custody_qty'] == 0


def test_non_custody_movement_ignored(client):
    with client.application.app_context():
        item, tech = _seed_item_and_tech()
        db.session.add(StockMovement(
            code='MV-C4',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف لمشروع / عميل',
            quantity=9,
            technician_id=tech.id,
        ))
        db.session.commit()
        assert item_custody_fields(item.id)['custody_qty'] == 0


def test_settle_custody_to_warehouse(client):
    with client.application.app_context():
        item, tech = _seed_item_and_tech()
        db.session.add(StockMovement(
            code='MV-S1',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف عهدة للفني',
            quantity=5,
            technician_id=tech.id,
        ))
        item.current_qty = 5
        db.session.commit()

        from inventory_custody import settle_technician_custody

        settle_technician_custody(
            item_id=item.id,
            technician_id=tech.id,
            quantity=2,
            target='warehouse',
        )
        db.session.commit()
        db.session.refresh(item)

        assert item.current_qty == 7
        assert item_custody_fields(item.id)['custody_qty'] == 3


def test_settle_custody_to_client(client):
    with client.application.app_context():
        from models import Contract, Customer

        item, tech = _seed_item_and_tech()
        cust = Customer(code='C-C1', name='عميل صيانة', status='نشط')
        db.session.add(cust)
        db.session.flush()
        contract = Contract(
            code='CN-C1',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date.today(),
            end_date=date.today(),
            maint_frequency='شهري',
            status='نشط',
        )
        db.session.add(contract)
        db.session.add(StockMovement(
            code='MV-S2',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف عهدة للفني',
            quantity=4,
            technician_id=tech.id,
        ))
        item.current_qty = 6
        db.session.commit()

        from inventory_custody import settle_technician_custody

        movement = settle_technician_custody(
            item_id=item.id,
            technician_id=tech.id,
            quantity=3,
            target='client',
            contract_id=contract.id,
        )
        db.session.commit()
        db.session.refresh(item)

        assert item.current_qty == 6
        assert item_custody_fields(item.id)['custody_qty'] == 1
        assert 'CN-C1' in (movement.reason or '')
        assert movement.reference == f'custody:maint:{contract.id}'


def test_custody_settle_api(client):
    from tests.conftest import login_as

    login_as(client, role='admin')
    with client.application.app_context():
        from models import Contract, Customer

        item, tech = _seed_item_and_tech()
        cust = Customer(code='C-API', name='عميل API', status='نشط')
        db.session.add(cust)
        db.session.flush()
        contract = Contract(
            code='CN-API',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date.today(),
            end_date=date.today(),
            maint_frequency='شهري',
            status='نشط',
        )
        db.session.add(contract)
        db.session.add(StockMovement(
            code='MV-S3',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف عهدة للفني',
            quantity=2,
            technician_id=tech.id,
        ))
        db.session.commit()
        item_id, tech_id, contract_id = item.id, tech.id, contract.id

    r = client.post(
        '/inventory/custody/settle',
        json={
            'item_id': item_id,
            'technician_id': tech_id,
            'quantity': 1,
            'target': 'client',
            'contract_id': contract_id,
        },
    )
    assert r.status_code == 200
    assert r.get_json()['ok'] is True


def test_filter_custody_rows():
    from inventory_custody import custody_report_summary, filter_custody_rows

    rows = [
        {'item_id': 1, 'item_code': '#101', 'item_name': 'مفتاح', 'technician_id': 10, 'technician_name': 'أحمد', 'qty': 2},
        {'item_id': 2, 'item_code': '#202', 'item_name': 'سلك', 'technician_id': 11, 'technician_name': 'خالد', 'qty': 1},
    ]
    by_tech = filter_custody_rows(rows, technician_id=10)
    assert len(by_tech) == 1
    assert by_tech[0]['item_code'] == '#101'
    by_q = filter_custody_rows(rows, q='سلك')
    assert len(by_q) == 1
    assert by_q[0]['technician_name'] == 'خالد'
    summary = custody_report_summary(by_tech)
    assert summary['line_count'] == 1
    assert summary['total_qty'] == 2


def test_custody_print_route(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item, tech = _seed_item_and_tech()
        db.session.add(StockMovement(
            code='MV-CPR',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف عهدة للفني',
            quantity=3,
            technician_id=tech.id,
        ))
        db.session.commit()
        tech_id = tech.id

    r = client.get(f'/inventory/custody/print?technician_id={tech_id}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'بيان عهدة قطع الغيار' in html
    assert tech.name in html


def test_custody_transfer_print_preview(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        item, tech = _seed_item_and_tech()
        db.session.commit()
        item_id, tech_id = item.id, tech.id

    r = client.get(
        '/inventory/custody/transfer/print'
        f'?item_id={item_id}&technician_id={tech_id}&target=warehouse'
        f'&quantity=2&movement_date={date.today().isoformat()}&draft=1'
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'إذن إرجاع عهدة للمخزن' in html
    assert 'مسودة' in html


def test_custody_transfer_print_movement(client):
    from tests.conftest import login_as
    from inventory_custody import settle_technician_custody

    login_as(client, 'admin')
    with client.application.app_context():
        item, tech = _seed_item_and_tech()
        db.session.add(StockMovement(
            code='MV-CP2',
            item_id=item.id,
            movement_date=date.today(),
            direction='صادر',
            movement_type='صرف عهدة للفني',
            quantity=3,
            technician_id=tech.id,
        ))
        db.session.commit()
        movement = settle_technician_custody(
            item_id=item.id,
            technician_id=tech.id,
            quantity=1,
            target='warehouse',
        )
        db.session.commit()
        movement_id = movement.id

    r = client.get(f'/inventory/custody/transfer/print?movement_id={movement_id}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert movement.code in html
    assert 'إرجاع عهدة للمخزن' in html
