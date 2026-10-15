"""نوافذ القوائم: قراءة على دفعات دون حذف أو تعديل الصفوف القديمة."""
from datetime import date

from list_windows import request_export_all, request_per_page
from models import Customer, Elevator, Fault, Invoice, MaintenanceVisit, db
from tests.conftest import ensure_test_organization, login_as


def test_request_per_page_allows_10_20_50_100():
    assert request_per_page({}) == 10
    assert request_per_page({'per': '10'}) == 10
    assert request_per_page({'per': '20'}) == 20
    assert request_per_page({'per': '50'}) == 50
    assert request_per_page({'per': '100'}) == 100
    assert request_per_page({'per': '7'}) == 10
    assert request_per_page({'per': 'all'}) == 10
    assert request_export_all({}) is False
    assert request_export_all({'export': '1'}) is True
    assert request_export_all({'export': 'all'}) is True


def _oid():
    return ensure_test_organization()


def _site(code_suffix='LW'):
    oid = _oid()
    cust = Customer(
        organization_id=oid,
        code=f'C-{code_suffix}',
        name=f'عميل {code_suffix}',
        phone='0550000000',
        status='نشط',
    )
    db.session.add(cust)
    db.session.flush()
    elev = Elevator(
        organization_id=oid,
        code=f'E-{code_suffix}',
        customer_id=cust.id,
        status='نشط',
    )
    db.session.add(elev)
    db.session.flush()
    return oid, cust, elev


def _shift_month(day: date, delta: int) -> date:
    month = day.month - 1 + delta
    year = day.year + month // 12
    month = month % 12 + 1
    return date(year, month, 15)


def test_visits_page_shows_all_months_by_default(client):
    login_as(client, 'admin')
    today = date.today()
    previous = _shift_month(today, -1)
    older = _shift_month(today, -2)
    prev_label = f'{previous.year:04d}-{previous.month:02d}'
    with client.application.app_context():
        oid, _cust, elev = _site('VIS')
        done_other = MaintenanceVisit(
            organization_id=oid,
            code='V-PREV-DONE',
            elevator_id=elev.id,
            visit_type='صيانة دورية',
            visit_date=previous,
            status='مكتملة',
        )
        open_other = MaintenanceVisit(
            organization_id=oid,
            code='V-OLD-OPEN',
            elevator_id=elev.id,
            visit_type='صيانة دورية',
            visit_date=older,
            status='مجدولة',
        )
        done_now = MaintenanceVisit(
            organization_id=oid,
            code='V-NOW-DONE',
            elevator_id=elev.id,
            visit_type='صيانة دورية',
            visit_date=date(today.year, today.month, 2),
            status='مكتملة',
        )
        db.session.add_all([done_other, open_other, done_now])
        db.session.commit()

    page = client.get('/maintenance-visits')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'V-NOW-DONE' in html
    assert 'V-OLD-OPEN' in html
    assert 'V-PREV-DONE' in html

    september = client.get(f'/maintenance-visits?month={prev_label}')
    sep_html = september.get_data(as_text=True)
    assert 'V-PREV-DONE' in sep_html
    assert 'V-OLD-OPEN' in sep_html
    assert 'V-NOW-DONE' not in sep_html

    month_only = client.get(f'/api/maintenance/visits?month={prev_label}')
    codes = [row['code'] for row in month_only.get_json()['visits']]
    assert 'V-PREV-DONE' in codes
    assert 'V-OLD-OPEN' not in codes

    live = client.get(f'/api/maintenance/visits?month={prev_label}&live=1')
    live_codes = [row['code'] for row in live.get_json()['visits']]
    assert 'V-PREV-DONE' in live_codes
    assert 'V-OLD-OPEN' in live_codes

    sync = client.get('/api/live/sync?page=maintenance-visits')
    sync_codes = [row['code'] for row in sync.get_json()['data']['VISITS']]
    assert 'V-NOW-DONE' in sync_codes
    assert 'V-OLD-OPEN' in sync_codes
    assert 'V-PREV-DONE' in sync_codes


