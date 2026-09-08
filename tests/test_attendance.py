"""اختبارات الحضور والانصراف + ADMS."""

from __future__ import annotations

from datetime import datetime

import pytest

from attendance.adms import parse_attlog_body
from attendance.service import (
    is_workday,
    parse_punch_timestamp,
    recompute_attendance_day,
)
from app import app
from models import (
    AttendanceBranch,
    AttendanceDay,
    AttendanceEmployee,
    AttendancePunch,
    BiometricDevice,
    Organization,
    db,
)
from tenant_scope import assign_organization


def test_parse_attlog_body():
    body = '1001\t2026-09-08 08:05:00\t0\t15\t0\n1002\t2026-09-08 17:01:00\t1\t15\t0'
    rows = parse_attlog_body(body)
    assert len(rows) == 2
    assert rows[0]['biometric_user_id'] == '1001'
    assert rows[0]['verify_mode'] == 15


def test_parse_punch_timestamp():
    dt = parse_punch_timestamp('2026-09-08 08:05:00')
    assert dt is not None
    assert dt.hour == 5  # UTC from Riyadh +3


def test_is_workday_sunday():
    assert is_workday(datetime(2026, 9, 6).date())  # Sunday


def test_recompute_attendance_day_late(client):
    with app.app_context():
        org = Organization.query.filter_by(slug='default').first()
        if not org:
            org = Organization(slug='default', name='Default', status='active')
            db.session.add(org)
            db.session.commit()
        branch = AttendanceBranch(
            organization_id=org.id,
            code='BR-001',
            name='Main',
            is_default=True,
            is_active=True,
        )
        db.session.add(branch)
        db.session.flush()
        emp = AttendanceEmployee(
            organization_id=org.id,
            code='EMP-001',
            name='Test Employee',
            branch_id=branch.id,
            biometric_user_id='1001',
            status='نشط',
        )
        db.session.add(emp)
        db.session.flush()
        work_date = datetime(2026, 9, 7).date()  # Monday
        punch_in = parse_punch_timestamp('2026-09-07 08:20:00')
        punch_out = parse_punch_timestamp('2026-09-07 17:00:00')
        db.session.add(AttendancePunch(
            organization_id=org.id,
            employee_id=emp.id,
            biometric_user_id='1001',
            punched_at=punch_in,
            status_code=0,
        ))
        db.session.add(AttendancePunch(
            organization_id=org.id,
            employee_id=emp.id,
            biometric_user_id='1001',
            punched_at=punch_out,
            status_code=1,
        ))
        db.session.commit()

        from flask import g
        g.organization_id = org.id
        day = recompute_attendance_day(emp.id, work_date)
        db.session.commit()
        assert day is not None
        assert day.late_minutes == 20
        assert day.status == 'متأخر'


def test_adms_unknown_device(client):
    resp = client.post(
        '/iclock/cdata?SN=UNKNOWN999&table=ATTLOG',
        data='1001\t2026-09-08 08:00:00\t0\t15\t0',
        headers={'Host': 'unknown999.liftcoreapp.com'},
    )
    assert resp.status_code == 403


def test_adms_auto_register_on_localhost(client):
    sn = 'AUTOTESTZK001'
    with app.app_context():
        BiometricDevice.query.filter_by(serial_number=sn).delete()
        db.session.commit()
    resp = client.post(
        f'/iclock/getrequest?SN={sn}',
        headers={'Host': '127.0.0.1'},
    )
    assert resp.status_code == 200
    with app.app_context():
        device = BiometricDevice.query.filter_by(serial_number=sn).first()
        assert device is not None
        assert device.auto_registered is True
        assert device.protocol == 'adms_zkteco'


def test_webhook_punch(client):
    with app.app_context():
        org = Organization.query.filter_by(slug='default').first()
        if not org:
            org = Organization(slug='default', name='Default', status='active')
            db.session.add(org)
            db.session.commit()
        branch = AttendanceBranch.query.filter_by(organization_id=org.id, code='BR-001').first()
        if not branch:
            branch = AttendanceBranch(
                organization_id=org.id,
                code='BR-001',
                name='Main',
                is_default=True,
                is_active=True,
            )
            db.session.add(branch)
            db.session.flush()
        token = 'test-webhook-token-abc'
        BiometricDevice.query.filter_by(serial_number='WH-TEST-001').delete()
        device = BiometricDevice(
            organization_id=org.id,
            branch_id=branch.id,
            serial_number='WH-TEST-001',
            name='Webhook Test',
            protocol='webhook',
            auth_token=token,
            is_active=True,
        )
        db.session.add(device)
        emp = AttendanceEmployee.query.filter_by(
            organization_id=org.id,
            biometric_user_id='9001',
        ).first()
        if not emp:
            emp = AttendanceEmployee(
                organization_id=org.id,
                code='EMP-9001',
                name='Webhook Employee',
                branch_id=branch.id,
                biometric_user_id='9001',
                status='نشط',
            )
            db.session.add(emp)
        db.session.commit()

    resp = client.post(
        '/attendance/api/punch',
        json={
            'user_id': '9001',
            'timestamp': '2026-09-08 08:00:00',
            'event': 'in',
        },
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True
