"""ترقيم عقود التجديد: تثبيت الأساس + سنة التعاقد (CN-00042-2026)."""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Optional

# CN-00042 أو CN-00042-2026 أو CN-00042/2026 أو CN-00042-2026-2
_YEAR_SUFFIX = re.compile(r'^(.+?)[-/](20\d{2})(?:-(\d+))?$', re.IGNORECASE)


def contract_base_code(code: Optional[str]) -> str:
    """يعيد أساس رقم العقد بدون سنة التجديد."""
    raw = (code or '').strip()
    if not raw:
        return ''
    m = _YEAR_SUFFIX.match(raw)
    if m:
        return m.group(1).strip()
    return raw


def contract_year_from_code(code: Optional[str]) -> Optional[int]:
    raw = (code or '').strip()
    m = _YEAR_SUFFIX.match(raw)
    if not m:
        return None
    try:
        return int(m.group(2))
    except (TypeError, ValueError):
        return None


def renewal_contract_code(existing_code: Optional[str], year: int) -> str:
    """
    رقم التجديد: الأساس-السنة.
    مثال: CN-00042 → CN-00042-2026
         CN-00042-2025 → CN-00042-2026
    """
    base = contract_base_code(existing_code)
    if not base:
        base = 'CN-00000'
    year = int(year)
    if year < 2000 or year > 2100:
        raise ValueError('سنة تعاقد غير صالحة')
    return f'{base}-{year}'


def unique_renewal_contract_code(existing_code: Optional[str], year: int, taken_codes) -> str:
    """يضمن فرادة الكود داخل المستأجر؛ إن وُجد تعارض يضيف -2، -3…"""
    candidate = renewal_contract_code(existing_code, year)
    taken = {str(c).strip() for c in (taken_codes or []) if c}
    if candidate not in taken:
        return candidate
    n = 2
    while True:
        alt = f'{candidate}-{n}'
        if alt not in taken:
            return alt
        n += 1
        if n > 99:
            raise ValueError('تعذّر توليد رقم عقد فريد للتجديد')


def _contract_sort_key(contract) -> tuple:
    start = getattr(contract, 'start_date', None) or date.min
    end = getattr(contract, 'end_date', None) or date.min
    cid = int(getattr(contract, 'id', 0) or 0)
    return (start, end, cid)


def build_superseded_contract_ids(contracts: Iterable) -> set[int]:
    """معرّفات العقود التي لها عقد أحدث بنفس أساس الرقم (تم تجديدها)."""
    from collections import defaultdict

    by_base: dict[str, list] = defaultdict(list)
    for c in contracts or []:
        base = contract_base_code(getattr(c, 'code', None))
        if not base:
            continue
        if getattr(c, 'id', None) is None:
            continue
        by_base[base].append(c)

    superseded: set[int] = set()
    for group in by_base.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=_contract_sort_key)
        for c in ordered[:-1]:
            superseded.add(int(c.id))
    return superseded
