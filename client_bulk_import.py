"""استيراد عملاء بالجملة — مطابقة أعمدة النموذج وتصدير جما."""
from __future__ import annotations

import re
from typing import Any

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    'name': (
        'الاسم (عربي)',
        'الاسم',
        'اسم العميل',
        'name',
        'Name',
    ),
    'phone': (
        'رقم الهاتف',
        'الهاتف',
        'الجوال',
        'رقم الجوال',
        'phone',
        'Phone',
        'mobile',
        'Mobile',
    ),
    'city': ('المدينة', 'city', 'City'),
    'district': ('الحي', 'الحي أو المنطقة', 'district', 'District'),
    'address': ('العنوان', 'العنوان التفصيلي', 'address', 'Address'),
    'email': (
        'البريد الإلكتروني',
        'البريد الالكتروني',
        'email',
        'Email',
    ),
    'contact_person': ('اسم المسؤول', 'المسؤول', 'contact', 'Contact'),
    'entity_type': ('نوع المتعاقد', 'entity_type'),
    'national_id': (
        'رقم هوية المتعاقد',
        'رقم الهوية',
        'national_id',
    ),
    'cr_number': ('رقم السجل التجاري', 'cr_number'),
    'vat_number': (
        'الرقم الضريبي',
        'الرقم الضريبي للعميل',
        'vat_number',
        'VAT',
    ),
    'national_address': (
        'العنوان الوطني',
        'national_address',
        'National Address',
    ),
    'code': ('رقم العميل', 'الكود', 'code', 'Code'),
    'status': ('حالة العميل', 'الحالة', 'status', 'Status'),
    'notes': ('ملاحظات', 'notes', 'Notes'),
}


def _compact(s: str) -> str:
    """إزالة المسافات لتسامح ملفات Excel التي فقدت المسافات في العناوين."""
    return re.sub(r'\s+', '', str(s or ''))


