"""فحص موقع عروض صيانة — طلب من المبيعات وتعبئة من الفني."""
from __future__ import annotations

from datetime import datetime

from models import (
    Elevator,
    MaintenanceQuote,
    MaintenanceQuoteSurvey,
    MaintenanceQuoteSurveyUnit,
    Technician,
    db,
)
from sales.service import sync_quote_elevators
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query

SURVEY_OPEN = frozenset({'مُرسَل', 'قيد الفحص'})
SURVEY_DONE = 'مكتمل'


def active_survey_for_quote(quote_id: int) -> MaintenanceQuoteSurvey | None:
    return (
        tenant_query(MaintenanceQuoteSurvey)
        .filter(
            MaintenanceQuoteSurvey.quote_id == quote_id,
            MaintenanceQuoteSurvey.status.in_(tuple(SURVEY_OPEN) + (SURVEY_DONE,)),
        )
        .order_by(MaintenanceQuoteSurvey.id.desc())
        .first()
    )


def latest_survey_for_quote(quote_id: int) -> MaintenanceQuoteSurvey | None:
    return (
        tenant_query(MaintenanceQuoteSurvey)
        .filter_by(quote_id=quote_id)
        .order_by(MaintenanceQuoteSurvey.id.desc())
        .first()
    )


def create_survey_request(
    quote: MaintenanceQuote,
    *,
    technician_id: int,
    request_notes: str | None,
    next_code_fn,
) -> MaintenanceQuoteSurvey:
    open_row = (
        tenant_query(MaintenanceQuoteSurvey)
        .filter(
            MaintenanceQuoteSurvey.quote_id == quote.id,
            MaintenanceQuoteSurvey.status.in_(tuple(SURVEY_OPEN)),
        )
        .first()
    )
    if open_row:
        raise ValueError('يوجد طلب فحص مفتوح لهذا العرض')

    tech = tenant_get_or_404(Technician, technician_id)
    if (tech.status or '') not in ('نشط', 'متاح', 'مشغول', ''):
        raise ValueError('الفني غير متاح')

    survey = MaintenanceQuoteSurvey(
        quote_id=quote.id,
        code=next_code_fn(MaintenanceQuoteSurvey, 'MQS-', digits=5),
        status='مُرسَل',
        technician_id=tech.id,
        request_notes=(request_notes or '').strip() or None,
        requested_at=datetime.utcnow(),
    )
    assign_organization(survey)
    db.session.add(survey)
    return survey


def survey_units_payload(survey: MaintenanceQuoteSurvey) -> list[dict]:
    rows = []
    for u in survey.units or []:
        rows.append(_unit_to_dict(u))
    return rows


def _unit_to_dict(u: MaintenanceQuoteSurveyUnit) -> dict:
    return {
        'id': u.id,
        'sort_order': u.sort_order or 1,
        'unit_label': u.unit_label or '',
        'building_name': u.building_name or '',
        'location_note': u.location_note or '',
        'elev_type': u.elev_type or '',
        'brand': u.brand or '',
        'model': u.model or '',
        'capacity_kg': u.capacity_kg or '',
        'capacity_persons': u.capacity_persons or '',
        'floors': u.floors or '',
        'stops': u.stops or '',
        'speed': u.speed or '',
        'machine_type': u.machine_type or '',
        'door_type': u.door_type or '',
        'control_type': u.control_type or '',
        'serial_number': u.serial_number or '',
        'technical_opinion': u.technical_opinion or '',
        'condition_status': u.condition_status or '',
        'needs_repair': bool(u.needs_repair),
        'needs_spare_parts': bool(u.needs_spare_parts),
        'repair_scope': u.repair_scope or '',
        'spare_parts_scope': u.spare_parts_scope or '',
        'separate_quote_notes': u.separate_quote_notes or '',
        'elevator_code': u.elevator.code if u.elevator else '',
    }


