"""خصم قطع الغيار وحالة «على حساب الشركة»."""
from __future__ import annotations

import json

from customer_billing import UNPAID_PARTS_STATUSES, parts_remaining
from models import Customer, Elevator, Fault, InventoryItem, PartsBilling, StockMovement, Technician, db
from operations import (
    COMPANY_ACCOUNT_STATUS,
    apply_fault_parts_billing,
    apply_parts_company_account_status,
    format_fault_parts_description,
    parse_fault_parts_lines,
    parts_billing_record_lines,
    parts_line_discount,
    parts_line_net,
    parts_lines_totals,
)

from tests.conftest import ensure_test_organization, login_as


def test_parts_line_discount_caps_at_gross():
    ln = {'qty': 2, 'unit_price': 100, 'discount': 500, 'cost_price': 40}
    assert parts_line_discount(ln) == 200
    assert parts_line_net(ln) == 0
    sell, cost, disc = parts_lines_totals([ln])
    assert sell == 0
    assert disc == 200
    assert cost == 80


def test_parts_line_partial_discount():
    ln = {'qty': 1, 'unit_price': 200, 'discount': 50, 'cost_price': 80}
    assert parts_line_net(ln) == 150
    sell, _cost, disc = parts_lines_totals([ln])
    assert sell == 150
    assert disc == 50


def test_parse_fault_parts_lines_keeps_discount(client):
    with client.application.app_context():
        lines = parse_fault_parts_lines(json.dumps([{
            'name': 'انتركم',
            'qty': 1,
            'unit_price': 150,
            'discount': 150,
            'cost_price': 50,
        }]))
        assert len(lines) == 1
        assert lines[0]['discount'] == 150
        assert parts_line_net(lines[0]) == 0
        desc = format_fault_parts_description(lines)
        assert 'خصم' in desc


def test_company_account_status_from_zero_sell():
    pb = PartsBilling(status='غير محصل', sell_price=0)
    apply_parts_company_account_status(pb)
    assert pb.status == COMPANY_ACCOUNT_STATUS
    pb.sell_price = 80
    apply_parts_company_account_status(pb)
    assert pb.status == 'غير محصل'


def test_fault_company_account_deducts_stock_and_not_collectible(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid, code='T-DS1', name='فني خصم',
            phone='0501110001', team='صيانة', status='متاح',
        )
        cust = Customer(organization_id=oid, code='C-DS1', name='عميل خصم', status='نشط')
        db.session.add_all([tech, cust])
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-DS1', customer_id=cust.id, status='نشط')
        item = InventoryItem(
            organization_id=oid, code='IT-DS1', name='لوحة أبواب',
            unit='قطعة', current_qty=5, buy_price=40, sell_price=120,
        )
        db.session.add_all([elev, item])
        db.session.flush()
        fault = Fault(
            organization_id=oid, code='FA-DS01', elevator_id=elev.id,
            technician_id=tech.id, fault_type='عطل أبواب', status='مفتوح',
        )
        db.session.add(fault)
        db.session.commit()

        lines = parse_fault_parts_lines(json.dumps([{
            'item_id': item.id,
            'name': item.name,
            'qty': 1,
            'unit_price': 120,
            'discount': 120,
            'cost_price': 40,
        }]))
        pb = apply_fault_parts_billing(fault, lines, technician_id=fault.technician_id)
        fault.needs_parts = True
        if pb and pb.status == COMPANY_ACCOUNT_STATUS:
            fault.billed = True
        db.session.commit()

        assert pb is not None
        assert pb.status == COMPANY_ACCOUNT_STATUS
        assert pb.sell_price == 0
        assert (item.current_qty or 0) == 4
        assert parts_remaining(pb) <= 0.01
        assert pb.status not in UNPAID_PARTS_STATUSES
        moves = StockMovement.query.filter_by(item_id=item.id).all()
        assert any(m.direction == 'صادر' for m in moves)

        from billing_consistency import refresh_parts_cache
        refresh_parts_cache(pb)
        db.session.commit()
        assert pb.status == COMPANY_ACCOUNT_STATUS


def test_fault_add_company_account_via_form(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid, code='T-DS2', name='فني نموذج',
            phone='0501110002', team='صيانة', status='متاح',
        )
        cust = Customer(organization_id=oid, code='C-DS2', name='عميل نموذج', status='نشط')
        db.session.add_all([tech, cust])
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-DS2', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.commit()
        tech_id, elev_id = tech.id, elev.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    r = client.post(
        '/faults/add',
        data={
            'csrf_token': 'test-csrf',
            'elevator_id': str(elev_id),
            'technician_ids': str(tech_id),
            'technician_id': str(tech_id),
            'fault_type': 'عطل',
            'priority': 'عادية',
            'client_report': 'تركيب مجاني',
            'billable': 'yes',
            'parts_lines': json.dumps([{
                'name': 'زر استدعاء',
                'qty': 1,
                'unit_price': 90,
                'discount': 120,
                'cost_price': 20,
            }]),
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    with client.application.app_context():
        f = Fault.query.filter_by(elevator_id=elev_id).order_by(Fault.id.desc()).first()
        assert f is not None
        assert f.needs_parts is True
        assert f.billed is True
        pb = PartsBilling.query.filter_by(fault_id=f.id).first()
        assert pb is not None
        assert pb.status == COMPANY_ACCOUNT_STATUS
        assert pb.sell_price == 0
        stored = parts_billing_record_lines(pb)
        assert stored and float(stored[0].get('discount') or 0) == 90
