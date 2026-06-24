"""تحقق من نماذج الإدخال — رسائل خطأ عربية أو None."""

from __future__ import annotations


def _str(val) -> str:
    return (val or '').strip()


def customer_name_error(name, customer_id=None):
    from models import Customer

    cleaned = _str(name)
    if not cleaned:
        return 'يرجى إدخال اسم العميل'
    norm = cleaned.lower()
    for customer in Customer.query.all():
        if customer_id and customer.id == customer_id:
            continue
        if customer.name and customer.name.strip().lower() == norm:
            return f'اسم العميل «{customer.name}» مستخدم مسبقاً ({customer.code})'
    return None


def elevator_form_error(form, parse_int=None):
    parse_int = parse_int or (lambda v: int(v) if str(v or '').strip().isdigit() else 0)
    if not _str(form.get('customer_id')):
        return 'يرجى اختيار العميل'
    floors = parse_int(form.get('floors'))
    if floors is not None and floors < 0:
        return 'عدد الوقفات غير صالح'
    capacity = parse_int(form.get('capacity_kg'))
    if capacity is not None and capacity < 0:
        return 'الحمولة غير صالحة'
    return None


def contract_form_error(form, money_round=None):
    money_round = money_round or (lambda v: float(v or 0))
    if not _str(form.get('customer_id')):
        return 'يرجى اختيار العميل'
    start = _str(form.get('start_date'))
    end = _str(form.get('end_date'))
    if start and end and start > end:
        return 'تاريخ نهاية العقد يجب أن يكون بعد تاريخ البداية'
    try:
        value = money_round(form.get('value', 0))
    except (TypeError, ValueError):
        return 'قيمة العقد غير صالحة'
    if value < 0:
        return 'قيمة العقد لا يمكن أن تكون سالبة'
    return None


def visit_form_error(form, parse_technician_ids=None):
    if not _str(form.get('elevator_id')):
        return 'يرجى اختيار المصعد'
    if not _str(form.get('visit_date')):
        return 'يرجى إدخال تاريخ الزيارة'
    if parse_technician_ids:
        try:
            tech_ids = parse_technician_ids(form)
        except (TypeError, ValueError):
            tech_ids = []
        if not tech_ids:
            return 'يرجى اختيار فني واحد على الأقل'
    return None


def fault_close_error(status, resolution):
    from operations import FAULT_CLOSED

    status = _str(status)
    if status in FAULT_CLOSED and not _str(resolution):
        return 'عند إغلاق العطل يجب إدخال طريقة الحل'
    return None


def invoice_amount_error(amount):
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        return 'مبلغ الفاتورة غير صالح'
    if value <= 0:
        return 'مبلغ الفاتورة يجب أن يكون أكبر من صفر'
    return None


def inventory_form_error(form):
    name = _str(form.get('name'))
    if not name:
        return 'يرجى إدخال اسم الصنف'
    for field, label in (
        ('current_qty', 'الكمية الحالية'),
        ('min_qty', 'الحد الأدنى'),
        ('buy_price', 'سعر الشراء'),
        ('sell_price', 'سعر البيع'),
    ):
        raw = _str(form.get(field))
        if not raw:
            continue
        try:
            if float(raw) < 0:
                return f'{label} لا يمكن أن يكون سالباً'
        except (TypeError, ValueError):
            return f'{label} غير صالح'
    return None
