"""LiftCore — محضر تقرير العطل (JSON + دمج مع سجل العطل)."""
from __future__ import annotations

import json
from datetime import datetime

from operations import FAULT_CLOSED, FAULT_STATUS_FIXED, FAULT_STATUS_FIXED_LEGACY

FAULT_TYPE_OPTIONS = [
    'عطل كهربائي',
    'عطل ميكانيكي',
    'عطل أبواب',
    'عطل محرك',
    'عطل لوحة تحكم',
    'مشكلة كابينة',
    'ضوضاء / اهتزاز',
    'توقف مفاجئ',
    'عطل هيدروليك',
    'عطل نظام أمان',
    'عطل إنذار طوارئ',
    'أخرى',
]

OUTCOME_MAP = {
    'solved': {'status': FAULT_STATUS_FIXED, 'needs_parts': False},
    'partial': {'status': 'قيد المعالجة', 'needs_parts': False},
    'needs_parts': {'status': 'انتظار قطع', 'needs_parts': True},
}


def empty_report() -> dict:
    return {
        'meta': {
            'visit_date': '',
            'arrival_time': '',
            'end_time': '',
            'elevator_brand': '',
            'elevator_model': '',
            'contract_type': 'عقد صيانة نشط',
            'client_description': '',
            'fault_types': [],
            'diagnosis': '',
            'action_taken': '',
            'prevention': '',
            'visit_outcome': '',
            'next_visit': '',
            'final_notes': '',
            'customer_rating': 0,
            'customer_comment': '',
            'labor_cost': 0,
        },
        'parts': [],
        'signatures': {
            'tech': '',
            'client': '',
            'tech_method': '',
            'tech_signed_by': '',
            'tech_signed_at': '',
        },
        'photos': [],
    }


def parse_fault_report_json(raw: str | None) -> dict:
    if not raw:
        return empty_report()
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return empty_report()
    base = empty_report()
    if not isinstance(data, dict):
        return base
    meta = data.get('meta') if isinstance(data.get('meta'), dict) else {}
    for key in base['meta']:
        if key in meta:
            base['meta'][key] = meta[key]
    if isinstance(data.get('parts'), list):
        base['parts'] = data['parts']
    sig = data.get('signatures') if isinstance(data.get('signatures'), dict) else {}
    for key in base['signatures']:
        base['signatures'][key] = sig.get(key) or base['signatures'].get(key) or ''
    if isinstance(data.get('photos'), list):
        base['photos'] = data['photos']
    return base


def merge_fault_report(saved: dict | None, fault) -> dict:
    """دمج JSON المحفوظ مع بيانات العطل من قاعدة البيانات."""
    merged = parse_fault_report_json(json.dumps(saved) if isinstance(saved, dict) else saved)
    meta = merged['meta']
    if fault:
        if not meta.get('client_description'):
            meta['client_description'] = fault.client_report or fault.description or ''
        if not meta.get('diagnosis'):
            meta['diagnosis'] = fault.tech_notes or ''
        if not meta.get('action_taken'):
            meta['action_taken'] = fault.resolution or ''
        if fault.fault_type and fault.fault_type not in (meta.get('fault_types') or []):
            types = list(meta.get('fault_types') or [])
            if fault.fault_type not in types:
                types.append(fault.fault_type)
            meta['fault_types'] = types
        if fault.status in (FAULT_STATUS_FIXED, FAULT_STATUS_FIXED_LEGACY):
            meta['visit_outcome'] = meta.get('visit_outcome') or 'solved'
        elif fault.status == 'انتظار قطع':
            meta['visit_outcome'] = meta.get('visit_outcome') or 'needs_parts'
    return merged


def report_has_content(data: dict) -> bool:
    meta = data.get('meta') or {}
    if meta.get('diagnosis') or meta.get('action_taken') or meta.get('visit_outcome'):
        return True
    if data.get('parts'):
        return True
    if data.get('photos'):
        return True
    sig = data.get('signatures') or {}
    return bool(sig.get('tech') or sig.get('client'))


def report_stats(data: dict) -> dict:
    meta = data.get('meta') or {}
    filled = sum(1 for k in ('diagnosis', 'action_taken', 'visit_outcome') if meta.get(k))
    return {'filled': filled, 'total': 3, 'has_report': report_has_content(data)}


def format_response_time(reported_at: datetime | None, responded_at: datetime | None) -> str:
    if not reported_at or not responded_at:
        return '—'
    delta = responded_at - reported_at
    mins = int(delta.total_seconds() // 60)
    if mins < 60:
        return f'{mins} دقيقة'
    hours = mins // 60
    rem = mins % 60
    if hours < 24:
        return f'{hours} س {rem} د' if rem else f'{hours} ساعة'
    days = hours // 24
    return f'{days} يوم'


def apply_report_to_fault(fault, data: dict, *, mark_resolved: bool = False) -> dict:
    """مزامنة حقول العطل من محضر JSON."""
    meta = data.get('meta') or {}
    fault.client_report = meta.get('client_description') or fault.client_report
    diagnosis = (meta.get('diagnosis') or '').strip()
    action = (meta.get('action_taken') or '').strip()
    prevention = (meta.get('prevention') or '').strip()
    final_notes = (meta.get('final_notes') or '').strip()
    notes_parts = [p for p in [diagnosis, prevention, final_notes] if p]
    fault.tech_notes = '\n\n'.join(notes_parts) if notes_parts else fault.tech_notes
    fault.resolution = action or fault.resolution

    outcome = meta.get('visit_outcome') or ''
    mapping = OUTCOME_MAP.get(outcome, {})
    if mapping:
        fault.status = mapping['status']
        fault.needs_parts = mapping['needs_parts']
    elif mark_resolved and fault.status in ('مفتوح', 'قيد المعالجة'):
        fault.status = FAULT_STATUS_FIXED
        fault.needs_parts = False

    if mark_resolved or fault.status in FAULT_CLOSED:
        fault.resolved_at = fault.resolved_at or datetime.utcnow()

    if not fault.responded_at and (meta.get('arrival_time') or fault.dispatched_at):
        fault.responded_at = fault.dispatched_at or datetime.utcnow()

    fault.response_time = format_response_time(fault.reported_at, fault.responded_at)
    return data