def survey_field_payload(survey_id: int, *, tech_id: int, base_url: str = '') -> dict:
    survey = tenant_get_or_404(MaintenanceQuoteSurvey, survey_id)
    if survey.technician_id != tech_id:
        raise PermissionError('طلب الفحص غير مكلّف لك')
    if survey.status == 'ملغى':
        raise PermissionError('طلب الفحص ملغى')
    quote = survey.quote
    cust = quote.customer if quote else None
    if survey.status == 'مُرسَل':
        survey.status = 'قيد الفحص'
        survey.started_at = datetime.utcnow()
    return {
        'survey_id': survey.id,
        'survey_code': survey.code,
        'status': survey.status,
        'quote_code': quote.code if quote else '—',
        'customer_name': cust.name if cust else '—',
        'customer_code': cust.code if cust else '—',
        'city': quote.city or (cust.city if cust else '') or '—',
        'district': quote.district or (cust.district if cust else '') or '—',
        'address': quote.address or (cust.address if cust else '') or '—',
        'request_notes': survey.request_notes or '',
        'units': survey_units_payload(survey),
        'save_url': f'/api/field/maint-quote-survey/{survey.id}',
        'complete_url': f'/api/field/maint-quote-survey/{survey.id}/complete',
        'back_url': base_url.rstrip('/') + '/field' if base_url else '/field',
    }


def _parse_int(raw) -> int | None:
    try:
        if raw in (None, ''):
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_bool(raw) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or '').strip().lower() in ('1', 'true', 'yes', 'on')


def save_survey_units(survey_id: int, *, tech_id: int, units: list[dict]) -> MaintenanceQuoteSurvey:
    survey = tenant_get_or_404(MaintenanceQuoteSurvey, survey_id)
    if survey.technician_id != tech_id:
        raise PermissionError('طلب الفحص غير مكلّف لك')
    if survey.status not in SURVEY_OPEN:
        raise ValueError('لا يمكن تعديل فحص مكتمل')

    tenant_query(MaintenanceQuoteSurveyUnit).filter_by(survey_id=survey.id).delete(
        synchronize_session=False
    )
    if not units:
        units = [{}]

    for idx, raw in enumerate(units, start=1):
        unit = MaintenanceQuoteSurveyUnit(
            survey_id=survey.id,
            sort_order=_parse_int(raw.get('sort_order')) or idx,
            unit_label=(raw.get('unit_label') or f'مصعد {idx}').strip()[:80],
            building_name=(raw.get('building_name') or '').strip()[:200] or None,
            location_note=(raw.get('location_note') or '').strip()[:200] or None,
            elev_type=(raw.get('elev_type') or '').strip()[:100] or None,
            brand=(raw.get('brand') or '').strip()[:100] or None,
            model=(raw.get('model') or '').strip()[:100] or None,
            capacity_kg=_parse_int(raw.get('capacity_kg')),
            capacity_persons=_parse_int(raw.get('capacity_persons')),
            floors=_parse_int(raw.get('floors')),
            stops=_parse_int(raw.get('stops')),
            speed=(raw.get('speed') or '').strip()[:50] or None,
            machine_type=(raw.get('machine_type') or '').strip()[:30] or None,
            door_type=(raw.get('door_type') or '').strip()[:50] or None,
            control_type=(raw.get('control_type') or '').strip()[:50] or None,
            serial_number=(raw.get('serial_number') or '').strip()[:100] or None,
            technical_opinion=(raw.get('technical_opinion') or '').strip() or None,
            condition_status=(raw.get('condition_status') or '').strip()[:40] or None,
            needs_repair=_parse_bool(raw.get('needs_repair')),
            needs_spare_parts=_parse_bool(raw.get('needs_spare_parts')),
            repair_scope=(raw.get('repair_scope') or '').strip() or None,
            spare_parts_scope=(raw.get('spare_parts_scope') or '').strip() or None,
            separate_quote_notes=(raw.get('separate_quote_notes') or '').strip() or None,
        )
        assign_organization(unit)
        db.session.add(unit)

    if survey.status == 'مُرسَل':
        survey.status = 'قيد الفحص'
        survey.started_at = datetime.utcnow()
    return survey


