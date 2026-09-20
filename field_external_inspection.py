"""فحص مصعد خارجي — يعبّئه الفني من بوابة /field (بدون عقد أو زيارة)."""
from __future__ import annotations

import json
from datetime import date, datetime

from checklist_templates import (
    empty_report_data,
    get_template,
    merge_report_data,
    parse_report_json,
    report_completion_stats,
)
from models import ExternalElevatorInspection, db
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query

STATUS_DRAFT = 'مسودة'
STATUS_DONE = 'مكتمل'
DEFAULT_TEMPLATE_KEY = 'external_elevator_v1'


def _parse_int(raw) -> int | None:
    try:
        if raw in (None, ''):
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _str_field(raw, max_len: int) -> str | None:
    s = (raw or '').strip()
    if not s:
        return None
    return s[:max_len]


def list_open_for_technician(tech_id: int) -> list[ExternalElevatorInspection]:
    return (
        tenant_query(ExternalElevatorInspection)
        .filter(
            ExternalElevatorInspection.technician_id == tech_id,
            ExternalElevatorInspection.status == STATUS_DRAFT,
        )
        .order_by(ExternalElevatorInspection.created_at.desc())
        .limit(20)
        .all()
    )


def create_inspection(*, tech_id: int, next_code_fn) -> ExternalElevatorInspection:
    row = ExternalElevatorInspection(
        code=next_code_fn(ExternalElevatorInspection, 'EEI-', digits=5),
        status=STATUS_DRAFT,
        technician_id=tech_id,
        checklist_template_key=DEFAULT_TEMPLATE_KEY,
        checklist_json=json.dumps(empty_report_data(DEFAULT_TEMPLATE_KEY), ensure_ascii=False),
        inspected_at=date.today(),
    )
    assign_organization(row)
    db.session.add(row)
    db.session.flush()
    return row


def _checklist_payload(row: ExternalElevatorInspection) -> dict:
    key = row.checklist_template_key or DEFAULT_TEMPLATE_KEY
    saved = parse_report_json(row.checklist_json)
    merged = merge_report_data(saved, key)
    tpl = get_template(key)
    return {
        'template_key': key,
        'template': tpl,
        'data': merged,
        'stats': report_completion_stats(merged, key),
    }


def inspection_summary_for_field(row: ExternalElevatorInspection, base_url: str = '') -> dict:
    base = base_url.rstrip('/') if base_url else ''
    url = f'{base}/field/external-inspection/{row.id}' if base else f'/field/external-inspection/{row.id}'
    label = (row.customer_name or row.building_name or 'موقع بدون اسم').strip() or 'مسودة فحص'
    return {
        'id': row.id,
        'code': row.code,
        'status': row.status,
        'customer': label,
        'city': row.city or '—',
        'inspected_at': str(row.inspected_at) if row.inspected_at else '—',
        'url': url,
    }


def inspection_list_payload(*, tech_id: int, base_url: str = '') -> dict:
    drafts = list_open_for_technician(tech_id)
    recent_done = (
        tenant_query(ExternalElevatorInspection)
        .filter(
            ExternalElevatorInspection.technician_id == tech_id,
            ExternalElevatorInspection.status == STATUS_DONE,
        )
        .order_by(ExternalElevatorInspection.completed_at.desc())
        .limit(15)
        .all()
    )
    return {
        'drafts': [inspection_summary_for_field(r, base_url) for r in drafts],
        'completed': [inspection_summary_for_field(r, base_url) for r in recent_done],
        'new_url': f'{base_url.rstrip("/")}/field/external-inspection/new' if base_url else '/field/external-inspection/new',
        'back_url': f'{base_url.rstrip("/")}/field' if base_url else '/field',
    }


def inspection_field_payload(inspection_id: int, *, tech_id: int, base_url: str = '') -> dict:
    row = tenant_get_or_404(ExternalElevatorInspection, inspection_id)
    if row.technician_id != tech_id:
        raise PermissionError('هذا الفحص غير مخصص لك')
    cl = _checklist_payload(row)
    base = base_url.rstrip('/') if base_url else ''
    iid = row.id
    return {
        'inspection_id': iid,
        'code': row.code,
        'status': row.status,
        'customer_name': row.customer_name or '',
        'customer_phone': row.customer_phone or '',
        'city': row.city or '',
        'district': row.district or '',
        'address': row.address or '',
        'building_name': row.building_name or '',
        'elev_type': row.elev_type or '',
        'brand': row.brand or '',
        'model': row.model or '',
        'capacity_kg': row.capacity_kg or '',
        'capacity_persons': row.capacity_persons or '',
        'floors': row.floors or '',
        'stops': row.stops or '',
        'serial_number': row.serial_number or '',
        'machine_type': row.machine_type or '',
        'door_type': row.door_type or '',
        'control_type': row.control_type or '',
        'condition_status': row.condition_status or '',
        'technical_opinion': row.technical_opinion or '',
        'recommendations': row.recommendations or '',
        'inspected_at': str(row.inspected_at) if row.inspected_at else '',
        'checklist_template': cl['template'],
        'checklist_data': cl['data'],
        'checklist_stats': cl['stats'],
        'save_url': f'{base}/api/field/external-inspection/{iid}' if base else f'/api/field/external-inspection/{iid}',
        'complete_url': f'{base}/api/field/external-inspection/{iid}/complete'
        if base
        else f'/api/field/external-inspection/{iid}/complete',
        'back_url': f'{base}/field/external-inspections' if base else '/field/external-inspections',
        'list_url': f'{base}/field/external-inspections' if base else '/field/external-inspections',
    }


