"""العقود المنتهية والزيارات والأعطال القديمة تظهر في القوائم الافتراضية."""
from datetime import date, datetime, timedelta

from models import Contract, ContractElevator, Customer, Elevator, Fault, MaintenanceVisit, db
from tests.conftest import ensure_test_organization, login_as


def _seed_old_and_new(client):
    login_as(client, 'admin')
    today = date.today()
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(
            organization_id=oid,
            code='C-ARCH',
            name='عيضة مسلم الحصيني',
            phone='0550000099',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(
            organization_id=oid,
            code='E-ARCH',
            customer_id=cust.id,
            status='نشط',
        )
        db.session.add(elev)
        db.session.flush()
        old = Contract(
            organization_id=oid,
            code='CN-ARCH-OLD',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=today - timedelta(days=800),
            end_date=today - timedelta(days=40),
            status='منتهي',
        )
        new = Contract(
            organization_id=oid,
            code='CN-ARCH-NEW',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=355),
            status='نشط',
        )
        db.session.add_all([old, new])
        db.session.flush()
        db.session.add_all([
            ContractElevator(organization_id=oid, contract_id=old.id, elevator_id=elev.id),
            ContractElevator(organization_id=oid, contract_id=new.id, elevator_id=elev.id),
        ])
        old_visit = MaintenanceVisit(
            organization_id=oid,
            code='VI-ARCH-OLD',
            elevator_id=elev.id,
            contract_id=old.id,
            visit_type='صيانة دورية',
            visit_date=today - timedelta(days=80),
            status='مكتملة',
        )
        new_visit = MaintenanceVisit(
            organization_id=oid,
            code='VI-ARCH-NEW',
            elevator_id=elev.id,
            contract_id=new.id,
            visit_type='صيانة دورية',
            visit_date=today,
            status='مجدولة',
        )
        live_old = MaintenanceVisit(
            organization_id=oid,
            code='VI-ARCH-LIVE',
            elevator_id=elev.id,
            contract_id=old.id,
            visit_type='صيانة دورية',
            visit_date=today - timedelta(days=5),
            status='مجدولة',
        )
        old_fault = Fault(
            organization_id=oid,
            code='FA-ARCH-OLD',
            elevator_id=elev.id,
            description='عطل على العقد القديم',
            status='مغلق',
            reported_at=datetime.combine(today - timedelta(days=90), datetime.min.time()),
        )
        open_fault = Fault(
            organization_id=oid,
            code='FA-ARCH-OPEN',
            elevator_id=elev.id,
            description='عطل مفتوح للمتابعة',
            status='مفتوح',
            reported_at=datetime.combine(today - timedelta(days=2), datetime.min.time()),
        )
        db.session.add_all([old_visit, new_visit, live_old, old_fault, open_fault])
        db.session.commit()


def test_expired_and_active_contracts_visible_by_default(client):
    _seed_old_and_new(client)
    page = client.get('/contracts?z=5')
    html = page.get_data(as_text=True)
    assert 'CN-ARCH-NEW' in html
    assert 'CN-ARCH-OLD' in html
    assert 'أرشيف العقود القديمة' not in html

    expired = client.get('/contracts?z=5&status=منتهي')
    expired_html = expired.get_data(as_text=True)
    assert 'CN-ARCH-OLD' in expired_html
    assert 'CN-ARCH-NEW' not in expired_html
    assert 'إخفاء العقود المنتهية' in html
    assert 'toggleHideExpiredContracts' in html