def test_faults_default_shows_open_and_closed(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid, _cust, elev = _site('FLT')
        db.session.add(Fault(
            organization_id=oid, code='FA-OPEN', elevator_id=elev.id,
            description='عطل مفتوح', status='مفتوح',
        ))
        db.session.add(Fault(
            organization_id=oid, code='FA-CLOSED', elevator_id=elev.id,
            description='عطل مغلق', status='مغلق',
        ))
        db.session.commit()

    all_page = client.get('/faults')
    assert all_page.status_code == 200
    all_html = all_page.get_data(as_text=True)
    assert 'FA-OPEN' in all_html
    assert 'FA-CLOSED' in all_html
    assert 'سجل الأعطال كاملاً' not in all_html

    open_only = client.get('/faults?scope=open')
    open_html = open_only.get_data(as_text=True)
    assert 'FA-OPEN' in open_html
    assert 'FA-CLOSED' not in open_html

    sync = client.get('/api/live/sync?page=faults')
    sync_codes = [row['code'] for row in sync.get_json()['data']['FAULTS']]
    assert 'FA-OPEN' in sync_codes
    assert 'FA-CLOSED' in sync_codes


def test_clients_search_returns_the_match_only(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = _oid()
        db.session.add(Customer(
            organization_id=oid, code='C-ALPHA', name='عميل نافذة ألف',
            phone='0551111111', status='نشط',
        ))
        db.session.add(Customer(
            organization_id=oid, code='C-BETA', name='عميل نافذة باء',
            phone='0552222222', status='نشط',
        ))
        db.session.commit()

    page = client.get('/clients', query_string={'q': 'ألف'})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'C-ALPHA' in html
    assert 'C-BETA' not in html
    assert '"server": true' in html or '"server":true' in html


def test_live_sync_export_returns_all_clients_not_just_the_page(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = _oid()
        for n in range(12):
            db.session.add(Customer(
                organization_id=oid,
                code=f'C-EX{n:02d}',
                name=f'عميل تصدير {n:02d}',
                phone=f'05530000{n:02d}',
                status='نشط',
            ))
        db.session.commit()

    page = client.get('/api/live/sync?page=clients')
    export = client.get('/api/live/sync?page=clients&export=1')
    assert page.status_code == 200
    assert export.status_code == 200
    page_codes = {row['code'] for row in page.get_json()['data']['CUSTOMERS']}
    export_codes = {row['code'] for row in export.get_json()['data']['CUSTOMERS']}
    seeded = {f'C-EX{n:02d}' for n in range(12)}
    assert len(page.get_json()['data']['CUSTOMERS']) <= 10
    assert not seeded <= page_codes
    assert seeded <= export_codes


def test_clients_page_includes_customers_with_many_elevators(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = _oid()
        first = Customer(organization_id=oid, code='C-PLAIN1', name='عميل صفحة واحد', status='نشط')
        second = Customer(organization_id=oid, code='C-PLAIN2', name='عميل صفحة اثنان', status='نشط')
        heavy = Customer(organization_id=oid, code='C-HEAVY', name='عميل مصاعد كثيرة', status='نشط')
        db.session.add_all([first, second, heavy])
        db.session.flush()
        for n in range(55):
            db.session.add(Elevator(
                organization_id=oid,
                code=f'E-HV-{n:02d}',
                customer_id=heavy.id,
                status='نشط',
            ))
        db.session.commit()

    page = client.get('/clients')
    html = page.get_data(as_text=True)
    assert 'C-HEAVY' in html
    assert 'C-PLAIN1' in html
    assert 'C-PLAIN2' in html


def test_dashboard_invoice_totals_ignore_vouchers(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = _oid()
        db.session.add(Invoice(
            organization_id=oid,
            code='INV-TAX-1',
            invoice_type='فاتورة ضريبية',
            invoice_date=date(2026, 10, 1),
            amount=1000,
            total=1000,
            paid_amount=0,
        ))
        db.session.add(Invoice(
            organization_id=oid,
            code='RV-1',
            invoice_type='سند قبض',
            invoice_date=date(2026, 10, 1),
            amount=5000,
            total=5000,
            paid_amount=5000,
        ))
        db.session.commit()

    page = client.get('/dashboard')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    marker = html.find('إجمالي الفواتير')
    assert marker > 0
    snippet = html[marker:marker + 350]
    assert '1,000' in snippet
    assert '6,000' not in snippet
