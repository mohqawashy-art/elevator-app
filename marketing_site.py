"""سياق صفحات التسويق العامة (تعريف المنتج + الأسعار)."""
from __future__ import annotations

from typing import Any

from plan_catalog import (
    ADDON_CATALOG,
    LIMIT_LABELS_AR,
    PLAN_CATALOG,
    PLAN_ORDER,
    public_addon_keys,
)

# نصوص تسويقية قصيرة — منفصلة عن حدود الباقة التقنية
PLAN_MARKETING: dict[str, dict[str, Any]] = {
    'liftcore': {
        'blurb': 'باقة واحدة شاملة — كل أقسام البرنامج لشركات الصيانة والتركيب.',
        'bullets': [
            '500 مصعد · 8 مستخدمين · 8 GB تخزين',
            'جميع أقسام البرنامج — صيانة، مخزون، مالية، وتركيب',
            'عملاء، عقود، زيارات، أعطال، وبوابة الفني',
            'فواتير ZATCA وتقارير تشغيل ومالية',
            'إضافات مرنة: 5 ر.س/مصعد · 40 ر.س/مستخدم · 45 ر.س/GB',
        ],
        'cta': 'ابدأ مع LiftCore',
        'featured': True,
        'badge': 'الباقة الشاملة',
        'cta_style': 'gold',
    },
}

ADDON_BLURBS_AR: dict[str, str] = {
    'elevator_unit': 'مصعد إضافي واحد على حد أسطولك',
    'office_user': 'مستخدم مكتبي إضافي للإدارة أو المحاسبة',
    'storage_gb_unit': 'جيجا إضافي للمرفقات والصور والمحاضر',
}

# حدود تُعرض في صفحة الأسعار العامة (بدون فنيين — مشمولون ضمن التشغيل)
PUBLIC_LIMIT_KEYS = ('elevators', 'office_users', 'storage_gb')

# ما يشمله شراء البرنامج كامل (رخصة ملكية — ليس إيجاراً)
BUY_INCLUDED: tuple[dict[str, str], ...] = (
    {'title': 'رخصة لشركتك', 'desc': 'استخدام داخلي دائم للنظام — تدفع مرة، والبرنامج عندك. ليس اشتراكاً شهرياً أو سنوياً.'},
    {'title': 'كل أقسام البرنامج', 'desc': 'عملاء، عقود، زيارات، أعطال، مخزون، مالية، تركيب، تقارير، وبوابة الفني.'},
    {'title': 'تثبيت على سيرفرك أو سيرفر مُدار', 'desc': 'نشر مخصص لشركتك مع نطاقك، وليس حساباً مؤجَّراً على متجر عام.'},
    {'title': 'تدريب وتسليم', 'desc': 'جلسة تشغيل، حساب مدير، ودليل مستخدم بعد الاستيراد أو البدء من صفر.'},
    {'title': 'دعم وضمان متفق عليه', 'desc': 'تصحيح أخطاء وتحديثات أمنية ضمن مدة الضمان في عقد الشراء.'},
    {'title': 'بياناتك ملكك', 'desc': 'تصدير واستعادة وفق العقد — لا يتوقف عملك لأن اشتراكاً انتهى.'},
)

# أقسام البرنامج المشمولة في الباقة الواحدة
INCLUDED_MODULES: tuple[dict[str, str], ...] = (
    {'title': 'العملاء والمصاعد', 'desc': 'سجل العملاء، الأسطول، الخريطة، والاستيراد'},
    {'title': 'العقود والصيانة', 'desc': 'عقود، زيارات، تقارير موقّعة، وجدولة'},
    {'title': 'الأعطال والطوارئ', 'desc': 'بلاغات، متابعة، وربط بالفني والزيارة'},
    {'title': 'بوابة الفني', 'desc': 'تطبيق ميداني للفريق والتقارير اليومية'},
    {'title': 'المخزون والمشتريات', 'desc': 'قطع الغيار، حركات المخزون، وأوامر الشراء'},
    {'title': 'المالية والفواتير', 'desc': 'فواتير، تحصيل، QR ضريبي، وتقارير'},
    {'title': 'وحدة التركيب', 'desc': 'فرص بيع، تقديرات، مشاريع، وتسليم'},
    {'title': 'التقارير والإدارة', 'desc': 'تشغيل، ربحية، Excel، وصلاحيات المستخدمين'},
)

