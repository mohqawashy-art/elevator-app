"""ترقيم العقود: بادئة حسب النوع + تجديد بالأساس-السنة (CN-00042-2026)."""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Optional

# صيانة/ضمان/طوارئ: CN-##### — تركيب/تحديث: CI-##### (تسلسل واحد)
CONTRACT_CODE_DIGITS = 5
CONTRACT_PREFIX_MAINTENANCE = 'CN-'
CONTRACT_PREFIX_INSTALLATION = 'CI-'

# CN-00042 أو CI-00003 أو CN-00042-2026 أو CN-00042/2026 أو CN-00042-2026-2
_YEAR_SUFFIX = re.compile(r'^(.+?)[-/](20\d{2})(?:-(\d+))?$', re.IGNORECASE)
_PADDED_CODE = re.compile(
    r'^(CN|CI)-(\d+)(?:[-/](20\d{2})(?:-(\d+))?)?$',
    re.IGNORECASE,
)


def normalize_contract_code(code: Optional[str]) -> str:
    """تطبيع رقم العقد مع الإبقاء على لاحقة سنة التجديد."""
    raw = (code or '').strip().upper().replace(' ', '')
    if not raw:
        return ''
    m = _PADDED_CODE.match(raw)
    if not m:
        return raw
    prefix, num, year, suf = m.group(1).upper(), int(m.group(2)), m.group(3), m.group(4)
    out = f'{prefix}-{num:05d}'
    if year:
        out = f'{out}-{year}'
        if suf:
            out = f'{out}-{suf}'
    return out


def contract_prefix_for_type(contract_type: Optional[str]) -> str:
    """بادئة كود العقد حسب النوع — تسلسل مستقل لكل بادئة.

    صيانة/ضمان/طوارئ → CN-
    تركيب أو تحديث (modernization) → CI- (نفس التسلسل)
    """
    raw = (contract_type or '').strip().lower()
    if not raw:
        return CONTRACT_PREFIX_MAINTENANCE
    if any(
        k in raw
        for k in (
            'تركيب',
            'تحديث',
            'installation',
            'install',
            'upgrade',
            'modern',
        )
    ):
        return CONTRACT_PREFIX_INSTALLATION
    return CONTRACT_PREFIX_MAINTENANCE


def is_installation_contract_type(contract_type: Optional[str]) -> bool:
    """True لعقود التركيب/التحديث فقط (ليست صيانة أو ضمان)."""
    return contract_prefix_for_type(contract_type) == CONTRACT_PREFIX_INSTALLATION


def is_maintenance_contract_type(contract_type: Optional[str]) -> bool:
    """True لعقود الصيانة/الضمان/الطوارئ (ليست تركيب أو تحديث)."""
    return not is_installation_contract_type(contract_type)


def contract_matches_scope(contract_type: Optional[str], scope: Optional[str]) -> bool:
    """scope: maintenance | installation | فارغ = الكل."""
    key = (scope or '').strip().lower()
    if key == 'installation':
        return is_installation_contract_type(contract_type)
    if key == 'maintenance':
        return is_maintenance_contract_type(contract_type)
    return True


def contracts_for_scope(contracts: Iterable, scope: Optional[str]) -> list:
    """صفّ عقود قائمة حسب نطاق القسم."""
    key = (scope or '').strip().lower()
    if key not in ('maintenance', 'installation'):
        return list(contracts or [])
    return [c for c in (contracts or []) if contract_matches_scope(getattr(c, 'contract_type', None), key)]


def customer_matches_scope(customer, scope: Optional[str]) -> bool:
    """عميل يظهر في نطاق القسم حسب العقود (أو مشاريع/فرص التركيب لنطاق التركيب)."""
    key = (scope or '').strip().lower()
    if key not in ('maintenance', 'installation'):
        return True
    contracts = list(getattr(customer, 'contracts', None) or [])
    if any(contract_matches_scope(getattr(c, 'contract_type', None), key) for c in contracts):
        return True
    if key == 'installation':
        # عملاء مرتبطون بفرص/مشاريع تركيب حتى قبل إنشاء عقد CI
        if list(getattr(customer, 'installation_projects', None) or []):
            return True
        if list(getattr(customer, 'installation_leads', None) or []):
            return True
    return False


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
         CI-00003-2025 → CI-00003-2026
    """
    base = contract_base_code(existing_code)
    if not base:
        base = f'{CONTRACT_PREFIX_MAINTENANCE}{"0" * CONTRACT_CODE_DIGITS}'
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
