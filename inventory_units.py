"""قواعد عرض وإدخال كميات المخزون حسب وحدة الصنف."""

from __future__ import annotations

DECIMAL_UNIT_HINTS = (
    'لتر', 'liter', 'litre', 'lit',
    'متر', 'meter', 'metre', 'm²', 'm2', 'sqm',
    'كيل', 'كجم', 'kg', 'kilogram',
    'جرام', 'gram', 'g ',
    'طن', 'ton', 'tonne',
    'قدم', 'foot', 'ft',
    'مل', 'ml', 'mm', 'سم', 'cm',
)

INTEGER_UNIT_HINTS = (
    'قطعة', 'حبة', 'علبة', 'كرتون', 'رول', 'زوج', 'مجمو', 'باك',
    'pcs', 'pc', 'piece', 'unit', 'box', 'roll', 'set', 'ea', 'each',
    'عدد', 'حزم', 'حزمة', 'كيس', 'ظرف', 'طقم',
)


def _norm_unit(unit: str | None) -> str:
    return (unit or '').strip().lower().replace('ـ', '')


def unit_allows_decimals(unit: str | None) -> bool:
    """هل الوحدة تقبل كسوراً عشرية؟ الافتراضي: لا (قطعة وما شابه)."""
    u = _norm_unit(unit)
    if not u:
        return False
    for hint in DECIMAL_UNIT_HINTS:
        if hint in u:
            return True
    for hint in INTEGER_UNIT_HINTS:
        if hint in u:
            return False
    return False


def normalize_inventory_qty(qty, unit: str | None) -> float:
    """توحيد الكمية للحفظ — يرفض الكسور لوحدة عددية."""
    q = float(qty or 0)
    if q <= 0:
        raise ValueError('أدخل كمية أكبر من صفر')
    if unit_allows_decimals(unit):
        return round(q, 4)
    rounded = int(round(q))
    if abs(q - rounded) > 1e-9:
        label = (unit or 'قطعة').strip() or 'قطعة'
        raise ValueError(f'وحدة «{label}» لا تقبل كسور — أدخل عدداً صحيحاً')
    return float(rounded)


def normalize_inventory_qty_field(qty, unit: str | None) -> float:
    """توحيد حقل رصيد/حد أدنى — يسمح بالصفر."""
    q = float(qty or 0)
    if q < 0:
        raise ValueError('الكمية لا يمكن أن تكون سالبة')
    if q == 0:
        return 0.0
    return normalize_inventory_qty(q, unit)


def format_inventory_qty(qty, unit: str | None = None) -> str:
    """عرض الكمية بدون علامة عشرية للوحدات العددية."""
    q = float(qty or 0)
    if not unit_allows_decimals(unit):
        return str(int(round(q)))
    if abs(q - round(q)) < 1e-9:
        return str(int(round(q)))
    text = f'{q:.4f}'.rstrip('0').rstrip('.')
    return text or '0'