COMPARE_ROWS: tuple[dict[str, Any], ...] = (
    {'key': 'price', 'label': 'السعر السنوي (ر.س)'},
    {'key': 'elevators', 'label': 'المصاعد'},
    {'key': 'office_users', 'label': 'مستخدم مكتبي'},
    {'key': 'technicians', 'label': 'فنيون'},
    {'key': 'storage_gb', 'label': 'التخزين (GB)'},
    {'key': 'maintenance_core', 'label': 'صيانة وعقود وأعطال'},
    {'key': 'inventory_pack', 'label': 'مخزون ومشتريات ومالية'},
    {'key': 'installation', 'label': 'وحدة التركيب'},
    {'key': 'priority_support', 'label': 'دعم أولوية'},
)


def _fmt_sar(amount: float) -> str:
    if amount is None:
        return '—'
    if float(amount).is_integer():
        return f'{int(amount):,}'
    return f'{amount:,.1f}'.rstrip('0').rstrip('.')


def build_pricing_plans() -> list[dict[str, Any]]:
    from plan_catalog import _safe_live_plans

    plans: list[dict[str, Any]] = []
    live = _safe_live_plans()
    for key in PLAN_ORDER:
        cat = live.get(key) or PLAN_CATALOG[key]
        mkt = PLAN_MARKETING.get(key) or {}
        limits = cat.get('limits') or {}
        plans.append({
            'key': key,
            'label': cat.get('label_ar') or cat.get('label') or key.title(),
            'label_ar': cat.get('label_ar') or key,
            'yearly_sar': cat.get('yearly_sar'),
            'monthly_sar': cat.get('monthly_sar'),
            'yearly_display': _fmt_sar(float(cat.get('yearly_sar') or 0)),
            'monthly_display': _fmt_sar(float(cat.get('monthly_sar') or 0)),
            'limits': limits,
            'limit_rows': [
                {
                    'key': lk,
                    'label': LIMIT_LABELS_AR.get(lk, lk),
                    'value': limits.get(lk),
                    'display': (
                        f"{limits.get(lk)} GB" if lk == 'storage_gb'
                        else str(limits.get(lk))
                    ),
                }
                for lk in PUBLIC_LIMIT_KEYS
            ],
            'features': cat.get('features') or {},
            'blurb': mkt.get('blurb') or '',
            'bullets': list(mkt.get('bullets') or []),
            'cta': mkt.get('cta') or 'اختر الباقة',
            'featured': bool(mkt.get('featured')),
            'badge': mkt.get('badge'),
            'cta_style': mkt.get('cta_style') or 'outline',
            'mailto_only': bool(mkt.get('mailto_only')),
        })
    return plans


def build_pricing_addons() -> list[dict[str, Any]]:
    from plan_catalog import _safe_live_addons

    rows: list[dict[str, Any]] = []
    live = _safe_live_addons()
    for key in public_addon_keys():
        ad = live.get(key) or ADDON_CATALOG[key]
        rows.append({
            'key': key,
            'label': ad.get('label') or key,
            'monthly_sar': ad.get('monthly_sar'),
            'yearly_sar': ad.get('yearly_sar'),
            'monthly_display': _fmt_sar(float(ad.get('monthly_sar') or 0)),
            'yearly_display': _fmt_sar(float(ad.get('yearly_sar') or 0)),
            'blurb': ADDON_BLURBS_AR.get(key, ''),
            'allow_qty': bool(ad.get('allow_qty')),
        })
    return rows


