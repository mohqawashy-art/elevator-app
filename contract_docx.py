"""تعبئة نموذج عقد Word دون المساس بالتنسيق أو اتجاه العربية."""
from __future__ import annotations

import io
import os
import re

from models import Settings

PLACEHOLDER_HELP = [
    ('{{رقم_العقد}}', 'رقم العقد'),
    ('{{اسم_العميل}}', 'اسم العميل'),
    ('{{رقم_الهوية}}', 'رقم الهوية / الإقامة'),
    ('{{السجل_التجاري}}', 'السجل التجاري للعميل'),
    ('{{الرقم_الضريبي}}', 'الرقم الضريبي للعميل'),
    ('{{العنوان}}', 'عنوان موقع العقد'),
    ('{{المدينة}}', 'المدينة'),
    ('{{الحي}}', 'الحي'),
    ('{{هاتف_العميل}}', 'هاتف العميل'),
    ('{{قيمة_العقد}}', 'قيمة العقد رقماً'),
    ('{{قيمة_العقد_كتابة}}', 'قيمة العقد كتابةً'),
    ('{{مدة_العقد}}', 'مدة العقد بالأشهر'),
    ('{{تاريخ_البداية}}', 'بداية العقد'),
    ('{{تاريخ_النهاية}}', 'نهاية العقد'),
    ('{{نوع_العقد}}', 'نوع العقد'),
    ('{{دورية_الصيانة}}', 'دورية الصيانة'),
    ('{{طريقة_الدفع}}', 'طريقة الدفع'),
    ('{{عدد_المصاعد}}', 'عدد المصاعد'),
    ('{{اليوم}}', 'يوم التوقيع'),
    ('{{التاريخ_الهجري}}', 'التاريخ الهجري'),
    ('{{التاريخ_الميلادي}}', 'التاريخ الميلادي'),
    ('{{اسم_الشركة}}', 'اسم الشركة (الطرف الأول)'),
    ('{{مقر_الشركة}}', 'مقر الشركة'),
    ('{{هاتف_الشركة}}', 'هاتف الشركة'),
    ('{{بريد_الشركة}}', 'بريد الشركة'),
    ('{{ممثل_الشركة}}', 'ممثل الشركة'),
    ('{{جوال_الممثل}}', 'جوال ممثل الشركة'),
]


