"""أيام العمل والإجازات — من إعدادات الشركة + العطل الرسمية للدولة."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from functools import lru_cache

# Python weekday(): الاثنين=0 … الأحد=6
DEFAULT_WEEKDAYS_BY_COUNTRY: dict[str, list[int]] = {
    'SA': [6, 0, 1, 2, 3],       # الأحد–الخميس
    'AE': [6, 0, 1, 2, 3, 4],    # الأحد–الجمعة (شائع)
    'KW': [6, 0, 1, 2, 3],       # الأحد–الخميس
    'QA': [6, 0, 1, 2, 3, 4],
    'BH': [6, 0, 1, 2, 3, 4],
    'OM': [6, 0, 1, 2, 3, 4],
    'EG': [0, 1, 2, 3, 4],       # الاثنين–الجمعة
    'JO': [0, 1, 2, 3, 4],
}

COUNTRY_OPTIONS: list[tuple[str, str]] = [
    ('SA', 'السعودية'),
    ('AE', 'الإمارات'),
    ('KW', 'الكويت'),
    ('QA', 'قطر'),
    ('BH', 'البحرين'),
    ('OM', 'عُمان'),
    ('EG', 'مصر'),
    ('JO', 'الأردن'),
]

WEEKDAY_LABELS_AR: dict[int, str] = {
    0: 'الاثنين',
    1: 'الثلاثاء',
    2: 'الأربعاء',
    3: 'الخميس',
    4: 'الجمعة',
    5: 'السبت',
    6: 'الأحد',
}

WEEKDAY_ORDER_AR = [6, 0, 1, 2, 3, 4, 5]


def _get_settings():
    from models import Settings, db
    from tenant_scope import tenant_query

    try:
        from flask import has_app_context
        if not has_app_context():
            return None
        s = tenant_query(Settings).first()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None
    return s


def _parse_date_list(raw: str | None) -> set[date]:
    out: set[date] = set()
    if not raw:
        return out
    text = raw.strip()
    if not text:
        return out
    if text.startswith('['):
        try:
            items = json.loads(text)
            if isinstance(items, list):
                for item in items:
                    try:
                        out.add(date.fromisoformat(str(item)[:10]))
                    except ValueError:
                        continue
                return out
        except json.JSONDecodeError:
            pass
    for line in text.replace(',', '\n').splitlines():
        line = line.strip()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', line):
            try:
                out.add(date.fromisoformat(line))
            except ValueError:
                continue
    return out


def work_weekdays(settings=None) -> set[int]:
    s = settings if settings is not None else _get_settings()
    raw = getattr(s, 'work_weekdays_json', None) if s else None
    if raw:
        try:
            vals = json.loads(raw)
            if isinstance(vals, list) and vals:
                return {int(x) for x in vals if str(x).isdigit() or isinstance(x, int)}
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    country = work_country(settings)
    return set(DEFAULT_WEEKDAYS_BY_COUNTRY.get(country, DEFAULT_WEEKDAYS_BY_COUNTRY['SA']))


def work_country(settings=None) -> str:
    s = settings if settings is not None else _get_settings()
    code = ((getattr(s, 'work_country', None) if s else None) or 'SA').strip().upper()
    return code if code in DEFAULT_WEEKDAYS_BY_COUNTRY else 'SA'


def respect_public_holidays(settings=None) -> bool:
    s = settings if settings is not None else _get_settings()
    val = getattr(s, 'respect_public_holidays', None) if s else None
    return True if val is None else bool(val)


def custom_holidays(settings=None) -> set[date]:
    s = settings if settings is not None else _get_settings()
    return _parse_date_list(getattr(s, 'custom_holidays_json', None) if s else None)


def extra_work_days(settings=None) -> set[date]:
    s = settings if settings is not None else _get_settings()
    return _parse_date_list(getattr(s, 'extra_work_days_json', None) if s else None)


@lru_cache(maxsize=32)
def _public_holidays_cached(country: str, year: int) -> frozenset[date]:
    try:
        import holidays

        cal = holidays.country_holidays(country, years=year)
        return frozenset(cal.keys())
    except Exception:
        return frozenset()


def public_holidays_for_year(year: int, settings=None) -> set[date]:
    if not respect_public_holidays(settings):
        return set()
    country = work_country(settings)
    return set(_public_holidays_cached(country, year))


def non_working_reason(d: date, settings=None) -> str | None:
    if d in extra_work_days(settings):
        return None
    if d.weekday() not in work_weekdays(settings):
        return f'يوم {WEEKDAY_LABELS_AR.get(d.weekday(), "عطلة أسبوعية")}'
    if d in custom_holidays(settings):
        return 'إجازة مخصّصة للشركة'
    if respect_public_holidays(settings) and d in public_holidays_for_year(d.year, settings):
        return 'عطلة رسمية'
    return None


def is_working_day(d: date, settings=None) -> bool:
    return non_working_reason(d, settings) is None


def next_working_day(d: date, settings=None) -> date:
    cur = d
    for _ in range(370):
        if is_working_day(cur, settings):
            return cur
        cur += timedelta(days=1)
    return d


def next_working_day_after(d: date, settings=None) -> date:
    return next_working_day(d + timedelta(days=1), settings)


def adjust_to_working_day(d: date, settings=None) -> date:
    return next_working_day(d, settings)


def work_days_between(start: date, end: date, settings=None) -> list[date]:
    if end < start:
        start, end = end, start
    days: list[date] = []
    cur = start
    while cur <= end:
        if is_working_day(cur, settings):
            days.append(cur)
        cur += timedelta(days=1)
    return days


def work_day_validation_error(d: date, settings=None) -> str | None:
    reason = non_working_reason(d, settings)
    if not reason:
        return None
    nxt = next_working_day(d, settings)
    hint = f' أقرب يوم عمل: {nxt.isoformat()}' if nxt != d else ''
    return f'التاريخ {d.isoformat()} — {reason}.{hint}'


def work_calendar_summary(settings=None) -> dict:
    s = settings if settings is not None else _get_settings()
    weekdays = sorted(work_weekdays(s), key=lambda w: WEEKDAY_ORDER_AR.index(w))
    country = work_country(s)
    country_label = dict(COUNTRY_OPTIONS).get(country, country)
    return {
        'country': country,
        'country_label': country_label,
        'weekdays': weekdays,
        'weekday_labels': [WEEKDAY_LABELS_AR[w] for w in weekdays],
        'work_hours_start': (getattr(s, 'work_hours_start', None) or '08:00') if s else '08:00',
        'work_hours_end': (getattr(s, 'work_hours_end', None) or '17:00') if s else '17:00',
        'respect_public_holidays': respect_public_holidays(s),
        'custom_holidays': sorted(d.isoformat() for d in custom_holidays(s)),
        'extra_work_days': sorted(d.isoformat() for d in extra_work_days(s)),
    }


def month_calendar(ym: str, settings=None) -> dict:
    year, month = map(int, ym.split('-', 1))
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    work = work_days_between(start, end, settings)
    off: list[dict] = []
    cur = start
    while cur <= end:
        reason = non_working_reason(cur, settings)
        if reason:
            off.append({'date': cur.isoformat(), 'reason': reason})
        cur += timedelta(days=1)
    return {
        'month': ym,
        'work_days': [d.isoformat() for d in work],
        'non_work_days': off,
        'summary': work_calendar_summary(settings),
    }
