"""استقبال حضور عبر API عام — أي جهاز متوافق مع HTTP."""

from __future__ import annotations

from datetime import datetime

from flask import Response, jsonify, request

from attendance.protocols import PROTOCOL_WEBHOOK
from attendance.service import (
    find_device_by_token,
    ingest_attendance_punch,
    parse_punch_timestamp,
    punch_status_from_event,
)


def _extract_token() -> str:
    auth = (request.headers.get('Authorization') or '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    for header in ('X-Attendance-Token', 'X-Device-Token'):
        value = (request.headers.get(header) or '').strip()
        if value:
            return value
    return (request.args.get('token') or '').strip()


def _parse_payload() -> tuple[dict | None, Response | None]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, Response('Expected JSON object', status=400, mimetype='text/plain')
    return data, None


def handle_webhook_punch():
    token = _extract_token()
    if not token:
        return jsonify({'ok': False, 'error': 'missing_token'}), 401

    device = find_device_by_token(token)
    if not device or device.protocol != PROTOCOL_WEBHOOK:
        return jsonify({'ok': False, 'error': 'invalid_token'}), 403

    data, err = _parse_payload()
    if err:
        return err

    user_id = str(data.get('user_id') or data.get('biometric_user_id') or '').strip()
    if not user_id:
        return jsonify({'ok': False, 'error': 'user_id_required'}), 400

    ts_raw = data.get('timestamp') or data.get('punched_at') or data.get('time')
    punched_at = parse_punch_timestamp(str(ts_raw or '')) if ts_raw else datetime.utcnow()
    if not punched_at:
        return jsonify({'ok': False, 'error': 'invalid_timestamp'}), 400

    status_code = punch_status_from_event(
        str(data.get('event') or data.get('type') or data.get('status') or ''),
        default=int(data.get('status_code') or 0),
    )

    punch = ingest_attendance_punch(
        device=device,
        biometric_user_id=user_id,
        punched_at=punched_at,
        status_code=status_code,
        verify_mode=int(data.get('verify_mode') or 0),
        work_code=int(data.get('work_code') or 0),
        raw_line=str(data)[:300],
    )
    return jsonify({
        'ok': True,
        'punch_id': punch.id if punch else None,
    })
