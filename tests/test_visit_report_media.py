"""اختبارات صور محضر الصيانة."""
from __future__ import annotations

import base64
import json
import os
from datetime import date

from models import Customer, Elevator, MaintenanceVisit, Technician, db

from tests.conftest import ensure_test_organization


TINY_PNG = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)
TINY_DATA_URL = f'data:image/png;base64,{TINY_PNG}'


def test_normalize_report_photos_persists_data_url(client):
    from visit_report_media import is_persisted_visit_photo_url, normalize_report_photos

    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-PHM', name='فني', phone='0501110001', team='صيانة')
        db.session.add(tech)
        cust = Customer(organization_id=oid, code='C-PHM', name='عميل', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-PHM', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        visit = MaintenanceVisit(
            organization_id=oid,
            code='V-PHM1',
            elevator_id=elev.id,
            technician_id=tech.id,
            visit_date=date.today(),
            status='عند العميل',
        )
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id
        root = client.application.root_path

        out = normalize_report_photos(root, visit_id, [{'url': TINY_DATA_URL, 'caption': 'اختبار'}])
        assert len(out) == 1
        assert is_persisted_visit_photo_url(out[0]['url'])
        assert out[0]['caption'] == 'اختبار'
        rel = out[0]['url'].replace('/static/', '')
        abs_path = os.path.join(root, 'static', rel.replace('/', os.sep))
        assert os.path.isfile(abs_path)


def test_save_visit_report_stores_photo_files(client):
    from checklist_templates import parse_report_json

    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-PHS', name='فني', phone='0501110002', team='صيانة')
        db.session.add(tech)
        cust = Customer(organization_id=oid, code='C-PHS', name='عميل', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-PHS', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        visit = MaintenanceVisit(
            organization_id=oid,
            code='V-PHS1',
            elevator_id=elev.id,
            technician_id=tech.id,
            visit_date=date.today(),
            status='عند العميل',
        )
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id
        tech_id = tech.id

    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id

    r = client.post(
        f'/api/maintenance-visits/{visit_id}/report',
        json={
            'items': {'5_3': {'status': 'ok', 'note': ''}},
            'photos': [{'url': TINY_DATA_URL, 'caption': 'صورة'}],
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    with client.application.app_context():
        v = db.session.get(MaintenanceVisit, visit_id)
        data = parse_report_json(v.checklist_json)
        assert len(data.get('photos') or []) == 1
        assert data['photos'][0]['url'].startswith('/static/uploads/visits/')
        assert data['photos'][0]['caption'] == 'صورة'


def test_upload_visit_report_photo_api(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-PHU', name='فني', phone='0501110003', team='صيانة')
        db.session.add(tech)
        cust = Customer(organization_id=oid, code='C-PHU', name='عميل', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-PHU', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        visit = MaintenanceVisit(
            organization_id=oid,
            code='V-PHU1',
            elevator_id=elev.id,
            technician_id=tech.id,
            visit_date=date.today(),
            status='عند العميل',
        )
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id
        tech_id = tech.id

    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id

    r = client.post(
        f'/api/maintenance-visits/{visit_id}/report-photo',
        json={'data_url': TINY_DATA_URL},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json() or {}
    assert body.get('ok') is True
    assert str(body.get('url', '')).startswith('/static/uploads/visits/')
