"""حفظ توقيع الموظف من الإعدادات."""
from io import BytesIO

from models import Signatory, db
from tests.conftest import login_as

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32


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
        db.session.delete(row)
        db.session.commit()
