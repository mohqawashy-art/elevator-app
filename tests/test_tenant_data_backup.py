"""تنزيل نسخة احتياطية مؤرخة لبيانات الشركة + تذكير المدير."""
import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone

from app import app, db
from models import BiometricDevice, Customer, Settings
from tenant_lifecycle import data_backup_status
from tests.conftest import login_as


def test_backup_due_until_a_recent_download():
    fresh = data_backup_status(type('S', (), {
        'last_data_backup_at': None,
        'data_backup_remind_days': 30,
    })())
    assert fresh['due'] is True
    assert fresh['never'] is True

    recent = datetime.now(timezone.utc) - timedelta(days=3)
    ok = data_backup_status(type('S', (), {
        'last_data_backup_at': recent,
        'data_backup_remind_days': 30,
    })())
    assert ok['due'] is False
    assert ok['age_days'] == 3

    old = datetime.now(timezone.utc) - timedelta(days=30)
    late = data_backup_status(type('S', (), {
        'last_data_backup_at': old,
        'data_backup_remind_days': 30,
    })())
    assert late['due'] is True
    assert late['age_days'] == 30

    off = data_backup_status(type('S', (), {
        'last_data_backup_at': None,
        'data_backup_remind_days': 0,
    })())
    assert off['due'] is False


def test_admin_downloads_dated_backup_and_reminder_clears(client):
    login_as(client, 'admin')
    page = client.get('/settings?tab=backup')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'تنزيل النسخة الاحتياطية' in html
    assert 'lc-backup-remind' in client.get('/settings').get_data(as_text=True)

    with app.app_context():
        org_id = Settings.query.first().organization_id
        db.session.add(Customer(organization_id=org_id, code='C-BAK', name='عميل النسخة'))
        db.session.add(BiometricDevice(
            organization_id=org_id,
            serial_number='ZK-1',
            name='بوابة',
            auth_token='SECRET-DEVICE-TOKEN',
        ))
        db.session.commit()

    downloaded = client.get('/settings/data-backup')
    assert downloaded.status_code == 200
    assert downloaded.mimetype == 'application/zip'
    disposition = downloaded.headers.get('Content-Disposition') or ''
    assert re.search(r'liftcore-default-export-\d{8}-\d{6}\.zip', disposition)

    with zipfile.ZipFile(io.BytesIO(downloaded.data)) as zf:
        readme = zf.read('README.txt').decode('utf-8')
        json_name = next(n for n in zf.namelist() if n.endswith('-data.json'))
        payload = json.loads(zf.read(json_name).decode('utf-8'))

    assert 'مؤرخ' in readme
    names = [row['name'] for row in payload['tables']['customers']]
    assert 'عميل النسخة' in names
    devices = payload['tables']['biometric_devices']
    assert devices
    assert devices[0]['auth_token'] == '[REDACTED]'
    assert 'SECRET-DEVICE-TOKEN' not in json.dumps(devices)

    with app.app_context():
        settings = Settings.query.first()
        assert settings.last_data_backup_at is not None

    again = client.get('/settings')
    assert 'lc-backup-remind' not in again.get_data(as_text=True)


def test_non_admin_cannot_download_backup(client):
    login_as(client, 'manager')
    response = client.get('/settings/data-backup', follow_redirects=True)
    assert response.status_code == 200
    assert response.mimetype != 'application/zip'
    assert 'مدير النظام' in response.get_data(as_text=True)
    assert 'lc-backup-remind' not in client.get('/settings').get_data(as_text=True)
    with app.app_context():
        assert Settings.query.first().last_data_backup_at is None


def test_admin_can_change_reminder_interval(client):
    login_as(client, 'admin')
    saved = client.post(
        '/settings/data-backup/reminder',
        data={'remind_days': '14'},
        follow_redirects=True,
    )
    assert saved.status_code == 200
    assert '14' in saved.get_data(as_text=True)
    with app.app_context():
        assert Settings.query.first().data_backup_remind_days == 14