def build_compare_table(plans: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    plans = plans or build_pricing_plans()
    by_key = {p['key']: p for p in plans}
    rows: list[dict[str, Any]] = []
    for spec in COMPARE_ROWS:
        cells: list[str] = []
        for key in PLAN_ORDER:
            p = by_key[key]
            feats = p.get('features') or {}
            limits = p.get('limits') or {}
            k = spec['key']
            if k == 'price':
                cells.append(p.get('yearly_display') or '—')
            elif k in limits:
                val = limits.get(k)
                cells.append(f'{val} GB' if k == 'storage_gb' else str(val))
            elif k == 'inventory_pack':
                ok = all(feats.get(f) for f in ('inventory', 'purchasing', 'advanced_finance'))
                cells.append('✓' if ok else '—')
            elif k == 'installation':
                cells.append('✓' if feats.get('installation') else 'إضافة')
            elif k == 'priority_support':
                cells.append('✓' if feats.get('priority_support') else '—')
            else:
                cells.append('✓' if feats.get(k) else '—')
        rows.append({'label': spec['label'], 'cells': cells, 'is_check': spec['key'] not in (
            'price', 'elevators', 'office_users', 'technicians', 'storage_gb',
        )})
    return rows


# لقطات العرض التسويقي (/deck) — أهم الشاشات للجوال
DECK_SHOTS: tuple[dict[str, str], ...] = (
    {
        'id': 'dashboard',
        'file': 'images/marketing/screens/dashboard.png',
        'title': 'لوحة التحكم',
        'caption': 'رؤية تشغيلية في شاشة واحدة',
        'desc': 'عملاء، مصاعد، عقود، زيارات، أعطال، ومستحقات — مع إجراءات سريعة.',
    },
    {
        'id': 'map',
        'file': 'images/marketing/screens/elevators-map.png',
        'title': 'خريطة المصاعد',
        'caption': 'أسطولك على الخريطة',
        'desc': 'تتبع مواقع المصاعد وتصفية الحالة: نشط، صيانة، متوقف.',
    },
    {
        'id': 'visits',
        'file': 'images/marketing/screens/visits.png',
        'title': 'زيارات الصيانة',
        'caption': 'جدولة ميدانية واضحة',
        'desc': 'جدول زيارات مع الفني والحالة والتاريخ وتقارير الصيانة.',
    },
    {
        'id': 'customers',
        'file': 'images/marketing/screens/customers.png',
        'title': 'العملاء',
        'caption': 'سجل العملاء والعقود',
        'desc': 'بيانات العملاء، حالة العقد، عدد المصاعد، واستيراد Excel.',
    },
    {
        'id': 'contracts',
        'file': 'images/marketing/screens/contracts.png',
        'title': 'العقود',
        'caption': 'دورة حياة العقد كاملة',
        'desc': 'عقود نشطة ومنتهية، تنبيهات التجديد، والمستحقات.',
    },
    {
        'id': 'technicians',
        'file': 'images/marketing/screens/technicians-list.png',
        'title': 'الفريق الفني',
        'caption': 'إدارة الفنيين والتخصص',
        'desc': 'حالة كل فني، التخصص، الطوارئ، وتقارير الفريق.',
    },
    {
        'id': 'warehouse',
        'file': 'images/marketing/screens/warehouse.png',
        'title': 'إدارة المخازن',
        'caption': 'مخزون قطع المصاعد',
        'desc': 'أصناف الرفع والجر وتنبيهات النفاد مع تقارير الأصناف.',
    },
)


# لقطات حقيقية من النظام — للصفحة التعريفية
LANDING_SHOTS: tuple[dict[str, str], ...] = (
    {
        'id': 'dashboard',
        'file': 'images/marketing/screens/dashboard.png',
        'title': 'لوحة التحكم',
        'caption': 'رؤية تشغيلية في شاشة واحدة',
        'desc': 'عملاء، مصاعد، عقود، زيارات، أعطال مفتوحة، ومستحقات — مع إجراءات سريعة وتنبيهات.',
        'layout': 'feature',
    },
    {
        'id': 'map',
        'file': 'images/marketing/screens/elevators-map.png',
        'title': 'خريطة المصاعد',
        'caption': 'أسطولك على الخريطة',
        'desc': 'تتبع مواقع المصاعد وتصفية الحالة: نشط، تحت الصيانة، متوقف، أو خارج الخدمة.',
        'layout': 'feature',
    },
    {
        'id': 'visits',
        'file': 'images/marketing/screens/visits.png',
        'title': 'زيارات الصيانة',
        'caption': 'جدولة ميدانية واضحة',
        'desc': 'جدول زيارات مع الفني والحالة والتاريخ — وتخطيط الشهر وتقارير الصيانة.',
        'layout': 'half',
    },
    {
        'id': 'customers',
        'file': 'images/marketing/screens/customers.png',
        'title': 'العملاء',
        'caption': 'سجل العملاء والعقود',
        'desc': 'بيانات العملاء في مكة والمدن، حالة العقد، وعدد المصاعد، واستيراد وتصدير Excel.',
        'layout': 'half',
    },
    {
        'id': 'contracts',
        'file': 'images/marketing/screens/contracts.png',
        'title': 'العقود',
        'caption': 'دورة حياة العقد كاملة',
        'desc': 'عقود نشطة ومنتهية، تنبيهات التجديد، القيم والمستحقات، وطباعة وتقارير.',
        'layout': 'half',
    },
    {
        'id': 'technicians',
        'file': 'images/marketing/screens/technicians-list.png',
        'title': 'الفريق الفني',
        'caption': 'إدارة الفنيين والتخصص',
        'desc': 'حالة كل فني (متاح/مشغول)، التخصص، الطوارئ، وتقارير الفريق.',
        'layout': 'half',
    },
    {
        'id': 'parts',
        'file': 'images/marketing/screens/parts-billing.png',
        'title': 'تركيب قطع الغيار',
        'caption': 'فوترة القطع والربح',
        'desc': 'بيان تركيب القطع مع التكلفة وسعر العميل والتحصيل — مربوط بالزيارة والعقد.',
        'layout': 'half',
    },
    {
        'id': 'warehouse',
        'file': 'images/marketing/screens/warehouse.png',
        'title': 'إدارة المخازن',
        'caption': 'مخزون قطع المصاعد',
        'desc': 'أصناف الرفع والجر والتنبيهات عند النفاد، مع استيراد Excel وتقارير الأصناف.',
        'layout': 'half',
    },
    {
        'id': 'estimate',
        'file': 'images/marketing/screens/estimate-form.png',
        'title': 'تقدير التركيب',
        'caption': 'عرض سعر إنشاء مصعد',
        'desc': 'مواصفات المشروع وبنود التكلفة والربح والضريبة — ثم حفظ وطباعة التقدير.',
        'layout': 'half',
    },
    {
        'id': 'leads',
        'file': 'images/marketing/screens/install-leads.png',
        'title': 'فرص البيع',
        'caption': 'إدارة فرصة بيع حتى نهاية التركيب',
        'desc': 'من تسجيل الفرصة ومتابعة العميل المحتمل إلى التقدير والعرض ومشروع التركيب حتى التسليم.',
        'layout': 'half',
    },
)


def marketing_page_context(*, signup_open: bool, signup_href: str, signup_label: str) -> dict[str, Any]:
    import os
    from urllib.parse import quote

    sales_email = (os.environ.get('LIFTCORE_SALES_EMAIL') or 'sales@liftcoreapp.com').strip()
    if '@' not in sales_email:
        sales_email = 'sales@liftcoreapp.com'

    demo_subject = 'طلب عرض تجريبي — LiftCore'
    demo_body = (
        'السلام عليكم،\n\n'
        'أرغب في الحصول على حساب تجريبي لتجربة LiftCore.\n'
        'اسم الشركة:\n'
        'المدينة:\n'
        'عدد المصاعد تقريباً:\n'
        'رقم الجوال:\n'
    )
    sales_mailto = f'mailto:{sales_email}'
    sales_mailto_demo = (
        f'mailto:{sales_email}'
        f'?subject={quote(demo_subject)}'
        f'&body={quote(demo_body)}'
    )
    whatsapp_phone = '966566299626'
    support_whatsapp_url = f'https://wa.me/{whatsapp_phone}'
    sales_whatsapp_demo = f'{support_whatsapp_url}?text={quote(demo_body)}'

    plans = build_pricing_plans()
    return {
        'signup_open': signup_open,
        'signup_href': signup_href,
        'signup_label': signup_label,
        'signup_external': False,
        'plans': plans,
        'addons': build_pricing_addons(),
        'compare_rows': build_compare_table(plans),
        'included_modules': INCLUDED_MODULES,
        'plan_labels': [p['label'] for p in plans],
        'sales_email': sales_email,
        'sales_mailto': sales_mailto,
        'sales_mailto_demo': sales_mailto_demo,
        'sales_whatsapp_demo': sales_whatsapp_demo,
        'support_email': sales_email,
        'support_whatsapp_url': support_whatsapp_url,
        'support_whatsapp_display': '0566299626',
        'landing_shots': LANDING_SHOTS,
        'buy_included': BUY_INCLUDED,
    }


def marketing_seo_context(*, page: str = 'landing') -> dict[str, Any]:
    """عناوين ووصف وبيانات منظمة لصفحات التسويق (SEO)."""
    base = 'https://liftcoreapp.com'
    og_image = f'{base}/static/images/liftcore-marketing-header-logo.png'
    org = {
        '@type': 'Organization',
        'name': 'LiftCore',
        'legalName': 'مؤسسة نسق كور للحلول المتكاملة',
        'url': base,
        'logo': og_image,
        'email': 'sales@liftcoreapp.com',
        'telephone': '+966566299626',
        'address': {
            '@type': 'PostalAddress',
            'addressLocality': 'مكة المكرمة',
            'addressCountry': 'SA',
        },
        'areaServed': 'SA',
    }
    from plan_catalog import DEFAULT_PLAN_KEY, PLAN_CATALOG, _safe_live_plans

    live = _safe_live_plans()
    plan = live.get(DEFAULT_PLAN_KEY) or PLAN_CATALOG[DEFAULT_PLAN_KEY]
    yearly_price = int(float(plan.get('yearly_sar') or 2399))
    software = {
        '@type': 'SoftwareApplication',
        'name': 'LiftCore',
        'applicationCategory': 'BusinessApplication',
        'operatingSystem': 'Web',
        'offers': {
            '@type': 'Offer',
            'priceCurrency': 'SAR',
            'price': str(yearly_price),
            'url': f'{base}/pricing',
        },
        'description': (
            'برنامج إدارة المصاعد ونظام تشغيل لشركات صيانة وتركيب المصاعد في السعودية: '
            'إدارة مصاعد، عملاء، عقود، زيارات، أعطال، مخزون، فواتير، وبوابة فني.'
        ),
        'inLanguage': 'ar',
        'provider': {'@type': 'Organization', 'name': 'LiftCore'},
    }

    if page == 'buy':
        buy_url = f'{base}/buy'
        return {
            'page_title': 'شراء LiftCore كامل — رخصة ملكية وليست إيجاراً',
            'page_description': (
                'اشترِ برنامج LiftCore كاملاً لشركتك: كل الأقسام، تثبيت مخصص، تدريب، '
                'ورخصة استخدام داخلي — بيع مرة واحدة وليس اشتراك إيجار سنوي.'
            ),
            'canonical_url': buy_url,
            'og_image_url': og_image,
            'json_ld': {
                '@context': 'https://schema.org',
                '@graph': [org, {
                    '@type': 'SoftwareApplication',
                    'name': 'LiftCore',
                    'applicationCategory': 'BusinessApplication',
                    'operatingSystem': 'Web',
                    'offers': {
                        '@type': 'Offer',
                        'priceCurrency': 'SAR',
                        'availability': 'https://schema.org/InStock',
                        'url': buy_url,
                        'description': 'رخصة شراء البرنامج كامل — عرض سعر مخصص',
                    },
                    'description': (
                        'برنامج إدارة المصاعد لشركات الصيانة في السعودية — يُباع رخصة كاملة لشركتك.'
                    ),
                    'inLanguage': 'ar',
                    'provider': {'@type': 'Organization', 'name': 'LiftCore'},
                }, {
                    '@type': 'WebPage',
                    'name': 'شراء برنامج LiftCore كامل',
                    'url': buy_url,
                    'isPartOf': {'@type': 'WebSite', 'url': base, 'name': 'LiftCore'},
                }],
            },
        }

    if page == 'pricing':
        return {
            'page_title': 'أسعار LiftCore — باقة واحدة شاملة لصيانة المصاعد',
            'page_description': (
                f'باقة LiftCore الواحدة لشركات صيانة المصاعد في السعودية — '
                f'{yearly_price:,} ر.س سنوياً · 500 مصعد · 8 مستخدمين · 8 GB · '
                'جميع أقسام البرنامج مشمولة.'
            ),
            'canonical_url': f'{base}/pricing',
            'og_image_url': og_image,
            'json_ld': {
                '@context': 'https://schema.org',
                '@graph': [org, software, {
                    '@type': 'WebPage',
                    'name': 'باقات وأسعار LiftCore',
                    'url': f'{base}/pricing',
                    'isPartOf': {'@type': 'WebSite', 'url': base, 'name': 'LiftCore'},
                }],
            },
        }

    if page == 'seo_elevator':
        page_url = f'{base}/برنامج-ادارة-المصاعد'
        return {
            'page_title': 'برنامج إدارة المصاعد — LiftCore لصيانة المصاعد في السعودية',
            'page_description': (
                'برنامج إدارة المصاعد وبرنامج صيانة المصاعد للشركات في السعودية: '
                'إدارة مصاعد وعملاء وعقود وزيارات وأعطال وفواتير في منصة عربية واحدة.'
            ),
            'canonical_url': page_url,
            'og_image_url': og_image,
            'json_ld': {
                '@context': 'https://schema.org',
                '@graph': [
                    org,
                    software,
                    {
                        '@type': 'WebPage',
                        'name': 'برنامج إدارة المصاعد',
                        'url': page_url,
                        'description': (
                            'دليل وبرنامج إدارة مصاعد لشركات الصيانة في السعودية — LiftCore.'
                        ),
                        'inLanguage': 'ar',
                        'isPartOf': {'@type': 'WebSite', 'url': base, 'name': 'LiftCore'},
                    },
                    {
                        '@type': 'FAQPage',
                        'mainEntity': [
                            {
                                '@type': 'Question',
                                'name': 'هل LiftCore برنامج إدارة مصاعد أم برنامج محاسبة فقط؟',
                                'acceptedAnswer': {
                                    '@type': 'Answer',
                                    'text': (
                                        'هو نظام تشغيل لصيانة المصاعد: عملاء، عقود، زيارات، أعطال، '
                                        'مخزون، مع فواتير مرتبطة بالعمل — وليس برنامج محاسبة عام.'
                                    ),
                                },
                            },
                            {
                                '@type': 'Question',
                                'name': 'هل يناسب الشركات في مكة والسعودية؟',
                                'acceptedAnswer': {
                                    '@type': 'Answer',
                                    'text': (
                                        'نعم. الواجهة عربية، والتركيز على شركات الصيانة المحلية، '
                                        'ودعم من مكة المكرمة.'
                                    ),
                                },
                            },
                            {
                                '@type': 'Question',
                                'name': 'كيف أجرب برنامج المصاعد؟',
                                'acceptedAnswer': {
                                    '@type': 'Answer',
                                    'text': (
                                        'اطلب تجربة من صفحة البدء، وسنرد على بريدك خلال يوم عمل '
                                        'لتهيئة حساب تجريبي.'
                                    ),
                                },
                            },
                        ],
                    },
                ],
            },
        }

    if page == 'ads':
        return {
            'page_title': 'جرّب LiftCore — برنامج صيانة المصاعد لشركتك',
            'page_description': (
                'اطلب تجربة LiftCore لشركات صيانة المصاعد في السعودية: '
                'عملاء، عقود، زيارات، أعطال، مخزون، وفواتير — نرد عليك خلال يوم عمل.'
            ),
            'canonical_url': f'{base}/start',
            'og_image_url': og_image,
            'robots': 'noindex, follow',
            'json_ld': {
                '@context': 'https://schema.org',
                '@graph': [org, software, {
                    '@type': 'WebPage',
                    'name': 'طلب تجربة LiftCore',
                    'url': f'{base}/start',
                }],
            },
        }

    if page == 'ads_thanks':
        return {
            'page_title': 'تم استلام طلبك — LiftCore',
            'page_description': 'شكراً لطلبك. فريق مبيعات LiftCore سيتواصل معك قريباً.',
            'canonical_url': f'{base}/start/thanks',
            'og_image_url': og_image,
            'robots': 'noindex, nofollow',
            'json_ld': None,
        }

    return {
        'page_title': 'برنامج إدارة المصاعد | LiftCore لصيانة المصاعد في السعودية',
        'page_description': (
            'برنامج إدارة المصاعد وبرنامج صيانة المصاعد للشركات في مكة والسعودية: '
            'إدارة مصاعد، عقود، زيارات، أعطال، مخزون، فواتير، وبوابة فني.'
        ),
        'canonical_url': f'{base}/',
        'og_image_url': og_image,
        'json_ld': {
            '@context': 'https://schema.org',
            '@graph': [
                org,
                software,
                {
                    '@type': 'WebSite',
                    'name': 'LiftCore',
                    'url': base,
                    'inLanguage': 'ar',
                    'publisher': {'@type': 'Organization', 'name': 'LiftCore'},
                },
            ],
        },
    }
