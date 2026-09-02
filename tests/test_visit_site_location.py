"""اختبار منطقة موقع الخدمة من العقد."""
from models import Contract, Customer, Organization, db
from maintenance_teams import visit_site_district, visit_site_coordinates


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
            start_date=__import__('datetime').date(2026, 1, 1),
            end_date=__import__('datetime').date(2027, 1, 1),
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
            start_date=__import__('datetime').date(2026, 1, 1),
            end_date=__import__('datetime').date(2027, 1, 1),
            lat='21.41',
            lng='39.82',
            status='نشط',
        )
        db.session.add(contract)
        db.session.commit()

        coords = visit_site_coordinates(contract, None, cust)
        assert coords == (21.41, 39.82)
