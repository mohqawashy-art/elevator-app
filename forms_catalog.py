"""فهرس نماذج المكتب — طباعة فارغة، فتح الشاشة، قوالب Excel."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable

from checklist_templates import DEFAULT_TEMPLATE_KEY


def _allowed(has_perm: Callable[[str], bool], perms: tuple[str, ...]) -> bool:
    if not perms:
        return True
    return any(has_perm(p) for p in perms)


def _catalog_raw(*, install_enabled: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            'id': 'maintenance-checklist',
            'category': 'عمليات وصيانة',
            'title': 'محضر صيانة مصعد',
            'description': 'قائمة الفحص القياسية — زيارة صيانة دورية',
            'perms': ('maintenance_visits.read',),
            'blank_endpoint': 'office_form_blank',
            'blank_kwargs': {'form_id': 'maintenance-checklist'},
            'open_href': '/maintenance-visits',
            'open_label': 'زيارات الصيانة',
        },
        {
            'id': 'fault-report',
            'category': 'عمليات وصيانة',
            'title': 'تقرير معالجة عطل',
            'description': 'يُعبّأ من سجل العطل أو بوابة الفني — الطباعة من العطل بعد الحفظ',
            'perms': ('faults.read',),
            'open_href': '/faults',
            'open_label': 'الأعطال',
        },
        {
            'id': 'external-inspection',
            'category': 'عمليات وصيانة',
            'title': 'فحص مصعد خارجي',
            'description': 'زيارة موقع بدون عقد — تعبئة إلكترونية من الفني',
            'perms': ('maintenance_visits.read', 'technicians.read'),
            'blank_endpoint': 'office_form_blank',
            'blank_kwargs': {'form_id': 'external-inspection'},
            'open_href': '/field/external-inspections',
            'open_label': 'بوابة الفني',
            'field_note': True,
        },
        {
            'id': 'parts-billing',
            'category': 'عمليات وصيانة',
            'title': 'تركيب قطع غيار (فوترة)',
            'description': 'نموذج تركيب قطع وربطها بالعميل',
            'perms': ('parts_billing.read',),
            'open_href': '/parts-billing',
            'open_label': 'تركيب قطع غيار',
        },
        {
            'id': 'maintenance-quote',
            'category': 'مبيعات وعروض',
            'title': 'عرض سعر صيانة',
            'description': 'طباعة PDF من العرض بعد إنشائه',
            'perms': ('sales_quotes.read',),
            'open_href': '/sales/maintenance-quotes',
            'open_label': 'عروض الصيانة',
        },
        {
            'id': 'install-quote',
            'category': 'مبيعات وعروض',
            'title': 'عرض سعر تركيب',
            'description': 'طباعة من عرض التركيب بعد الحفظ',
            'perms': ('installation_projects.read',),
            'open_href': '/sales/quotes?kind=install',
            'open_label': 'عروض التركيب',
            'requires_install': True,
        },
        {
            'id': 'elevator-estimate',
            'category': 'مبيعات وعروض',
            'title': 'تقدير تكلفة إنشاء مصعد',
            'description': 'طباعة التقدير من السجل',
            'perms': ('elevator_estimates.read',),
            'open_href': '/elevator-estimates',
            'open_label': 'تقديرات المصاعد',
        },
        {
            'id': 'contract-print',
            'category': 'عقود ومستندات',
            'title': 'عقد صيانة / تركيب',
            'description': 'طباعة العقد من صفحة العقود',
            'perms': ('contracts.read',),
            'open_href': '/contracts?scope=maintenance',
            'open_label': 'العقود',
        },
        {
            'id': 'invoice-print',
            'category': 'مالية',
            'title': 'فاتورة / سند قبض / سند صرف',
            'description': 'طباعة من قائمة الفواتير والسندات',
            'perms': ('invoices.read',),
            'open_href': '/invoices',
            'open_label': 'الفواتير والسندات',
        },
        {
            'id': 'purchase-order',
            'category': 'مخازن ومشتريات',
            'title': 'أمر شراء',
            'description': 'طباعة PO من أمر الشراء',
            'perms': ('purchase_orders.read',),
            'open_href': '/purchase-orders',
            'open_label': 'أوامر الشراء',
        },
        {
            'id': 'supplier-rfq',
            'category': 'مخازن ومشتريات',
            'title': 'طلب عرض سعر (مورد)',
            'description': 'طباعة RFQ من الطلب',
            'perms': ('supplier_rfqs.read',),
            'open_href': '/supplier-rfqs',
            'open_label': 'طلبات عروض الأسعار',
        },
        {
            'id': 'warehouse-issue',
            'category': 'مخازن ومشتريات',
            'title': 'محضر صرف مخزن',
            'description': 'طباعة من حركة الصرف',
            'perms': ('stock_movements.read', 'inventory.read'),
            'open_href': '/warehouse/issue',
            'open_label': 'صرف المخزن',
        },
        {
            'id': 'inventory-custody',
            'category': 'مخازن ومشتريات',
            'title': 'عهدة مخزنية / تحويل عهدة',
            'description': 'طباعة من سجل العهدة',
            'perms': ('inventory.read',),
            'open_href': '/inventory',
            'open_label': 'المخزون (عهدة)',
        },
        {
            'id': 'import-clients',
            'category': 'استيراد Excel',
            'title': 'قالب استيراد العملاء',
            'description': 'ملف Excel فارغ للاستيراد',
            'perms': ('clients.read',),
            'download_href': '/clients/template',
            'download_label': 'تحميل Excel',
        },
        {
            'id': 'import-elevators',
            'category': 'استيراد Excel',
            'title': 'قالب استيراد المصاعد',
            'description': 'ملف Excel فارغ للاستيراد',
            'perms': ('elevators.read',),
            'download_href': '/elevators/template',
            'download_label': 'تحميل Excel',
        },
        {
            'id': 'import-contracts',
            'category': 'استيراد Excel',
            'title': 'قالب استيراد العقود',
            'description': 'ملف Excel فارغ للاستيراد',
            'perms': ('contracts.read',),
            'download_href': '/contracts/template',
            'download_label': 'تحميل Excel',
        },
        {
            'id': 'import-inventory',
            'category': 'استيراد Excel',
            'title': 'قالب استيراد الأصناف',
            'description': 'ملف Excel فارغ للمخزن',
            'perms': ('inventory.read',),
            'download_href': '/inventory/template',
            'download_label': 'تحميل Excel',
        },
        {
            'id': 'import-parts-billing',
            'category': 'استيراد Excel',
            'title': 'قالب تركيب قطع الغيار',
            'description': 'استيراد دفعات التركيب',
            'perms': ('parts_billing.read',),
            'download_href': '/parts-billing/template',
            'download_label': 'تحميل Excel',
        },
        {
            'id': 'field-portal',
            'category': 'بوابة الفني',
            'title': 'مهام الفني (جوال)',
            'description': 'زيارات، أعطال، فحوص خارجية — تعبئة من /field',
            'perms': ('technicians.read', 'maintenance_visits.read', 'faults.read'),
            'open_href': '/field',
            'open_label': 'فتح بوابة الفني',
            'field_note': True,
        },
    ]
    if not install_enabled:
        rows = [r for r in rows if not r.get('requires_install')]
    return rows


def catalog_for_user(
    *,
    has_perm: Callable[[str], bool],
    url_for: Callable[..., str],
    install_enabled: bool = True,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in _catalog_raw(install_enabled=install_enabled):
        if not _allowed(has_perm, tuple(raw.get('perms') or ())):
            continue
        item = dict(raw)
        be = item.pop('blank_endpoint', None)
        bk = item.pop('blank_kwargs', None) or {}
        if be:
            try:
                item['blank_url'] = url_for(be, **bk)
            except Exception:
                item['blank_url'] = None
        else:
            item['blank_url'] = None
        out.append(item)
    return out


def catalog_grouped(items: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for it in items:
        cat = it.get('category') or 'أخرى'
        groups.setdefault(cat, []).append(it)
    return list(groups.items())


def blank_form_payload(
    form_id: str,
    *,
    back_url: str,
) -> dict[str, Any]:
    """بيانات طباعة نموذج فارغ."""
    from checklist_templates import get_template
    from models import Settings
    from operations import _report_brand_logo_url
    from tenant_scope import tenant_query

    settings = tenant_query(Settings).first()
    company = (getattr(settings, 'company_name', None) or 'LiftCore') if settings else 'LiftCore'
    logo_url = _report_brand_logo_url()

    if form_id == 'maintenance-checklist':
        tpl = get_template(DEFAULT_TEMPLATE_KEY)
        return {
            'form_kind': 'maintenance',
            'title_ar': 'محضر صيانة مصعد',
            'title_en': 'Elevator maintenance report',
            'company_name': company,
            'logo_url': logo_url,
            'checklist_template': tpl,
            'back_url': back_url,
            'doc_code_label': 'رقم الزيارة',
        }
    if form_id == 'external-inspection':
        from field_external_inspection import DEFAULT_TEMPLATE_KEY as ext_key

        tpl = get_template(ext_key)
        return {
            'form_kind': 'external',
            'title_ar': 'فحص مصعد خارجي',
            'title_en': 'External elevator site inspection',
            'company_name': company,
            'logo_url': logo_url,
            'checklist_template': tpl,
            'back_url': back_url,
            'doc_code_label': 'رقم الفحص',
        }
    raise ValueError('نموذج غير معروف')
