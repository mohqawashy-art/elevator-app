"""LiftCore — بيانات طباعة عقد CN0000 (مطابق لملف Word)."""
from __future__ import annotations

import re
from datetime import date, datetime

from models import Contract, Elevator, Settings

# نص ثابت من CN0000.docx — لا يُغيّر
CONTRACT_TITLE = 'صيانة مصاعد سنوي بدون قطع الغيار (عادي)'

AR_WEEKDAYS = [
    'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد'
]

PRINT_DEFAULTS = {
    'company_name': '',
    'city': '',
    'city_full': '',
    'phone': '',
    'email': '',
    'rep_name': '',
    'rep_mobile': '',
}

MAINT_FREQ_PHRASE = {
    'شهري': 'مرة شهريا',
    'كل شهرين': 'مرة كل شهرين',
    'ربع سنوي': 'مرة كل ثلاثة أشهر',
    'نصف سنوي': 'مرة كل ستة أشهر',
    'سنوي': 'مرة سنويا',
}

PAY_TERMS_PHRASE = {
    'دفعة واحدة': 'مقدم',
    'مقدم': 'مقدم',
    'ربع سنوي': 'ربع سنوي',
    'نصف سنوي': 'نصف سنوي',
    'سنوي': 'سنوي',
}


def _gregorian_to_jdn(year: int, month: int, day: int) -> int:
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return (
        day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    )


