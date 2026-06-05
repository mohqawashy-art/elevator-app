"""
LiftCore — قوالب قائمة الفحص (SaaS-ready)

كل مستأجر (tenant) يمكنه لاحقاً اختيار template_key مختلف من الإعدادات.
الزيارة تحفظ template_key المستخدم وقت التنفيذ حتى لو تغيّر القالب لاحقاً.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

DEFAULT_TEMPLATE_KEY = 'liftcore_standard_v1'

# قالب افتراضي — 5 أقسام (مطابق لمحضر الصيانة)
TEMPLATES: dict[str, dict[str, Any]] = {
    DEFAULT_TEMPLATE_KEY: {
        'key': DEFAULT_TEMPLATE_KEY,
        'version': 1,
        'name_ar': 'محضر صيانة مصعد — قياسي',
        'name_en': 'Standard elevator maintenance checklist',
        'sections': [
            {
                'id': 1,
                'title_ar': 'غرفة الماكينة',
                'title_en': 'Machine Room',
                'items': [
                    {'id': '1_0', 'ar': 'فحص زيت المحرك والتأكد من سيره الطبيعي', 'en': 'Check motor oil and normal operation'},
                    {'id': '1_1', 'ar': 'فحص عمل الفرامل وتضبيطه وتشحيم المحاور', 'en': 'Check brake system and lubricate axles'},
                    {'id': '1_2', 'ar': 'التأكد من عدم وجود تسريب زيت', 'en': 'Check for oil leaks'},
                    {'id': '1_3', 'ar': 'فحص منظم السرعة وضبطه', 'en': 'Check and adjust speed governor'},
                    {'id': '1_4', 'ar': 'تنظيف أرضية الغرفة', 'en': 'Clean machine room floor'},
                    {'id': '1_5', 'ar': 'التأكد من عدم وجود تهريب مياه بالغرفة', 'en': 'Check for water leaks in machine room'},
                    {'id': '1_6', 'ar': 'التأكد من عدم وجود أي تخزين بالغرفة', 'en': 'Ensure no storage items in machine room'},
                    {'id': '1_7', 'ar': 'التأكد من تشغيل المكيف بحالة سليمة', 'en': 'Check AC unit is working properly'},
                    {'id': '1_8', 'ar': 'التأكد من السلم إلى غرفة الماكينة', 'en': 'Check ladder access to machine room'},
                ],
            },
            {
                'id': 2,
                'title_ar': 'بئر المصعد',
                'title_en': 'Elevator Shaft',
                'items': [
                    {'id': '2_0', 'ar': 'فحص جهاز الريفيزيون في حالة الصعود والهبوط والتوقف', 'en': 'Check revision device (up/down/stop)'},
                    {'id': '2_1', 'ar': 'فحص حبال الجر وتثبيتات الحبال', 'en': 'Check traction ropes and rope fastenings'},
                    {'id': '2_2', 'ar': 'فحص بكرات الحبال والتأكد من سلامتها', 'en': 'Check rope pulleys integrity'},
                    {'id': '2_3', 'ar': 'تزييت وتشحيم أدلة سير الصاعدة والثقل', 'en': 'Lubricate guide rails for cabin and counterweight'},
                    {'id': '2_4', 'ar': 'فحص كراسي الثقل والكابينة', 'en': 'Check counterweight and cabin frames'},
                ],
            },
            {
                'id': 3,
                'title_ar': 'داخل الصاعدة',
                'title_en': 'Inside the Cabin',
                'items': [
                    {'id': '3_0', 'ar': 'الكشف على أزرار التحكم والتشغيل', 'en': 'Check control and operation buttons'},
                    {'id': '3_1', 'ar': 'الكشف على الإنارة والجرس والإنتركوم والمروحة', 'en': 'Check lighting, bell, intercom, and fan'},
                    {'id': '3_2', 'ar': 'تنظيف مجاري الأبواب', 'en': 'Clean door tracks and guides'},
                ],
            },
            {
                'id': 4,
                'title_ar': 'أبواب الطوابق',
                'title_en': 'Landing Doors',
                'items': [
                    {'id': '4_0', 'ar': 'فحص أبواب الأدوار وضبطها', 'en': 'Check and adjust landing doors'},
                    {'id': '4_1', 'ar': 'فحص الباب الداخلي وضبطه', 'en': 'Check and adjust cabin door'},
                    {'id': '4_2', 'ar': 'فحص الكبسات والمؤشرات والمبينات وتضبيط الإضاءة', 'en': 'Check buttons, indicators, displays, and lighting'},
                ],
            },
            {
                'id': 5,
                'title_ar': 'حفرة البئر',
                'title_en': 'Shaft Pit',
                'items': [
                    {'id': '5_0', 'ar': 'الكشف على بكرة منظم السرعة', 'en': 'Check speed governor pulley'},
                    {'id': '5_1', 'ar': 'تنظيف وفحص قواطع نهاية المشوار', 'en': 'Clean and check limit switches'},
                    {'id': '5_2', 'ar': 'تنظيف الحفرة', 'en': 'Clean the pit'},
                    {'id': '5_3', 'ar': 'إذا يوجد "إيماتيك" في المصعد، تأكد عن عمله', 'en': 'Check IMATIC system if available'},
                    {'id': '5_4', 'ar': 'تأكد عن ربط المصعد مع لوحة إنذار الحريق إن وجد', 'en': 'Verify connection to fire alarm panel if exists'},
                ],
            },
        ],
    },
}


def get_template(template_key: str | None = None) -> dict[str, Any]:
    key = (template_key or DEFAULT_TEMPLATE_KEY).strip()
    tpl = TEMPLATES.get(key)
    if not tpl:
        tpl = TEMPLATES[DEFAULT_TEMPLATE_KEY]
    return deepcopy(tpl)


def template_for_settings(settings_row=None) -> dict[str, Any]:
    """لاحقاً: قراءة checklist_template_key من إعدادات المستأجر."""
    key = DEFAULT_TEMPLATE_KEY
    if settings_row is not None:
        key = getattr(settings_row, 'checklist_template_key', None) or key
    return get_template(key)


def empty_report_data(template_key: str | None = None) -> dict[str, Any]:
    tpl = get_template(template_key)
    items: dict[str, dict[str, str]] = {}
    for sec in tpl['sections']:
        for item in sec['items']:
            items[item['id']] = {'status': '', 'note': ''}
    return {
        'template_key': tpl['key'],
        'template_version': tpl['version'],
        'items': items,
        'meta': {
            'overall_status': 'جيدة',
            'arrival_time': '',
            'end_time': '',
            'tech_notes': '',
            'issues_found': '',
            'parts_used': '',
            'next_visit': '',
        },
        'signatures': {'tech': '', 'client': ''},
        'photos': [],
    }


def parse_report_json(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (TypeError, json.JSONDecodeError):
        return None


def merge_report_data(saved: dict[str, Any] | None, template_key: str | None = None) -> dict[str, Any]:
    base = empty_report_data(template_key or (saved or {}).get('template_key'))
    if not saved:
        return base
    base['template_key'] = saved.get('template_key') or base['template_key']
    base['template_version'] = saved.get('template_version') or base['template_version']
    for item_id, val in (saved.get('items') or {}).items():
        if item_id in base['items'] and isinstance(val, dict):
            base['items'][item_id] = {
                'status': val.get('status') or '',
                'note': val.get('note') or '',
            }
    meta = saved.get('meta') or {}
    if isinstance(meta, dict):
        base['meta'].update({k: meta.get(k) or base['meta'].get(k, '') for k in base['meta']})
    sig = saved.get('signatures') or {}
    if isinstance(sig, dict):
        base['signatures']['tech'] = sig.get('tech') or ''
        base['signatures']['client'] = sig.get('client') or ''
    if isinstance(saved.get('photos'), list):
        base['photos'] = saved['photos']
    return base


def report_completion_stats(data: dict[str, Any] | None, template_key: str | None = None) -> dict[str, int]:
    tpl = get_template(template_key or (data or {}).get('template_key'))
    total = sum(len(s['items']) for s in tpl['sections'])
    if not data:
        return {'total': total, 'filled': 0, 'percent': 0}
    items = data.get('items') or {}
    filled = sum(1 for sec in tpl['sections'] for it in sec['items'] if (items.get(it['id']) or {}).get('status'))
    return {'total': total, 'filled': filled, 'percent': round(100 * filled / total) if total else 0}


def checklist_summary_lines(data: dict[str, Any], template_key: str | None = None) -> list[str]:
    """ملخص نصي للأعمال المنفذة من قائمة الفحص."""
    tpl = get_template(template_key or data.get('template_key'))
    items = data.get('items') or {}
    status_ar = {'ok': 'سليم', 'repair': 'يحتاج إصلاح', 'na': 'لا ينطبق'}
    lines: list[str] = []
    for sec in tpl['sections']:
        for it in sec['items']:
            st = (items.get(it['id']) or {}).get('status') or ''
            if not st or st == 'not-checked':
                continue
            line = f"• {it['ar']}: {status_ar.get(st, st)}"
            note = (items.get(it['id']) or {}).get('note') or ''
            if note.strip():
                line += f" ({note.strip()})"
            lines.append(line)
    return lines
