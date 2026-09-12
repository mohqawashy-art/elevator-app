"""اختبار منطقة موقع الخدمة من العقد."""
from datetime import date

from models import Contract, ContractElevator, Customer, Elevator, Organization, db
from operations import _elevators_for_maintenance_plan, list_districts
from maintenance_teams import (
    visit_site_district,
    visit_site_coordinates,
    visit_site_maps_link,
    _district_from_address,
)


def test_visit_site_district_prefers_contract_over_customer(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-SITE-01',
            name='عميل عنوان',
            district='حي العميل',
            city='مكة',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        contract = Contract(
            organization_id=org.id,
            code='CN-SITE-01',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            district='حي العقد',
            city='مكة',
            status='نشط',
        )
        db.session.add(contract)
        db.session.commit()

        assert visit_site_district(contract, None, cust) == 'حي العقد'


def test_visit_site_coordinates_from_contract(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-SITE-02',
            name='عميل GPS',
            lat='21.5',
            lng='39.9',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        contract = Contract(
            organization_id=org.id,
            code='CN-SITE-02',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            lat='21.41',
            lng='39.82',
            status='نشط',
        )
        db.session.add(contract)
        db.session.commit()

        coords = visit_site_coordinates(contract, None, cust)
        assert coords == (21.41, 39.82)


def test_visit_site_maps_link_uses_contract_coords(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-SITE-03',
            name='عميل',
            lat='21.5',
            lng='39.9',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        contract = Contract(
            organization_id=org.id,
            code='CN-SITE-03',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            lat='21.41',
            lng='39.82',
            status='نشط',
        )
        db.session.add(contract)
        db.session.commit()

        link = visit_site_maps_link(contract, None)
        assert '21.41' in link and '39.82' in link


def test_visit_site_district_from_contract_address_when_fields_empty(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-ADDR-01',
            name='عميل',
            district='حي العميل',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        contract = Contract(
            organization_id=org.id,
            code='CN-ADDR-01',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            address='9184 شارع 1 محبس الجن - محبس الجن - مكة',
            status='نشط',
        )
        db.session.add(contract)
        db.session.commit()

        assert _district_from_address(contract.address) == 'محبس الجن'
        assert visit_site_district(contract, None, cust) == 'محبس الجن'


def test_maintenance_plan_uses_contract_elevators_not_all_customer_elevators(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-PLAN-ELEV',
            name='عميل مصاعد',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        elev_on = Elevator(
            organization_id=org.id,
            customer_id=cust.id,
            code='EL-ON-01',
            building_name='مبنى العقد',
            status='نشط',
        )
        elev_off = Elevator(
            organization_id=org.id,
            customer_id=cust.id,
            code='EL-OFF-01',
            building_name='مبنى آخر',
            status='نشط',
        )
        db.session.add_all([elev_on, elev_off])
        db.session.flush()
        contract = Contract(
            organization_id=org.id,
            code='CN-PLAN-ELEV',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            district='حي العقد',
            status='نشط',
        )
        db.session.add(contract)
        db.session.flush()
        db.session.add(ContractElevator(contract_id=contract.id, elevator_id=elev_on.id))
        db.session.commit()

        rows = _elevators_for_maintenance_plan(contract)
        codes = {e.code for e in rows}
        assert codes == {'EL-ON-01'}


def test_list_districts_from_contract_not_customer(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-PLAN-01',
            name='عميل تخطيط',
            district='حي العميل',
            city='جدة',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        contract = Contract(
            organization_id=org.id,
            code='CN-PLAN-01',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            district='حي العقد',
            city='جدة',
            status='نشط',
        )
        db.session.add(contract)
        db.session.commit()

        districts = list_districts('2026-06')
        assert 'حي العقد' in districts
        assert 'حي العميل' not in districts
