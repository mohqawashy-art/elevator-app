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


def _seed(*, phone='0555123456', visit_type='صيانة دورية', status='مجدولة', visit_day=None):
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
    tech = Technician(organization_id=oid, code='T-VN', name='فني رسالة', phone='0501111111')
    db.session.add(tech)
    cust = Customer(
        organization_id=oid,
        code='C-VN',
        name='عميل رسالة',
        phone=phone,
        status='نشط',
    )
    db.session.add(cust)
    db.session.flush()
    elev = Elevator(organization_id=oid, code='E-VN', customer_id=cust.id, status='نشط')
    db.session.add(elev)
    db.session.flush()
    visit = MaintenanceVisit(
        organization_id=oid,
        code='V-VN1',
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
