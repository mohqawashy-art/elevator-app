"""حفظ توقيع الموظف من الإعدادات."""
import os
from io import BytesIO

from models import Signatory, db
from tests.conftest import login_as

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32


def _drop_signatory(client, national_id):
    with client.application.app_context():
        row = Signatory.query.filter_by(national_id=national_id).one()
        if row.signature_path:
            abs_path = os.path.join(
                client.application.root_path,
                row.signature_path.replace('/', os.sep),
            )
            if os.path.isfile(abs_path):
                os.remove(abs_path)
        db.session.delete(row)
        db.session.commit()


def test_add_manager_signatory_from_settings(client):
    login_as(client, 'admin')
    response = client.post(
        '/settings/signatories/add',
        data={
            'name': 'موظف المكتب',
            'national_id': '1234567890',
            'role': 'manager',
            'sign_pin': '123456',
            'signature': (BytesIO(PNG), 'sign.png'),
        },
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'normalize_national_id' not in html
    assert 'تم حفظ التوقيع بنجاح' in html
    with client.application.app_context():
        row = Signatory.query.filter_by(name='موظف المكتب').one()
        assert row.role == 'manager'
        assert row.national_id == '1234567890'
        assert row.signature_path
    _drop_signatory(client, '1234567890')


def test_manager_signatory_verifies_on_technician_signature_slot(client):
    login_as(client, 'admin')
    saved = client.post(
        '/settings/signatories/add',
        data={
            'name': 'موظف المكتب',
            'national_id': '1098765432',
            'role': 'manager',
            'sign_pin': '654321',
            'signature': (BytesIO(PNG), 'sign.png'),
        },
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert 'تم حفظ التوقيع بنجاح' in saved.get_data(as_text=True)

    ok = client.post('/api/signatures/verify', json={
        'national_id': '1098765432',
        'pin': '654321',
        'role': 'technician',
    })
    body = ok.get_json()
    assert ok.status_code == 200
    assert body['ok'] is True
    assert body['name'] == 'موظف المكتب'
    assert body.get('signature_data')

    bad = client.post('/api/signatures/verify', json={
        'national_id': '1098765432',
        'pin': '000000',
        'role': 'technician',
    })
    assert bad.status_code == 401
    assert bad.get_json()['ok'] is False
    _drop_signatory(client, '1098765432')