def _apply_header_fields(row: ExternalElevatorInspection, body: dict) -> None:
    if not isinstance(body, dict):
        return
    row.customer_name = _str_field(body.get('customer_name'), 200)
    row.customer_phone = _str_field(body.get('customer_phone'), 30)
    row.city = _str_field(body.get('city'), 100)
    row.district = _str_field(body.get('district'), 100)
    row.address = _str_field(body.get('address'), 300)
    row.building_name = _str_field(body.get('building_name'), 200)
    row.elev_type = _str_field(body.get('elev_type'), 100)
    row.brand = _str_field(body.get('brand'), 100)
    row.model = _str_field(body.get('model'), 100)
    row.capacity_kg = _parse_int(body.get('capacity_kg'))
    row.capacity_persons = _parse_int(body.get('capacity_persons'))
    row.floors = _parse_int(body.get('floors'))
    row.stops = _parse_int(body.get('stops'))
    row.serial_number = _str_field(body.get('serial_number'), 100)
    row.machine_type = _str_field(body.get('machine_type'), 100)
    row.door_type = _str_field(body.get('door_type'), 100)
    row.control_type = _str_field(body.get('control_type'), 100)
    row.condition_status = _str_field(body.get('condition_status'), 80)
    row.technical_opinion = (body.get('technical_opinion') or '').strip() or None
    row.recommendations = (body.get('recommendations') or '').strip() or None
    inspected = (body.get('inspected_at') or '').strip()
    if inspected and len(inspected) >= 10:
        try:
            row.inspected_at = datetime.strptime(inspected[:10], '%Y-%m-%d').date()
        except ValueError:
            pass


def _apply_checklist(row: ExternalElevatorInspection, body: dict) -> None:
    key = row.checklist_template_key or DEFAULT_TEMPLATE_KEY
    checklist = body.get('checklist') if isinstance(body, dict) else None
    if not isinstance(checklist, dict):
        checklist = body if isinstance(body, dict) else {}
    existing = parse_report_json(row.checklist_json)
    merged = merge_report_data(existing, key)
    incoming_items = checklist.get('items') or body.get('items') or {}
    if isinstance(incoming_items, dict):
        for item_id, val in incoming_items.items():
            if item_id in merged['items'] and isinstance(val, dict):
                merged['items'][item_id] = {
                    'status': (val.get('status') or '').strip(),
                    'note': (val.get('note') or '').strip(),
                }
    meta = checklist.get('meta') or body.get('meta') or {}
    if isinstance(meta, dict):
        for mk in merged['meta']:
            if mk in meta:
                merged['meta'][mk] = meta.get(mk) or ''
    merged['template_key'] = key
    row.checklist_json = json.dumps(merged, ensure_ascii=False)


def save_inspection(inspection_id: int, *, tech_id: int, body: dict) -> ExternalElevatorInspection:
    row = tenant_get_or_404(ExternalElevatorInspection, inspection_id)
    if row.technician_id != tech_id:
        raise PermissionError('هذا الفحص غير مخصص لك')
    if row.status != STATUS_DRAFT:
        raise ValueError('لا يمكن تعديل فحص مكتمل')
    _apply_header_fields(row, body)
    _apply_checklist(row, body)
    return row


def complete_inspection(inspection_id: int, *, tech_id: int, body: dict) -> ExternalElevatorInspection:
    row = save_inspection(inspection_id, tech_id=tech_id, body=body)
    if not (row.customer_name or '').strip():
        raise ValueError('اسم العميل أو الجهة مطلوب')
    if not (row.technical_opinion or '').strip():
        raise ValueError('الرأي الفني مطلوب')
    row.status = STATUS_DONE
    row.completed_at = datetime.utcnow()
    if not row.inspected_at:
        row.inspected_at = date.today()
    return row


def blank_print_payload(*, base_url: str = '', back_url: str | None = None) -> dict:
    """نموذج فارغ للطباعة — قائمة الفحص الخارجي + حقول يدوية."""
    from models import Settings
    from operations import _report_brand_logo_url
    from tenant_scope import tenant_query

    template = get_template(DEFAULT_TEMPLATE_KEY)
    settings = tenant_query(Settings).first()
    company = (getattr(settings, 'company_name', None) or 'LiftCore') if settings else 'LiftCore'
    base = base_url.rstrip('/') if base_url else ''
    return {
        'title_ar': 'فحص مصعد خارجي',
        'title_en': 'External elevator site inspection',
        'company_name': company,
        'logo_url': _report_brand_logo_url(),
        'checklist_template': template,
        'back_url': back_url or (f'{base}/field/external-inspections' if base else '/field/external-inspections'),
    }
