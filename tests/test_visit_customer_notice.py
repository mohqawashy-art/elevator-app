"""رسائل واتساب العميل: تذكير زيارة الغد، ورسالة بعد انتهاء الصيانة."""
from datetime import date
from urllib.parse import unquote

from models import Customer, Elevator, MaintenanceVisit, Settings, Technician, db
from operations import (
    build_periodic_visit_done_message,
    build_periodic_visit_eve_message,
    visit_customer_notice_whatsapp,
)
from tests.conftest import ensure_test_organization


def _seed(*, phone='0555123456', visit_type='صيانة دورية', status='مجدولة', visit_day=None, building='', suffix='VN'):
    oid = ensure_test_organization()
    settings = Settings.query.filter_by(organization_id=oid).first()
    if not settings:
        settings = Settings(
            organization_id=oid,
            company_name='تقنية جما التميز للمصاعد',
            phone='0509988776',
        )
        db.session.add(settings)
    else:
        settings.company_name = 'تقنية جما التميز للمصاعد'
        settings.phone = '0509988776'
    tech = Technician(organization_id=oid, code=f'T-{suffix}', name='فني رسالة', phone='0501111111')
    db.session.add(tech)
    cust = Customer(
        organization_id=oid,
        code=f'C-{suffix}',
        name='عميل رسالة',
        phone=phone,
        status='نشط',
    )
    db.session.add(cust)
    db.session.flush()
    elev = Elevator(
        organization_id=oid,
        code=f'E-{suffix}',
        customer_id=cust.id,
        status='نشط',
        building_name=building or None,
    )
    db.session.add(elev)
    db.session.flush()
    visit = MaintenanceVisit(
        organization_id=oid,
        code=f'V-{suffix}1',
        elevator_id=elev.id,
        technician_id=tech.id,
        visit_type=visit_type,
        visit_date=visit_day or date(2026, 10, 4),
        status=status,
    )
    db.session.add(visit)
    db.session.commit()
    return visit.id, tech.id


def test_eve_message_matches_jama_wording(client):
    with client.application.app_context():
        visit_id, _tech_id = _seed(visit_day=date(2026, 10, 4))
        visit = db.session.get(MaintenanceVisit, visit_id)
        msg = build_periodic_visit_eve_message(visit, company_name='تقنية جما التميز للمصاعد')
    assert 'عميلنا العزيز' in msg
    assert 'غدا الأحد' in msg
    assert 'الموافق ٢٠٢٦/١٠/٤ م' in msg
    assert 'تسهيل أمر فريق الصيانه' in msg
    assert msg.endswith('شركة تقنية جما التميز للمصاعد')


def test_done_message_includes_company_phone(client):
    msg = build_periodic_visit_done_message(
        company_name='تقنية جما التميز للمصاعد',
        contact_phone='0509988776',
    )
    assert 'تم عمل الصيانه الدوريه لمصعدكم اليوم' in msg
    assert 'نحوز على رضاكم' in msg
    assert '0509988776' in msg
    assert msg.endswith('شركة تقنية جما التميز للمصاعد')


