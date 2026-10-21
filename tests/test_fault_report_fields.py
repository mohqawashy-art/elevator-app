"""تقرير العطل: ظهور بيانات السجل وحفظ كل حقول الفني."""
import json

from models import Customer, Elevator, Fault, Technician, db
from tests.conftest import login_as
from tests.test_visit_report_media import TINY_DATA_URL


def _fault(**extra):
    from tests.conftest import ensure_test_organization

    oid = ensure_test_organization()
    tech = Technician(
        organization_id=oid, code='T-FRFLD', name='فني التقرير',
        phone='0500000091', team='أعطال', status='متاح',
    )
    cust = Customer(
        organization_id=oid, code='C-FRFLD', name='عميل التقرير',
        phone='0550000091', address='شارع العليا', district='العليا', status='نشط',
    )
    db.session.add_all([tech, cust])
    db.session.flush()
    elev = Elevator(
        organization_id=oid, code='E-FRFLD', customer_id=cust.id, status='نشط',
        brand='Otis', model='Gen2', elev_type='ركاب', building_name='برج النخيل',
    )
    db.session.add(elev)
    db.session.flush()
    fault = Fault(
        organization_id=oid,
        code='F-FRFLD',
        elevator_id=elev.id,
        technician_id=tech.id,
        fault_type='عطل أبواب',
        status='قيد المعالجة',
        client_report='المصعد واقف بين الأدوار',
        reporter_name='أبو سعد',
        reporter_phone='0550000091',
        tech_notes='الكونتاكتور لا يمسك',
        resolution='',
        priority='عاجلة',
        **extra,
    )
    db.session.add(fault)
    db.session.commit()
    return fault.id


def test_report_page_shows_fault_and_elevator_data(client):
    login_as(client, role='admin')
    with client.application.app_context():
        fault_id = _fault()

    page = client.get(f'/faults/{fault_id}/report')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    for text in (
        'المصعد واقف بين الأدوار',
        'الكونتاكتور لا يمسك',
        'Otis',
        'Gen2',
        'أبو سعد',
        'برج النخيل',
        'عطل أبواب',
    ):
        assert text in html, text
    assert 'id="elevator-brand"' in html
    assert 'value="ركاب"' not in html.split('id="elevator-brand"', 1)[1][:80]


def test_report_json_does_not_break_the_page(client):
    login_as(client, role='admin')
    with client.application.app_context():
        fault_id = _fault(report_json=json.dumps({
            'meta': {'diagnosis': 'قبل </script><script>alert(1)</script> بعد'},
        }, ensure_ascii=False))

    html = client.get(f'/faults/{fault_id}/report').get_data(as_text=True)
    assert '</script><script>alert(1)' not in html
    assert 'قبل' in html and 'بعد' in html


def test_save_keeps_every_report_field(client):
    login_as(client, role='admin')
    with client.application.app_context():
        fault_id = _fault()
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    payload = {
        'csrf_token': 'test-csrf',
        'meta': {
            'visit_date': '2026-10-19',
            'arrival_time': '09:15',
            'end_time': '10:40',
            'elevator_brand': 'Otis',
            'elevator_model': 'Gen2',
            'contract_type': 'عقد ضمان',
            'client_description': 'المصعد واقف بين الأدوار',
            'fault_types': ['عطل أبواب', 'عطل كهربائي'],
            'diagnosis': 'حساس الباب لا يعمل',
            'action_taken': 'استبدال الحساس',
            'prevention': 'فحص الحساس كل زيارة',
            'visit_outcome': 'partial',
            'next_visit': '2026-10-26',
            'final_notes': 'يحتاج متابعة',
            'customer_rating': 4,
            'customer_comment': 'شكراً',
            'labor_cost': 150,
        },
        'parts': [{'item_id': None, 'name': 'حساس باب', 'qty': 1, 'unit_price': 80}],
        'signatures': {'tech': '', 'client': ''},
        'photos': [{'url': TINY_DATA_URL, 'caption': 'باب المصعد'}],
    }
    resp = client.post(f'/api/faults/{fault_id}/report', json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)

    with client.application.app_context():
        saved = Fault.query.get(fault_id)
        data = json.loads(saved.report_json)
        meta = data['meta']
        assert meta['diagnosis'] == 'حساس الباب لا يعمل'
        assert meta['action_taken'] == 'استبدال الحساس'
        assert meta['prevention'] == 'فحص الحساس كل زيارة'
        assert meta['final_notes'] == 'يحتاج متابعة'
        assert meta['customer_comment'] == 'شكراً'
        assert meta['visit_outcome'] == 'partial'
        assert meta['fault_types'] == ['عطل أبواب', 'عطل كهربائي']
        assert meta['end_time'] == '10:40'
        assert meta['labor_cost'] == 150
        assert meta['elevator_brand'] == 'Otis'
        assert meta['elevator_model'] == 'Gen2'
        assert data['parts'][0]['name'] == 'حساس باب'
        assert data['photos'][0]['url'].startswith('/static/uploads/faults/')
        assert data['photos'][0]['caption'] == 'باب المصعد'
        assert saved.tech_notes == 'حساس الباب لا يعمل'
        assert saved.resolution == 'استبدال الحساس'
        assert 'فحص الحساس' not in (saved.tech_notes or '')

    html = client.get(f'/faults/{fault_id}/report').get_data(as_text=True)
    for text in ('حساس الباب لا يعمل', 'استبدال الحساس', 'فحص الحساس كل زيارة', 'يحتاج متابعة', 'حساس باب'):
        assert text in html, text


def test_short_form_save_appears_in_report(client):
    from operations import complete_field_fault

    login_as(client, role='admin')
    with client.application.app_context():
        fault_id = _fault()
        complete_field_fault(
            fault_id,
            tech_notes='تم فحص اللوحة',
            resolution='إعادة ضبط القواطع',
            status='تم الاصلاح',
        )
        saved = Fault.query.get(fault_id)
        data = json.loads(saved.report_json)
        assert data['meta']['diagnosis'] == 'تم فحص اللوحة'
        assert data['meta']['action_taken'] == 'إعادة ضبط القواطع'
        assert data['meta']['visit_outcome'] == 'solved'

    html = client.get(f'/faults/{fault_id}/report').get_data(as_text=True)
    assert 'تم فحص اللوحة' in html
    assert 'إعادة ضبط القواطع' in html


def test_print_report_shows_arrival_and_end_times(client):
    from datetime import datetime

    login_as(client, role='admin')
    with client.application.app_context():
        fault_id = _fault(
            responded_at=datetime(2026, 10, 21, 6, 30),
            resolved_at=datetime(2026, 10, 21, 8, 5),
            report_json='{}',
        )

    html = client.get(f'/faults/{fault_id}/report?print=1').get_data(as_text=True)
    assert 'class="fr-time-print" data-print-for="arrival-time">09:30' in html
    assert 'class="fr-time-print" data-print-for="end-time">11:05' in html
    assert 'value="09:30"' in html
    assert 'value="11:05"' in html

    with client.application.app_context():
        saved = json.loads(Fault.query.get(fault_id).report_json or '{}')
        assert (saved.get('meta') or {}).get('arrival_time', '') in ('', None)
