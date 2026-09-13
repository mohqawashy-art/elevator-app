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
            movement_type='صرف لفني',
            quantity=5,
            technician_id=tech.id,
        ))
        db.session.add(StockMovement(
            code='MV-C3',
            item_id=item.id,
            movement_date=date.today(),
            direction='وارد',
            movement_type='صرف عهدة للفني',
            quantity=2,
            technician_id=tech.id,
        ))
        db.session.commit()

        fields = item_custody_fields(item.id)
        assert fields['custody_qty'] == 3


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
