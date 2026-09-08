"""ZKTeco ADMS — استقبال uFace 800 وغيره."""

from __future__ import annotations

from datetime import datetime

from flask import Response, request

from attendance.service import (
    bind_device_tenant,
    find_device_by_serial,
    ingest_attendance_punch,
    parse_punch_timestamp,
)
from models import db


def _device_serial() -> str:
    return (request.args.get('SN') or request.args.get('sn') or '').strip()


def _ok_response(extra: str = '') -> Response:
    body = 'OK'
    if extra:
        body = f'OK\n{extra}'
    return Response(body, mimetype='text/plain')


def _require_device():
    sn = _device_serial()
    device = find_device_by_serial(sn)
    if not device:
        return None, Response('Unknown device', status=403, mimetype='text/plain')
    bind_device_tenant(device)
    device.last_seen_at = datetime.utcnow()
    device.last_ip = (request.remote_addr or '')[:45]
    pushver = request.args.get('pushver') or request.args.get('PushVersion')
    if pushver:
        device.firmware = str(pushver)[:40]
    db.session.commit()
    return device, None


def parse_attlog_body(body: str) -> list[dict]:
    records = []
    for line in (body or '').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        bio_id = parts[0].strip()
        ts = parse_punch_timestamp(parts[1])
        if not bio_id or not ts:
            continue
        status_code = 0
        verify_mode = 0
        work_code = 0
        if len(parts) > 2 and str(parts[2]).strip().isdigit():
            status_code = int(parts[2].strip())
        if len(parts) > 3 and str(parts[3]).strip().isdigit():
            verify_mode = int(parts[3].strip())
        if len(parts) > 4 and str(parts[4]).strip().isdigit():
            work_code = int(parts[4].strip())
        records.append({
            'biometric_user_id': bio_id,
            'punched_at': ts,
            'status_code': status_code,
            'verify_mode': verify_mode,
            'work_code': work_code,
            'raw_line': line[:300],
        })
    return records


def handle_iclock_cdata():
    device, err = _require_device()
    if err:
        return err

    table = (request.args.get('table') or '').strip().upper()
    if request.method == 'GET':
        if table == 'OPTIONS':
            return Response(
                'GET OPTION FROM: SN\n'
                'Stamp=9999\n'
                'OpStamp=9999\n'
                'ErrorDelay=30\n'
                'Delay=10\n'
                'TransTimes=00:00;14:00\n'
                'TransInterval=1\n'
                'TransFlag=TransData AttLog OpLog\n'
                'Realtime=1\n'
                'Encrypt=0\n',
                mimetype='text/plain',
            )
        return _ok_response()

    body = request.get_data(as_text=True) or ''
    if table == 'ATTLOG' or (not table and body.strip()):
        count = 0
        for rec in parse_attlog_body(body):
            ingest_attendance_punch(
                device=device,
                biometric_user_id=rec['biometric_user_id'],
                punched_at=rec['punched_at'],
                status_code=rec['status_code'],
                verify_mode=rec['verify_mode'],
                work_code=rec['work_code'],
                raw_line=rec['raw_line'],
            )
            count += 1
        return _ok_response(str(count) if count else '')
    return _ok_response()


def handle_iclock_getrequest():
    device, err = _require_device()
    if err:
        return err
    return Response('OK', mimetype='text/plain')


def handle_iclock_devicecmd():
    device, err = _require_device()
    if err:
        return err
    return _ok_response()


def handle_iclock_registry():
    device, err = _require_device()
    if err:
        return err
    if request.method == 'POST':
        return _ok_response('RegistryCode=1')
    return _ok_response('RegistryCode=1')