def test_finish_at_client_returns_done_whatsapp(client):
    with client.application.app_context():
        visit_id, tech_id = _seed(status='عند العميل')
    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id
    res = client.post(
        f'/api/maintenance-visits/{visit_id}/report',
        json={'mark_finished_at_client': True},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data['ok'] is True
    url = data.get('customer_whatsapp_url') or ''
    assert url.startswith('https://wa.me/')
    text = unquote(url.split('text=', 1)[-1])
    assert 'تم عمل الصيانه الدوريه' in text
    assert '0509988776' in text


def test_second_finish_does_not_repeat_whatsapp(client):
    with client.application.app_context():
        visit_id, tech_id = _seed(status='عند العميل')
    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id
    first = client.post(
        f'/api/maintenance-visits/{visit_id}/report',
        json={'mark_finished_at_client': True},
    )
    assert first.get_json().get('customer_whatsapp_url')
    second = client.post(
        f'/api/maintenance-visits/{visit_id}/report',
        json={'mark_finished_at_client': True},
    )
    assert second.status_code == 200
    assert not second.get_json().get('customer_whatsapp_url')


def test_fault_visit_has_no_periodic_notice(client):
    with client.application.app_context():
        visit_id, _tech_id = _seed(visit_type='عطل')
        visit = db.session.get(MaintenanceVisit, visit_id)
        assert visit_customer_notice_whatsapp(visit, 'done') == ''
        assert visit_customer_notice_whatsapp(visit, 'eve') == ''


def test_tomorrow_notices_one_message_per_phone(client):
    from datetime import timedelta
    from operations import tomorrow_customer_eve_notices

    with client.application.app_context():
        _seed(visit_day=date.today() + timedelta(days=1))
        items, skipped = tomorrow_customer_eve_notices(on_date=date.today())
    assert skipped == 0
    assert len(items) == 1
    text = unquote(items[0]['url'].split('text=', 1)[-1])
    assert 'موعد الصيانة الدورية لمصعدكم غدا' in text
    assert 'تسهيل أمر فريق الصيانه' in text
    assert 'شركة تقنية جما التميز للمصاعد' in text


def test_tomorrow_notices_api(client):
    from datetime import timedelta
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        _seed(visit_day=date.today() + timedelta(days=1))
    res = client.post('/api/maintenance/tomorrow-customer-notices', json={})
    assert res.status_code == 200
    data = res.get_json()
    assert data['ok'] is True
    assert data['count'] == 1
    assert 'wa.me' in data['items'][0]['url']


def test_tomorrow_alert_whatsapp_uses_eve_message(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        visit_id, _tech_id = _seed(visit_day=date(2026, 10, 4))
    res = client.get(f'/api/alerts/customer-whatsapp/visit_eve/{visit_id}')
    assert res.status_code == 200
    url = (res.get_json() or {}).get('whatsapp_url') or ''
    text = unquote(url.split('text=', 1)[-1])
    assert text.startswith('عميلنا العزيز')
    assert 'غدا الأحد' in text
    assert 'الموافق ٢٠٢٦/١٠/٤ م' in text
    assert 'تسهيل أمر فريق الصيانه' in text
    assert text.endswith('شركة تقنية جما التميز للمصاعد')
    assert 'متابعة زيارة' not in text


def test_eve_and_done_messages_include_building(client):
    with client.application.app_context():
        visit_id, _tech_id = _seed(building='برج النور', visit_day=date(2026, 10, 4))
        visit = db.session.get(MaintenanceVisit, visit_id)
        eve = build_periodic_visit_eve_message(visit)
        done = build_periodic_visit_done_message(
            visit,
            company_name='تقنية جما التميز للمصاعد',
            contact_phone='0509988776',
        )
    assert 'المبنى: برج النور' in eve
    assert 'المبنى: برج النور' in done


def test_tomorrow_notice_lists_each_building(client):
    from datetime import timedelta
    from operations import tomorrow_customer_eve_notices

    day = date.today() + timedelta(days=1)
    with client.application.app_context():
        _seed(visit_day=day, building='برج أ', phone='0555000111', suffix='B1')
        _seed(visit_day=day, building='برج ب', phone='0555000111', suffix='B2')
        items, skipped = tomorrow_customer_eve_notices(on_date=date.today())
    assert skipped == 0
    assert len(items) == 1
    text = unquote(items[0]['url'].split('text=', 1)[-1])
    assert 'المبنى: برج أ، برج ب' in text


def test_scheduled_tomorrow_alert_includes_building(client):
    from datetime import timedelta
    from operations import visit_alerts

    with client.application.app_context():
        _seed(visit_day=date.today() + timedelta(days=1), building='برج التنبيه', suffix='AL')
        alerts = visit_alerts()
    tomorrow = next(a for a in alerts if a['alert_id'] == 'visits_tomorrow')
    assert 'زيارة مجدولة غداً' in tomorrow['text']
    assert 'برج التنبيه' in tomorrow['text']


def test_visits_tomorrow_drill_includes_building(client):
    from datetime import timedelta
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        _seed(visit_day=date.today() + timedelta(days=1), building='برج البيان', suffix='DR')
    res = client.get('/api/dashboard/drill/visits_tomorrow')
    assert res.status_code == 200
    data = res.get_json()
    assert data['columns'][2] == 'المبنى'
    assert any('برج البيان' in (row.get('cells') or []) for row in data['rows'])


def test_customer_notice_api_eve(client):
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        visit_id, _tech_id = _seed()
    res = client.post(
        f'/api/maintenance-visits/{visit_id}/customer-notice',
        json={'kind': 'eve'},
    )
    assert res.status_code == 200
    url = res.get_json()['url']
    text = unquote(url.split('text=', 1)[-1])
    assert 'موعد الصيانة الدورية' in text
    assert 'تسهيل أمر فريق الصيانه' in text