def test_hide_expired_contracts_button(client):
    _seed_old_and_new(client)
    hidden = client.get('/contracts?z=5&hide_expired=1')
    hidden_html = hidden.get_data(as_text=True)
    assert 'CN-ARCH-NEW' in hidden_html
    assert 'CN-ARCH-OLD' not in hidden_html
    assert 'إظهار العقود المنتهية' in hidden_html

    still = client.get('/contracts?z=5&hide_expired=1&status=منتهي')
    still_html = still.get_data(as_text=True)
    assert 'CN-ARCH-OLD' in still_html

    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer.query.filter_by(code='C-ARCH').first()
        renewed = Contract(
            organization_id=oid,
            code='CN-ARCH-REN',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date.today() - timedelta(days=400),
            end_date=date.today() - timedelta(days=10),
            status='تم تجديده',
        )
        db.session.add(renewed)
        db.session.commit()
    hidden_ren = client.get('/contracts?z=5&hide_expired=1')
    assert 'CN-ARCH-REN' not in hidden_ren.get_data(as_text=True)
    shown_ren = client.get('/contracts?z=5&hide_expired=0').get_data(as_text=True)
    assert 'CN-ARCH-REN' in shown_ren


def test_hide_expired_survives_leaving_the_page(client):
    _seed_old_and_new(client)
    hidden = client.get('/contracts?z=5&hide_expired=1')
    assert hidden.status_code == 200
    assert 'CN-ARCH-OLD' not in hidden.get_data(as_text=True)

    back = client.get('/contracts?z=5')
    back_html = back.get_data(as_text=True)
    assert 'CN-ARCH-NEW' in back_html
    assert 'CN-ARCH-OLD' not in back_html
    assert 'إظهار العقود المنتهية' in back_html

    shown = client.get('/contracts?z=5&hide_expired=0')
    shown_html = shown.get_data(as_text=True)
    assert 'CN-ARCH-OLD' in shown_html
    again = client.get('/contracts?z=5')
    assert 'CN-ARCH-OLD' in again.get_data(as_text=True)


def test_all_visits_visible_by_default(client):
    _seed_old_and_new(client)
    page = client.get('/maintenance-visits')
    html = page.get_data(as_text=True)
    assert 'VI-ARCH-NEW' in html
    assert 'VI-ARCH-LIVE' in html
    assert 'VI-ARCH-OLD' in html
    assert 'أرشيف العقود القديمة' not in html


def test_all_faults_visible_by_default(client):
    _seed_old_and_new(client)
    page = client.get('/faults')
    html = page.get_data(as_text=True)
    assert 'FA-ARCH-OPEN' in html
    assert 'FA-ARCH-OLD' in html
    assert 'أرشيف العقود القديمة' not in html


def test_contracts_sort_by_end_date(client):
    from app import sort_contracts_for_list

    _seed_old_and_new(client)
    today = date.today()
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer.query.filter_by(code='C-ARCH').first()
        older = Contract(
            organization_id=oid,
            code='CN-ARCH-OLDER',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=today - timedelta(days=1200),
            end_date=today - timedelta(days=400),
            status='منتهي',
        )
        db.session.add(older)
        db.session.commit()

    asc = client.get('/contracts?z=5&sort=end_date&dir=asc')
    asc_html = asc.get_data(as_text=True)
    assert asc_html.find('CN-ARCH-OLDER') < asc_html.find('CN-ARCH-OLD"')

    desc = client.get('/contracts?z=5&sort=end_date&dir=desc')
    desc_html = desc.get_data(as_text=True)
    assert desc_html.find('CN-ARCH-OLD"') < desc_html.find('CN-ARCH-OLDER')

    with client.application.app_context():
        rows = [
            Contract(code='CN-2', end_date=today - timedelta(days=10)),
            Contract(code='CN-1', end_date=today - timedelta(days=80)),
        ]
        ordered = sort_contracts_for_list(rows, 'end_date', 'asc')
        assert [c.code for c in ordered] == ['CN-1', 'CN-2']
        ordered = sort_contracts_for_list(rows, 'end_date', 'desc')
        assert [c.code for c in ordered] == ['CN-2', 'CN-1']


def test_contracts_page_size_in_list_meta(client):
    _seed_old_and_new(client)
    page = client.get('/contracts?z=5&per=20')
    html = page.get_data(as_text=True)
    assert '"per_page": 20' in html or '"per_page":20' in html
    default = client.get('/contracts?z=5')
    default_html = default.get_data(as_text=True)
    assert '"per_page": 10' in default_html or '"per_page":10' in default_html