def template_abs_path(settings: Settings | None, app_root: str) -> str | None:
    rel = (getattr(settings, 'contract_template_path', None) or '').replace('\\', '/').strip()
    if not rel:
        return None
    rel = rel.lstrip('/')
    candidates = [
        os.path.join(app_root, 'static', rel),
        os.path.join(app_root, rel),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def has_contract_template(settings: Settings | None, app_root: str) -> bool:
    return bool(template_abs_path(settings, app_root))


def _xml_safe(value) -> str:
    if value is None:
        return ''
    return str(value)


def _duration_phrase(contract) -> str:
    months = getattr(contract, 'duration_months', None)
    start = getattr(contract, 'start_date', None)
    end = getattr(contract, 'end_date', None)
    if not months and start and end:
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if end.day >= start.day:
            months += 0
        if months < 0:
            months = 0
    if not months:
        return ''
    if months == 1:
        return 'شهر واحد'
    if months == 2:
        return 'شهرين'
    if 3 <= months <= 10:
        return f'{months} أشهر'
    return f'{months} شهراً'


def placeholder_map(contract) -> dict[str, str]:
    from contract_print import (
        amount_in_words,
        company_info,
        contract_print_payload,
        format_contract_code,
    )

    payload = contract_print_payload(contract.id)
    customer = payload['customer']
    company = payload['company'] or company_info()
    amount = payload['amount']
    amount_fmt = f'{amount:,}'.replace(',', '٬') if amount else '0'

    values = {
        'رقم_العقد': payload['contract_code'] or format_contract_code(contract.code),
        'اسم_العميل': (customer.name if customer else '') or '',
        'رقم_الهوية': (getattr(customer, 'national_id', None) or '') if customer else '',
        'السجل_التجاري': (getattr(customer, 'cr_number', None) or '') if customer else '',
        'الرقم_الضريبي': (getattr(customer, 'vat_number', None) or '') if customer else '',
        'العنوان': payload.get('customer_address') or '',
        'المدينة': (contract.city or (customer.city if customer else '') or '') or '',
        'الحي': (contract.district or (customer.district if customer else '') or '') or '',
        'هاتف_العميل': (customer.phone if customer else '') or '',
        'قيمة_العقد': amount_fmt,
        'قيمة_العقد_كتابة': (payload.get('amount_words') or amount_in_words(amount)) + ' ريال سعودي',
        'مدة_العقد': _duration_phrase(contract),
        'تاريخ_البداية': payload.get('start_gregorian') or '',
        'تاريخ_النهاية': payload.get('end_gregorian') or '',
        'نوع_العقد': contract.contract_type or '',
        'دورية_الصيانة': payload.get('maint_phrase') or '',
        'طريقة_الدفع': payload.get('pay_phrase') or '',
        'عدد_المصاعد': str(payload.get('elevator_count') or ''),
        'اليوم': payload.get('sign_day') or '',
        'التاريخ_الهجري': payload.get('sign_hijri') or '',
        'التاريخ_الميلادي': payload.get('sign_gregorian') or '',
        'اسم_الشركة': company.get('company_name') or '',
        'مقر_الشركة': company.get('city_full') or '',
        'هاتف_الشركة': company.get('phone') or '',
        'بريد_الشركة': company.get('email') or '',
        'ممثل_الشركة': company.get('rep_name') or '',
        'جوال_الممثل': company.get('rep_mobile') or '',
    }

    mapping: dict[str, str] = {}
    for key, val in values.items():
        text = _xml_safe(val)
        mapping[f'{{{{{key}}}}}'] = text
        mapping[f'{{{{{key.replace("_", " ")}}}}}'] = text
    return mapping


def _replace_in_element(element, mapping: dict[str, str]) -> None:
    from docx.oxml.ns import qn

    keys = tuple(mapping.keys())
    for p in element.iter(qn('w:p')):
        nodes = list(p.iter(qn('w:t')))
        if not nodes:
            continue
        full = ''.join(n.text or '' for n in nodes)
        if not any(k in full for k in keys):
            continue
        new = full
        for key, val in mapping.items():
            if key in new:
                new = new.replace(key, val)
        nodes[0].text = new
        for n in nodes[1:]:
            n.text = ''


def _iter_docx_parts(doc):
    seen = set()
    parts = [doc.part]
    for rel in doc.part.rels.values():
        if getattr(rel, 'is_external', False):
            continue
        reltype = (getattr(rel, 'reltype', '') or '').lower()
        if any(token in reltype for token in ('header', 'footer', 'footnotes', 'endnotes')):
            try:
                parts.append(rel.target_part)
            except Exception:
                continue
    for part in parts:
        ident = id(part)
        if ident in seen:
            continue
        seen.add(ident)
        yield part


def fill_contract_docx(contract, template_path: str) -> bytes:
    from docx import Document

    mapping = placeholder_map(contract)
    doc = Document(template_path)
    for part in _iter_docx_parts(doc):
        _replace_in_element(part.element, mapping)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def filled_filename(contract) -> str:
    from contract_print import format_contract_code

    code = re.sub(r'[^\w\-]+', '_', format_contract_code(contract.code) or 'contract')
    return f'عقد-{code}.docx'


def try_send_filled_contract(contract_id: int):
    """يرجع استجابة Flask لتنزيل الورد، أو None إن لم يوجد نموذج."""
    from flask import current_app, send_file

    from models import Contract
    from tenant_scope import tenant_get_or_404, tenant_query

    contract = tenant_get_or_404(Contract, contract_id)
    settings = tenant_query(Settings).first()
    path = template_abs_path(settings, current_app.root_path)
    if not path:
        return None
    data = fill_contract_docx(contract, path)
    buf = io.BytesIO(data)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=filled_filename(contract),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