def _cell(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            val = str(row[key]).strip()
            if val and val.lower() != 'none':
                return val
    # مطابقة مرنة: مسافات زائدة أو عناوين بلا مسافات (رقمالهاتف)
    by_strip = {str(k).strip(): v for k, v in row.items() if k is not None}
    by_compact = {_compact(k): v for k, v in row.items() if k is not None}
    for key in keys:
        for table in (by_strip, by_compact):
            lookup = key if table is by_strip else _compact(key)
            if lookup in table and table[lookup] is not None:
                val = str(table[lookup]).strip()
                if val and val.lower() != 'none':
                    return val
    return ''


def normalize_import_row(row: dict[str, Any]) -> dict[str, str]:
    """حوّل صف Excel/JSON إلى حقول العميل القياسية."""
    if not isinstance(row, dict):
        return {}
    # إن كانت الحقول مُطبَّعة مسبقاً من الواجهة
    if row.get('name') or row.get('phone'):
        out = {k: str(row.get(k) or '').strip() for k in (
            'name', 'phone', 'city', 'district', 'address', 'email',
            'contact_person', 'entity_type', 'national_id', 'cr_number',
            'vat_number', 'national_address',
            'code', 'status', 'notes',
        )}
        # املأ الناقص من الأسماء البديلة
        for field, aliases in FIELD_ALIASES.items():
            if not out.get(field):
                out[field] = _cell(row, *aliases)
        return out

    return {field: _cell(row, *aliases) for field, aliases in FIELD_ALIASES.items()}


def _prepare_import_phone(phone_raw: str) -> str:
    """طبّع أرقام Excel (05… أو 5… أو +966…) قبل التحقق."""
    import re

    from app import format_phone_storage

    digits = re.sub(r'\D', '', phone_raw or '')
    if not digits:
        return ''
    if digits.startswith('966'):
        return format_phone_storage(phone_raw)
    if digits.startswith('0') and len(digits) >= 10:
        return format_phone_storage(phone_raw)
    if digits.startswith('5') and len(digits) == 9:
        return '+966' + digits
    return format_phone_storage(phone_raw) or (phone_raw or '').strip()


def import_customer_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """استيراد قائمة صفوف. يُرجع imported/failed/errors."""
    from form_validation import customer_name_error
    from models import Customer, db
    from sqlalchemy.exc import IntegrityError
    from tenant_scope import assign_organization

    # استيراد دوال التطبيق بعد تهيئة السياق
    from app import (
        _client_account_status,
        client_phone_error,
        next_code,
        phone_key,
        phone_taken,
    )

    imported = 0
    failed = 0
    errors: list[dict[str, Any]] = []
    seen_phones: set[str] = set()
    seen_names: set[str] = set()

    for idx, raw in enumerate(rows, start=1):
        data = normalize_import_row(raw or {})
        name = data.get('name') or ''
        if name == 'برج الياسمين':
            continue
        if not name:
            failed += 1
            errors.append({'row': idx, 'error': 'اسم العميل مطلوب'})
            continue

        name_key = name.strip().lower()
        if name_key in seen_names:
            failed += 1
            errors.append({'row': idx, 'error': f'اسم مكرر في الملف: {name}'})
            continue

        name_err = customer_name_error(name)
        if name_err:
            failed += 1
            errors.append({'row': idx, 'error': name_err})
            continue

        phone = _prepare_import_phone(data.get('phone') or '')
        phone_err = client_phone_error(phone)
        if phone_err:
            failed += 1
            errors.append({'row': idx, 'error': phone_err})
            continue

        phone_k = phone_key(phone)
        if phone_k and phone_k in seen_phones:
            failed += 1
            errors.append({'row': idx, 'error': f'رقم جوال مكرر في الملف: {phone}'})
            continue

        taken, msg = phone_taken(phone)
        if taken:
            failed += 1
            errors.append({'row': idx, 'error': msg})
            continue

        entity_type = data.get('entity_type') or 'فرد'
        if entity_type not in ('فرد', 'شركة'):
            entity_type = 'فرد'

        preferred = (data.get('code') or '').strip()
        code = _allocate_customer_code(preferred)

        payload = dict(
            name=name,
            city=data.get('city') or '',
            district=data.get('district') or '',
            address=data.get('address') or '',
            phone=phone,
            email=data.get('email') or '',
            contact_person=data.get('contact_person') or '',
            entity_type=entity_type,
            national_id=(data.get('national_id') or '') if entity_type != 'شركة' else '',
            cr_number=(data.get('cr_number') or '') if entity_type == 'شركة' else '',
            vat_number=(data.get('vat_number') or '') if entity_type == 'شركة' else '',
            national_address=(
                (data.get('national_address') or '') if entity_type == 'شركة' else ''
            ),
            status=_client_account_status(data.get('status') or 'نشط'),
            notes=data.get('notes') or '',
        )

        try:
            c = Customer(code=code, **payload)
            assign_organization(c)
            db.session.add(c)
            db.session.commit()
            imported += 1
            seen_names.add(name_key)
            if phone_k:
                seen_phones.add(phone_k)
        except IntegrityError as exc:
            db.session.rollback()
            # تعارض UNIQUE(code) القديم — أعد بكود جديد
            try:
                c = Customer(code=next_code(Customer, 'C-', digits=4), **payload)
                assign_organization(c)
                db.session.add(c)
                db.session.commit()
                imported += 1
                seen_names.add(name_key)
                if phone_k:
                    seen_phones.add(phone_k)
            except Exception as exc2:  # noqa: BLE001
                db.session.rollback()
                failed += 1
                errors.append({'row': idx, 'error': f'خطأ في الحفظ: {exc2}'})
        except Exception as exc:  # noqa: BLE001 — نُبلغ الصف ونكمل
            db.session.rollback()
            failed += 1
            errors.append({'row': idx, 'error': f'خطأ في الحفظ: {exc}'})

    return {
        'imported': imported,
        'failed': failed,
        'errors': errors[:20],
        'total': len(rows),
    }


def _allocate_customer_code(preferred: str) -> str:
    from app import _legacy_global_code_unique, next_code
    from models import Customer
    from tenant_scope import tenant_query

    code = (preferred or '').strip()
    if code:
        if tenant_query(Customer).filter_by(code=code).first():
            return next_code(Customer, 'C-', digits=4)
        if _legacy_global_code_unique('customers'):
            taken = (
                Customer.query.execution_options(skip_tenant=True)
                .filter_by(code=code)
                .first()
            )
            if taken:
                return next_code(Customer, 'C-', digits=4)
        return code
    return next_code(Customer, 'C-', digits=4)
