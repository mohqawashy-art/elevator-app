"""استيراد فني من الواجهة يحافظ على كود Tech-xxx."""
from app import db
from models import Customer, Technician

from tests.conftest import ensure_test_organization, login_as

JSON_HEADERS = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}


def test_technician_import_keeps_code(client):
    login_as(client, 'admin')
    with client.application.app_context():
        ensure_test_organization()
    r = client.post(
        '/technicians/add',
        data={
            'code': 'Tech-001',
            'name': 'رأفت السيد محمود',
            'job_title': 'فني اعطال',
            'status': 'متاح',
            'city': 'مكة',
            'emergency': 'on',
        },
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body['ok'] is True
    assert body['code'] == 'Tech-001'
    with client.application.app_context():
        t = Technician.query.filter_by(code='Tech-001').first()
        assert t is not None
        assert t.name == 'رأفت السيد محمود'
        assert t.status == 'متاح'


def test_technician_import_updates_existing_code(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        db.session.add(Technician(
            organization_id=oid, code='Tech-002', name='قديم', status='متاح',
        ))
        db.session.commit()
    r = client.post(
        '/technicians/add',
        data={'code': 'Tech-002', 'name': 'عبدالله لشكري', 'status': 'متاح'},
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    )
    assert r.status_code == 200
    with client.application.app_context():
        rows = Technician.query.filter_by(code='Tech-002').all()
        assert len(rows) == 1
        assert rows[0].name == 'عبدالله لشكري'


def test_technician_create_only_does_not_upsert_existing_code(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        db.session.add(Technician(
            organization_id=oid, code='Tech-001', name='قديم', status='متاح',
        ))
        db.session.commit()
    r = client.post(
        '/technicians/add',
        data={
            'code': 'Tech-001',
            'create_only': '1',
            'name': 'فني جديد',
            'status': 'متاح',
        },
        headers=JSON_HEADERS,
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body['ok'] is True
    assert body['code'] != 'Tech-001'
    with client.application.app_context():
        names = {t.name for t in Technician.query.all()}
        assert names == {'قديم', 'فني جديد'}


def test_technician_add_reports_duplicate_phone(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        db.session.add(Customer(
            organization_id=oid, code='C-0001', name='عميل', phone='+966512345678',
        ))
        db.session.commit()
    r = client.post(
        '/technicians/add',
        data={
            'create_only': '1',
            'name': 'فني جوال مكرر',
            'phone': '512345678',
            'status': 'متاح',
        },
        headers=JSON_HEADERS,
    )
    assert r.status_code == 400
    body = r.get_json()
    assert body['ok'] is False
    assert 'الجوال' in (body.get('message') or '')
    with client.application.app_context():
        assert Technician.query.filter_by(name='فني جوال مكرر').first() is None


def test_technician_add_accepts_profile_fields(client):
    login_as(client, 'admin')
    with client.application.app_context():
        ensure_test_organization()
    r = client.post(
        '/technicians/add',
        data={
            'create_only': '1',
            'name': 'أحمد علي',
            'job_title': 'فني أول',
            'specialization': 'كهرباء',
            'city': 'مكة',
            'status': 'متاح',
            'salary': '3,500',
            'experience_years': '٥',
            'hire_date': '19/09/2026',
        },
        headers=JSON_HEADERS,
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body['ok'] is True
    with client.application.app_context():
        t = Technician.query.filter_by(name='أحمد علي').first()
        assert t is not None
        assert t.salary == 3500
        assert t.experience_years == 5
        assert str(t.hire_date) == '2026-09-19'
