"""حساب تكلفة إنشاء/تركيب مصعد — أسعار افتراضية قابلة للتعديل في الواجهة."""

DEFAULT_VAT_PCT = 15.0
DEFAULT_MARGIN_PCT = 12.0

# أسعار تقريبية بالريال السعودي (مرجعية — تُعدَّل قبل الحفظ)
RATE_TABLE = {
    'MR': {
        'machine_base': 85000,
        'machine_per_kg_over_630': 28,
        'rail_per_floor': 4800,
        'cabin': 45000,
        'door_automatic': 8800,
        'control_panel': 32000,
        'electrical_package': 18000,
        'install_per_floor': 6000,
        'commissioning': 14000,
        'transport_crane': 9000,
        'shaft_prep_per_floor': 3500,
    },
    'MRL': {
        'machine_base': 98000,
        'machine_per_kg_over_630': 32,
        'rail_per_floor': 5200,
        'cabin': 48000,
        'door_automatic': 9500,
        'control_panel': 35000,
        'electrical_package': 20000,
        'install_per_floor': 6500,
        'commissioning': 15000,
        'transport_crane': 9500,
        'shaft_prep_per_floor': 3800,
    },
    'Hydraulic': {
        'machine_base': 72000,
        'machine_per_kg_over_630': 22,
        'rail_per_floor': 4200,
        'cabin': 40000,
        'door_automatic': 7800,
        'control_panel': 26000,
        'electrical_package': 16000,
        'install_per_floor': 5500,
        'commissioning': 12000,
        'transport_crane': 8500,
        'shaft_prep_per_floor': 3200,
    },
}

MACHINE_TYPES = ('MR', 'MRL', 'Hydraulic')
ELEV_TYPES = ('مصعد ركاب', 'مصعد بضائع', 'مصعد مستشفى', 'مصعد منزلي')
ESTIMATE_STATUSES = ('مسودة', 'معتمد', 'ملغي')


def _safe_int(value, default=0, minimum=0):
    try:
        n = int(float(value or 0))
    except (TypeError, ValueError):
        n = default
    return max(n, minimum)


def _safe_float(value, default=0.0):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _line(category, description, quantity, unit, unit_price):
    qty = _safe_float(quantity, 1)
    price = _safe_float(unit_price, 0)
    return {
        'category': category,
        'description': description,
        'quantity': qty,
        'unit': unit,
        'unit_price': price,
        'line_total': round(qty * price, 2),
    }


def calculate_lines(spec):
    """يُرجع قائمة بنود التكلفة من مواصفات المشروع."""
    machine_type = (spec.get('machine_type') or 'MR').strip()
    if machine_type not in RATE_TABLE:
        machine_type = 'MR'
    rates = RATE_TABLE[machine_type]

    floors = _safe_int(spec.get('floors'), 2, minimum=2)
    stops = _safe_int(spec.get('stops'), floors, minimum=2)
    if stops > floors:
        stops = floors
    capacity = _safe_int(spec.get('capacity_kg'), 630, minimum=400)
    doors = _safe_int(spec.get('doors_count'), stops, minimum=1)
    include_install = str(spec.get('include_installation', '1')).lower() not in ('0', 'false', 'no')
    include_shaft = str(spec.get('include_shaft_work', '0')).lower() in ('1', 'true', 'yes')
    elev_type = (spec.get('elev_type') or 'مصعد ركاب').strip()

    machine_price = rates['machine_base']
    if capacity > 630:
        machine_price += (capacity - 630) * rates['machine_per_kg_over_630']
    if elev_type == 'مصعد بضائع':
        machine_price *= 1.12
    elif elev_type == 'مصعد مستشفى':
        machine_price *= 1.08

    lines = [
        _line('مكينة', f'مجموعة مكينة {machine_type} — {capacity} كجم', 1, 'مجموعة', machine_price),
        _line('كابينة', f'كابينة {elev_type}', 1, 'كابينة', rates['cabin']),
        _line('مزلاق', f'مزلاق وأوزان — {floors} طوابق', floors, 'طابق', rates['rail_per_floor']),
        _line('أبواب', f'أبواب أوتوماتيك — {doors} باب', doors, 'باب', rates['door_automatic']),
        _line('تحكم', 'لوحة تحكم + محول VVVF + أجهزة أمان', 1, 'مجموعة', rates['control_panel']),
        _line('كهرباء', 'كابلات + حبال + تمديدات كهربائية', 1, 'مجموعة', rates['electrical_package']),
    ]

    if include_install:
        lines.append(
            _line('تركيب', f'تركيب وتشغيل — {stops} محطة', stops, 'محطة', rates['install_per_floor'])
        )
        lines.append(
            _line('تشغيل', 'تشغيل تجريبي + فحص + تسليم', 1, 'مرة', rates['commissioning'])
        )
        lines.append(
            _line('نقل', 'نقل ومعدات رفع', 1, 'مرة', rates['transport_crane'])
        )

    if include_shaft:
        lines.append(
            _line('بئر', f'أعمال بئر/هيكل — {floors} طابق', floors, 'طابق', rates['shaft_prep_per_floor'])
        )

    return lines


def summarize_lines(lines, margin_pct=None, vat_pct=None):
    """يحسب الإجماليات من البنود."""
    margin_pct = _safe_float(margin_pct, DEFAULT_MARGIN_PCT)
    vat_pct = _safe_float(vat_pct, DEFAULT_VAT_PCT)
    cost_subtotal = round(sum(_safe_float(ln.get('line_total')) for ln in lines), 2)
    margin_amount = round(cost_subtotal * margin_pct / 100, 2)
    subtotal = round(cost_subtotal + margin_amount, 2)
    vat_amount = round(subtotal * vat_pct / 100, 2)
    total = round(subtotal + vat_amount, 2)
    return {
        'cost_subtotal': cost_subtotal,
        'margin_pct': margin_pct,
        'margin_amount': margin_amount,
        'subtotal': subtotal,
        'vat_pct': vat_pct,
        'vat_amount': vat_amount,
        'total': total,
    }
