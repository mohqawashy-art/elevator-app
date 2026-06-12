"""كتالوج تسعير التركيب — مناشئ الماكينة والماركات (قابل للنقل لقاعدة بيانات لاحقاً)."""

MACHINE_ORIGINS = [
    {'id': 'chinese', 'label': 'صيني', 'factor': 1.00},
    {'id': 'turkish', 'label': 'تركي', 'factor': 1.15},
    {'id': 'korean', 'label': 'كوري', 'factor': 1.20},
    {'id': 'indian', 'label': 'هندي', 'factor': 0.95},
    {'id': 'european', 'label': 'أوروبي', 'factor': 1.25},
    {'id': 'italian', 'label': 'إيطالي', 'factor': 1.35},
    {'id': 'german', 'label': 'ألماني', 'factor': 1.30},
    {'id': 'japanese', 'label': 'ياباني', 'factor': 1.30},
]

CUSTOM_ORIGIN_OPTION = '__custom__'

MACHINE_BRANDS = {
    'chinese': ['Monarch', 'Hosting', 'Generic OEM'],
    'turkish': ['Eker', 'Asansör'],
    'korean': ['Hyundai', 'Dong Yang'],
    'indian': ['Johnson', 'Kone India OEM'],
    'european': ['Schindler OEM', 'Kone OEM'],
    'italian': ['Sicor', 'IMEM'],
    'german': ['Thyssen OEM', 'Hütter-Aufzüge'],
    'japanese': ['Mitsubishi', 'Fujitec OEM'],
}

CONTROL_PANEL_BRANDS = {
    'chinese': ['Monarch', 'STEP', 'Nice', 'Generic OEM'],
    'turkish': ['Arkel', 'Eker', 'Mikrolift'],
    'korean': ['Hyundai', 'Mitsubishi OEM'],
    'indian': ['STEP India', 'Generic OEM'],
    'european': ['Fermator OEM', 'Kone OEM', 'Schindler OEM'],
    'italian': ['Sicor', 'IMEM'],
    'german': ['Thyssen OEM', 'Generic OEM'],
    'japanese': ['Mitsubishi', 'Fujitec OEM'],
}

CUSTOM_BRAND_OPTION = '__custom__'

DEFAULT_MACHINE_ORIGIN = 'chinese'
DEFAULT_PANEL_ORIGIN = 'chinese'


def origin_factor(origin_id):
    for o in MACHINE_ORIGINS:
        if o['id'] == origin_id:
            return o['factor']
    return 1.0


def origin_label(origin_id):
    if not origin_id or origin_id == CUSTOM_ORIGIN_OPTION:
        return '—'
    for o in MACHINE_ORIGINS:
        if o['id'] == origin_id:
            return o['label']
    return origin_id or '—'


def origin_label_from_spec(spec, origin_key='machine_origin', country_key='machine_origin_country'):
    if not spec:
        return '—'
    origin_id = spec.get(origin_key, '')
    if origin_id == CUSTOM_ORIGIN_OPTION:
        return (spec.get(country_key) or '').strip() or '—'
    return origin_label(origin_id)


def origins_for_js():
    return [{'id': o['id'], 'label': o['label'], 'factor': o['factor']} for o in MACHINE_ORIGINS]
