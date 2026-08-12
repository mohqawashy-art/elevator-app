"""سياق صفحات التسويق العامة (تعريف المنتج + الأسعار)."""
from __future__ import annotations

from typing import Any

from plan_catalog import (
    ADDON_CATALOG,
    LIMIT_LABELS_AR,
    PLAN_CATALOG,
    PLAN_ORDER,
    known_addon_keys,
)

# نصوص تسويقية قصيرة — منفصلة عن حدود الباقة التقنية
PLAN_MARKETING: dict[str, dict[str, Any]] = {
    'basic': {
        'blurb': 'للشركات الناشئة وبداية تنظيم الصيانة اليومية.',
        'bullets': [
            'عملاء ومصاعد وعقود صيانة',
            'جدولة زيارات وتقارير موقّعة',
            'أعطال + بوابة الفني',
            'فواتير مع QR ضريبي (مرحلة 1)',
            'تقارير تشغيل أساسية',
        ],
        'cta': 'اختر Basic',
        'featured': False,
        'badge': None,
        'cta_style': 'outline',
    },
    'plus': {
        'blurb': 'نفس حدود Basic مع مخزون ومشتريات ومالية أوضح.',
        'bullets': [
            'كل مزايا Basic',
            'مخزون قطع وحركات المخزون',
            'أوامر شراء ومالية أوضح',
            'تقارير تشغيل ومالية أوسع',
            'استيراد Excel',
        ],
        'cta': 'ابدأ مع Plus',
        'featured': True,
        'badge': 'الأنسب',
        'cta_style': 'gold',
    },
    'pro': {
        'blurb': 'نفس مزايا Plus بسعة أكبر للأسطول والفريق.',
        'bullets': [
            'كل مزايا Plus',
            'سعة أعلى للمصاعد والفنيين',
            'تخزين أكبر للملفات والمحاضر',
            'مناسب للشركات الشغّالة',
            'مسار ترقية طبيعي من Plus',
        ],
        'cta': 'اختر Pro',
        'featured': False,
        'badge': None,
        'cta_style': 'outline',
    },
    'enterprise': {
        'blurb': 'للشركات الكبيرة ومتطلبات الدعم والتخصيص.',
        'bullets': [
            'كل مزايا Pro',
            'وحدة التركيب مشمولة',
            'دعم أولوية',
            'حدود أعلى وتخزين أكبر',
            'تخصيص وعقد سنوي مرن',
        ],
        'cta': 'تواصل للمؤسسات',
        'featured': False,
        'badge': None,
        'cta_style': 'outline',
        'mailto_only': True,
    },
}

ADDON_BLURBS_AR: dict[str, str] = {
    'office_user': 'حساب إضافي للإدارة أو المحاسبة',
    'technician': 'وصول كامل لبوابة الفني والتقارير',
    'elevators_10': 'باقة نمو مرنة لحجم الأسطول',
    'storage_10gb': 'للمرفقات والصور والمحاضر',
    'installation': 'عروض ومشاريع وتسليم تركيب',
    'zatca_phase2': 'عند التفعيل الكامل للمرحلة الثانية',
    'priority_support': 'أولوية استجابة — مجاني في Enterprise',
    'inventory_pack': 'مخزون ومشتريات ومالية لباقة Basic',
}

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
    plans: list[dict[str, Any]] = []
    for key in PLAN_ORDER:
        cat = PLAN_CATALOG[key]
        mkt = PLAN_MARKETING.get(key) or {}
        limits = cat.get('limits') or {}
        plans.append({
            'key': key,
            'label': cat.get('label') or key.title(),
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
                for lk in ('elevators', 'office_users', 'technicians', 'storage_gb')
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
    rows: list[dict[str, Any]] = []
    for key in known_addon_keys():
        ad = ADDON_CATALOG[key]
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
                if feats.get('priority_support'):
                    cells.append('✓')
                else:
                    cells.append('إضافة' if key in ('plus', 'pro', 'enterprise') else '—')
            else:
                cells.append('✓' if feats.get(k) else '—')
        rows.append({'label': spec['label'], 'cells': cells, 'is_check': spec['key'] not in (
            'price', 'elevators', 'office_users', 'technicians', 'storage_gb',
        )})
    return rows


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
        'plan_labels': [p['label'] for p in plans],
        'sales_email': sales_email,
        'sales_mailto': sales_mailto,
        'sales_mailto_demo': sales_mailto_demo,
        'sales_whatsapp_demo': sales_whatsapp_demo,
        'support_email': sales_email,
        'support_whatsapp_url': support_whatsapp_url,
        'support_whatsapp_display': '0566299626',
        'landing_shots': LANDING_SHOTS,
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
    software = {
        '@type': 'SoftwareApplication',
        'name': 'LiftCore',
        'applicationCategory': 'BusinessApplication',
        'operatingSystem': 'Web',
        'offers': {
            '@type': 'Offer',
            'priceCurrency': 'SAR',
            'price': '3000',
            'url': f'{base}/pricing',
        },
        'description': (
            'نظام تشغيل لشركات صيانة وتركيب المصاعد في السعودية: '
            'عملاء، عقود، زيارات، أعطال، مخزون، فواتير، وبوابة فني.'
        ),
        'inLanguage': 'ar',
        'provider': {'@type': 'Organization', 'name': 'LiftCore'},
    }

    if page == 'pricing':
        return {
            'page_title': 'أسعار LiftCore — باقات صيانة المصاعد في السعودية',
            'page_description': (
                'باقات LiftCore لشركات صيانة المصاعد في السعودية — '
                'اشتراك سنوي من 3,000 ر.س، حدود مصاعد وفنيين واضحة، وإضافات للنمو.'
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
        'page_title': 'LiftCore — برنامج إدارة صيانة المصاعد في السعودية',
        'page_description': (
            'LiftCore نظام تشغيل لشركات صيانة وتركيب المصاعد في مكة والسعودية: '
            'عملاء، عقود، زيارات ميدانية، أعطال، مخزون، فواتير، وبوابة فني.'
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
