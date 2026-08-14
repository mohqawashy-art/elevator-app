"""استيراد فني من الواجهة يحافظ على كود Tech-xxx."""
from app import db
from models import Technician

from tests.conftest import ensure_test_organization, login_as


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