def complete_survey(survey_id: int, *, tech_id: int, next_elevator_code_fn) -> MaintenanceQuoteSurvey:
    survey = tenant_get_or_404(MaintenanceQuoteSurvey, survey_id)
    if survey.technician_id != tech_id:
        raise PermissionError('طلب الفحص غير مكلّف لك')
    if survey.status == SURVEY_DONE:
        return survey
    if survey.status not in SURVEY_OPEN:
        raise ValueError('حالة الفحص لا تسمح بالإكمال')

    quote = survey.quote
    if not quote:
        raise ValueError('العرض غير موجود')

    units = list(survey.units or [])
    if not units:
        raise ValueError('أضف مصعداً واحداً على الأقل في نموذج الفحص')

    for u in units:
        if not (u.elev_type or u.brand or u.capacity_kg or u.floors):
            raise ValueError(f'عبّئ مواصفات {u.unit_label or "المصعد"}')
        if not (u.technical_opinion or '').strip():
            raise ValueError(f'أدخل الرأي الفني لـ {u.unit_label or "المصعد"}')

    elev_ids: list[int] = []
    for u in units:
        elev = _ensure_elevator_from_unit(u, quote, next_elevator_code_fn)
        u.elevator_id = elev.id
        elev_ids.append(elev.id)

    sync_quote_elevators(quote.id, elev_ids)
    survey.status = SURVEY_DONE
    survey.completed_at = datetime.utcnow()
    return survey


def _ensure_elevator_from_unit(
    unit: MaintenanceQuoteSurveyUnit,
    quote: MaintenanceQuote,
    next_code_fn,
) -> Elevator:
    if unit.elevator_id:
        elev = tenant_query(Elevator).filter_by(id=unit.elevator_id).first()
        if elev:
            _apply_unit_to_elevator(elev, unit, quote)
            return elev

    elev = Elevator(
        code=next_code_fn(Elevator, 'EL-', digits=4),
        customer_id=quote.customer_id,
        building_name=unit.building_name or None,
        city=quote.city,
        district=quote.district,
        address=quote.address,
        elev_type=unit.elev_type,
        brand=unit.brand,
        model=unit.model,
        capacity_kg=unit.capacity_kg,
        capacity_persons=unit.capacity_persons,
        floors=unit.floors,
        stops=unit.stops,
        speed=unit.speed,
        machine_type=unit.machine_type,
        door_type=unit.door_type,
        control_type=unit.control_type,
        serial_number=unit.serial_number,
        status='نشط',
        notes=(unit.technical_opinion or '')[:500] or None,
    )
    assign_organization(elev)
    db.session.add(elev)
    db.session.flush()
    return elev


def _apply_unit_to_elevator(elev: Elevator, unit: MaintenanceQuoteSurveyUnit, quote: MaintenanceQuote) -> None:
    elev.customer_id = quote.customer_id
    if unit.building_name:
        elev.building_name = unit.building_name
    if quote.city:
        elev.city = quote.city
    if quote.district:
        elev.district = quote.district
    if quote.address:
        elev.address = quote.address
    for attr in (
        'elev_type', 'brand', 'model', 'capacity_kg', 'capacity_persons',
        'floors', 'stops', 'speed', 'machine_type', 'door_type',
        'control_type', 'serial_number',
    ):
        val = getattr(unit, attr, None)
        if val not in (None, ''):
            setattr(elev, attr, val)


def survey_summary_for_field(survey: MaintenanceQuoteSurvey, base_url: str = '') -> dict:
    quote = survey.quote
    cust = quote.customer if quote else None
    return {
        'id': survey.id,
        'code': survey.code,
        'status': survey.status,
        'quote_code': quote.code if quote else '—',
        'customer': cust.name if cust else '—',
        'customer_code': cust.code if cust else '—',
        'city': quote.city or '—',
        'district': quote.district or '—',
        'url': f'{base_url.rstrip("/")}/field/maint-quote-survey/{survey.id}' if base_url else f'/field/maint-quote-survey/{survey.id}',
        'units_count': len(survey.units or []),
    }


def quote_survey_units_for_display(quote: MaintenanceQuote) -> list[MaintenanceQuoteSurveyUnit]:
    survey = latest_survey_for_quote(quote.id)
    if not survey or survey.status != SURVEY_DONE:
        return []
    return list(survey.units or [])