def _jdn_to_hijri(jdn: int) -> tuple[int, int, int]:
    jdn = int(jdn)
    l = jdn - 1948440 + 10632
    n = (l - 1) // 10631
    l = l - 10631 * n + 354
    j = (
        ((10985 - l) // 5316) * ((50 * l) // 17719)
        + (l // 5670) * ((43 * l) // 15238)
    )
    l = (
        l
        - ((30 - j) // 15) * ((17719 * j) // 50)
        - (j // 16) * ((15238 * j) // 43)
        + 29
    )
    month = (24 * l) // 709
    day = l - (709 * month) // 24
    year = 30 * n + j - 30
    return year, month, day


def gregorian_to_hijri(d: date) -> tuple[int, int, int]:
    return _jdn_to_hijri(_gregorian_to_jdn(d.year, d.month, d.day))


def fmt_gregorian(d: date | None) -> str:
    if not d:
        return '—'
    return f'{d.day:02d}/{d.month:02d}/{d.year}'


def fmt_hijri(d: date | None) -> str:
    if not d:
        return '—'
    hy, hm, hd = gregorian_to_hijri(d)
    return f'{hd:02d}/{hm:02d}/{hy} هـ'


def weekday_ar(d: date | None) -> str:
    if not d:
        return '—'
    return AR_WEEKDAYS[d.weekday()]


def _under100(n: int) -> str:
    ones = [
        '', 'واحد', 'اثنان', 'ثلاثة', 'أربعة', 'خمسة', 'ستة', 'سبعة', 'ثمانية', 'تسعة',
        'عشرة', 'أحد عشر', 'اثنا عشر', 'ثلاثة عشر', 'أربعة عشر', 'خمسة عشر',
        'ستة عشر', 'سبعة عشر', 'ثمانية عشر', 'تسعة عشر',
    ]
    tens = [
        '', '', 'عشرون', 'ثلاثون', 'أربعون', 'خمسون', 'ستون', 'سبعون', 'ثمانون', 'تسعون',
    ]
    if n < 20:
        return ones[n]
    t, o = divmod(n, 10)
    if o == 0:
        return tens[t]
    return ones[o] + ' و' + tens[t]


def _under1000(n: int) -> str:
    if n < 100:
        return _under100(n)
    h, r = divmod(n, 100)
    hundreds = {
        1: 'مائة', 2: 'مئتان', 3: 'ثلاثمائة', 4: 'أربعمائة', 5: 'خمسمائة',
        6: 'ستمائة', 7: 'سبعمائة', 8: 'ثمانمائة', 9: 'تسعمائة',
    }
    head = hundreds.get(h, _under100(h) + ' مائة')
    if r == 0:
        return head
    return head + ' و' + _under100(r)


def amount_in_words(amount: float) -> str:
    n = int(round(amount or 0))
    if n == 0:
        return 'صفر'
    if n < 0:
        return 'سالب ' + amount_in_words(-n)

    parts: list[str] = []
    thousands, n = divmod(n, 1000)
    if thousands:
        if thousands == 1:
            parts.append('ألف')
        elif thousands == 2:
            parts.append('ألفان')
        elif 3 <= thousands <= 10:
            parts.append(_under100(thousands) + ' آلاف')
        else:
            parts.append(_under1000(thousands) + ' ألف')
    if n:
        parts.append(_under1000(n))
    return ' و'.join(parts)


def format_contract_code(code: str | None) -> str:
    """CN-00001 → CN0001 (كما في Word)."""
    if not code:
        return 'CN0000'
    digits = re.sub(r'\D', '', code)
    if not digits:
        return code
    return 'CN' + digits.zfill(4)[-4:]


def company_info() -> dict:
    """بيانات الطرف الأول من إعدادات الشركة المشغّلة للبرنامج."""
    s = Settings.query.first()
    info = dict(PRINT_DEFAULTS)
    if not s:
        return info
    info['company_name'] = (s.company_name or '').strip()
    info['phone'] = (s.phone or '').strip()
    info['email'] = (s.email or '').strip()
    info['rep_name'] = (getattr(s, 'rep_name', None) or '').strip()
    info['rep_mobile'] = (getattr(s, 'rep_mobile', None) or '').strip()
    city = (s.city or '').strip()
    info['city'] = city
    if city in ('مكة', 'مكة المكرمة') or 'مكة' in city:
        info['city_full'] = 'مكة المكرمة' if 'مكرمة' in city or city == 'مكة' else city
    else:
        info['city_full'] = city or (s.address or '').strip()
    return info


def customer_address_line(customer) -> str:
    """سطر العنوان كما في Word: وعنوانه / ..."""
    if not customer:
        return '—'
    city = (customer.city or '').strip()
    if city in ('مكة', 'مكة المكرمة'):
        return 'مكة المكرمــــة –'
    parts = []
    if customer.address:
        parts.append(customer.address.strip())
    if customer.district:
        parts.append(customer.district)
    if city and city not in str(parts):
        parts.append(city)
    return ' — '.join(parts) if parts else '—'


def elevators_for_contract(contract: Contract) -> list[dict]:
    ids = [ce.elevator_id for ce in contract.elevators]
    if not ids:
        return [{
            'type': '',
            'floors': '',
            'doors': '',
            'capacity': '',
        }]
    rows = Elevator.query.filter(Elevator.id.in_(ids)).all()
    out = []
    for e in rows:
        out.append({
            'type': e.elev_type or '',
            'floors': str(e.floors) if e.floors is not None else '',
            'doors': '',
            'capacity': str(e.capacity_kg) if e.capacity_kg else '',
        })
    return out


def contract_print_payload(contract_id: int) -> dict:
    contract = Contract.query.get_or_404(contract_id)
    customer = contract.customer
    sign_date = contract.start_date or date.today()
    elevators = elevators_for_contract(contract)
    elevator_count = len(contract.elevators) or 1
    company = company_info()
    amount = int(round(contract.value or contract.total or 0))
    maint = contract.maint_frequency or 'شهري'
    pay = contract.payment_terms or 'دفعة واحدة'

    return {
        'contract': contract,
        'customer': customer,
        'company': company,
        'elevators': elevators,
        'elevator_count': elevator_count,
        'title': CONTRACT_TITLE,
        'contract_code': format_contract_code(contract.code),
        'sign_day': weekday_ar(sign_date),
        'sign_hijri': fmt_hijri(sign_date),
        'sign_gregorian': fmt_gregorian(sign_date),
        'start_gregorian': fmt_gregorian(contract.start_date),
        'end_gregorian': fmt_gregorian(contract.end_date),
        'customer_address': customer_address_line(customer),
        'maint_phrase': MAINT_FREQ_PHRASE.get(maint, 'مرة شهريا'),
        'pay_phrase': PAY_TERMS_PHRASE.get(pay, 'مقدم'),
        'amount': amount,
        'amount_words': amount_in_words(amount),
    }
