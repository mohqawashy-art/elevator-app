"""بيانات طباعة الفاتورة الضريبية / سند القبض — LiftCore."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from flask import url_for

from contract_print import amount_in_words
from models import Contract, Customer, Invoice, Settings
from tenant_scope import tenant_query
from zatca_tenant import tenant_vat_number
from zatca_qr import (
    is_tax_invoice as zatca_is_tax_invoice,
    zatca_phase1_tlv_base64,
    zatca_qr_image_data_url,
)


@dataclass
class PrintLineItem:
    name: str
    qty: float
    unit: str
    unit_price: float
    discount: float
    total: float
    vat_rate: float = 15.0
    vat_amount: float = 0.0
    total_incl_vat: float = 0.0


def _logo_url(settings: Settings) -> str:
    if settings.logo_path:
        return url_for('static', filename=settings.logo_path.replace('\\', '/'))
    return url_for('static', filename='logo.png')


def _customer_address(customer: Customer | None) -> str:
    if not customer:
        return ''
    parts = [p for p in (customer.address, customer.district, customer.city) if (p or '').strip()]
    return ' — '.join(parts)


def _supplier_address(settings: Settings) -> str:
    parts = [p for p in (settings.city, settings.address) if (p or '').strip()]
    return ' — '.join(parts) if parts else ''


def _payment_method_ar(raw: str | None) -> str:
    val = (raw or '').strip()
    return val or '—'


def _fmt_date(d: date | None) -> str:
    if not d:
        return '—'
    return d.strftime('%d/%m/%Y')


def _fmt_time_12h(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    ampm = 'PM' if dt.hour >= 12 else 'AM'
    return f'{h:02d}:{dt.minute:02d} {ampm}'


def _is_simplified(invoice_type: str | None) -> bool:
    return 'مبسطة' in (invoice_type or '')


def _is_paid_status(status: str | None) -> bool:
    s = (status or '').strip()
    return s in ('مدفوعة', 'مسددة', 'مدفوع', 'Paid', 'paid')


def _doc_titles(invoice_type: str | None, is_tax: bool, is_receipt: bool, is_simplified: bool) -> tuple[str, str]:
    t = (invoice_type or '').strip()
    if is_receipt or 'سند' in t:
        return 'سند قبض', 'Receipt Voucher'
    if is_simplified:
        return 'فاتورة ضريبية مبسطة', 'Simplified Tax Invoice'
    if is_tax:
        return 'فاتورة ضريبية', 'Tax Invoice'
    return 'فاتورة', 'Invoice'


def _compliance_warnings(
    settings: Settings,
    customer: Customer | None,
    *,
    is_tax: bool,
    is_receipt: bool,
    is_simplified: bool,
    show_zatca_qr: bool,
    vat_number: str,
    line_items: list[PrintLineItem],
) -> list[str]:
    if not is_tax or is_receipt:
        return []

    warnings: list[str] = []
    if not (settings.company_name or '').strip():
        warnings.append('اسم المورد (البائع) غير مسجّل في إعدادات الشركة — مطلوب ZATCA.')
    if not vat_number:
        warnings.append('الرقم الضريبي للمورد (15 رقم) غير مسجّل — مطلوب ZATCA.')
    elif len(vat_number.replace(' ', '')) != 15 or not vat_number.isdigit():
        warnings.append('تحقق من الرقم الضريبي للمورد — يجب أن يكون 15 رقمًا.')
    if not (settings.cr_number or '').strip():
        warnings.append('السجل التجاري للمورد غير مسجّل في الإعدادات.')
    if not _supplier_address(settings):
        warnings.append('عنوان المورد غير مكتمل في الإعدادات — مطلوب ZATCA.')
    if not show_zatca_qr and vat_number:
        warnings.append('رمز QR (المرحلة الأولى) غير متوفر — مطلوب على الفاتورة الضريبية.')
    if not is_simplified:
        if not customer or not (customer.name or '').strip():
            warnings.append('اسم المشتري (العميل) مطلوب في الفاتورة الضريبية (B2B).')
        if customer and not _customer_address(customer):
            warnings.append('عنوان المشتري غير مسجّل — مطلوب في الفاتورة الضريبية (B2B).')
    for ln in line_items:
        if not (ln.name or '').strip() or ln.name == '—':
            warnings.append('وصف البند / الخدمة مطلوب على الفاتورة.')
            break
    return warnings


def _amount_in_words_sar(total: float) -> str:
    t = round(float(total or 0), 2)
    riyals = int(t)
    halalas = int(round((t - riyals) * 100))
    core = amount_in_words(riyals)
    if halalas > 0:
        return f'{core} ريال سعودي و{amount_in_words(halalas)} هللة فقط لا غير'
    return f'{core} ريال سعودي فقط لا غير'


def invoice_print_payload(invo: Invoice, *, base_url: str = '') -> dict:
    settings = tenant_query(Settings).first()
    if not settings:
        raise RuntimeError('إعدادات النظام غير موجودة')

    customer = (
        tenant_query(Customer).filter_by(id=invo.customer_id).first()
        if invo.customer_id else None
    )
    contract = (
        tenant_query(Contract).filter_by(id=invo.contract_id).first()
        if invo.contract_id else None
    )

    tax_pct = float(settings.tax_pct or 15)
    is_receipt = not zatca_is_tax_invoice(invo.invoice_type)
    is_tax = zatca_is_tax_invoice(invo.invoice_type)
    is_simplified = _is_simplified(invo.invoice_type)
    doc_title, doc_title_en = _doc_titles(invo.invoice_type, is_tax, is_receipt, is_simplified)
    page_size = 'A5' if is_receipt else 'A4'
    status = invo.status or '—'
    is_paid = _is_paid_status(status)

    inv_date = invo.invoice_date or date.today()
    supply_date = inv_date
    issue_dt = datetime.combine(inv_date, time(12, 0, 0))
    if invo.created_at:
        issue_dt = invo.created_at

    amount = float(invo.amount or 0)
    tax_amount = float(invo.tax_amount or 0)
    total = float(invo.total or 0)
    if total <= 0 and amount > 0:
        total = round(amount + tax_amount, 2)
    if tax_amount <= 0 and is_tax and amount > 0:
        tax_amount = round(amount * tax_pct / 100, 2)
        total = round(amount + tax_amount, 2)

    desc = (invo.description or '').strip() or '—'
    line = PrintLineItem(
        name=desc,
        qty=1,
        unit='خدمة',
        unit_price=round(amount, 2),
        discount=0.0,
        total=round(amount, 2),
        vat_rate=tax_pct,
        vat_amount=round(tax_amount, 2),
        total_incl_vat=round(total, 2),
    )
    line_items = [line]
    items_subtotal = round(amount, 2)
    total_discount = 0.0

    company_name = settings.company_name or '—'
    vat_number = tenant_vat_number() if is_tax else (settings.vat_number or '').strip().replace(' ', '')
    cr_number = (settings.cr_number or '').strip()

    zatca_qr_image = ''
    zatca_warning = ''
    show_zatca_qr = False
    if is_tax and not is_receipt and vat_number:
        try:
            from zatca_phase2 import qr_tlv_from_invoice
            stored_tlv = qr_tlv_from_invoice(invo)
            tlv = stored_tlv or zatca_phase1_tlv_base64(
                seller_name=company_name,
                vat_number=vat_number,
                invoice_date=inv_date,
                invoice_total=total,
                vat_total=tax_amount,
                timestamp=issue_dt,
            )
            zatca_qr_image = zatca_qr_image_data_url(tlv) or ''
            show_zatca_qr = bool(zatca_qr_image)
            if not zatca_qr_image:
                zatca_warning = 'تعذّر إنشاء رمز QR — ثبّت qrcode[pil] على الخادم.'
        except Exception as exc:
            zatca_warning = f'تعذّر إنشاء رمز QR: {exc}'

    logo_width = int(settings.logo_width_report or 150)
    currency_code = (settings.currency or 'SAR').strip() or 'SAR'
    bank_name = (getattr(settings, 'bank_name', None) or '').strip()
    bank_account_name = (getattr(settings, 'bank_account_name', None) or '').strip()
    bank_iban = (getattr(settings, 'bank_iban', None) or '').strip()
    bank_account_no = (getattr(settings, 'bank_account_no', None) or '').strip()
    company_website = (getattr(settings, 'company_website', None) or '').strip()
    show_bank = bool(bank_name or bank_iban or bank_account_no)

    from operations import build_invoice_payment_whatsapp, invoice_whatsapp_eligible

    show_whatsapp_payment = invoice_whatsapp_eligible(invo)
    whatsapp_payment_url = (
        build_invoice_payment_whatsapp(invo, base_url)
        if base_url and show_whatsapp_payment
        else ''
    )

    return {
        'doc_title': doc_title,
        'doc_title_en': doc_title_en,
        'invoice_type_label': (invo.invoice_type or doc_title).strip(),
        'irn': invo.code,
        'logo_url': _logo_url(settings),
        'logo_width': logo_width,
        'page_size': page_size,
        'is_receipt': is_receipt,
        'is_tax_invoice': is_tax,
        'is_simplified': is_simplified,
        'is_paid': is_paid,
        'company_name': company_name,
        'company_name_en': settings.company_name_en or '',
        'company_phone': settings.phone or '',
        'company_email': settings.email or '',
        'company_website': company_website,
        'vat_number': vat_number,
        'cr_number': cr_number,
        'seller_id_type': 'السجل التجاري',
        'supplier_address': _supplier_address(settings) or '—',
        'customer_name': (customer.name if customer else '—'),
        'customer_code': (customer.code if customer else '—'),
        'customer_city': (customer.city if customer else '') or '—',
        'customer_district': (customer.district if customer else '') or '—',
        'customer_address_line': (customer.address if customer else '') or '—',
        'customer_phone': (customer.phone if customer else '') or '',
        'buyer_address': _customer_address(customer),
        'buyer_cr': (customer.cr_number or '').strip() if customer else '',
        'invoice_date': _fmt_date(inv_date),
        'issue_date_display': _fmt_date(inv_date),
        'issue_date_iso': inv_date.isoformat(),
        'issue_time': issue_dt.strftime('%H:%M:%S'),
        'issue_time_display': _fmt_time_12h(issue_dt),
        'supply_date_display': _fmt_date(supply_date),
        'due_date_display': _fmt_date(invo.due_date) if invo.due_date else '—',
        'payment_method_ar': _payment_method_ar(invo.payment_method),
        'contract_code': contract.code if contract else '—',
        'status': status,
        'line_items': line_items,
        'notes': (invo.notes or '').strip(),
        'items_subtotal': items_subtotal,
        'total_discount': total_discount,
        'taxable_amount': items_subtotal - total_discount,
        'tax_pct': tax_pct,
        'tax_amount': round(tax_amount, 2),
        'total': round(total, 2),
        'total_words': _amount_in_words_sar(total),
        'currency_code': currency_code,
        'currency_label': 'ريال سعودي' if currency_code == 'SAR' else currency_code,
        'amount_includes_vat_label': 'المبلغ شامل ضريبة القيمة المضافة',
        'show_zatca_qr': show_zatca_qr,
        'zatca_qr_image': zatca_qr_image,
        'zatca_warning': zatca_warning,
        'show_bank': show_bank,
        'bank_name': bank_name,
        'bank_account_name': bank_account_name or company_name,
        'bank_iban': bank_iban,
        'bank_account_no': bank_account_no,
        'compliance_warnings': _compliance_warnings(
            settings,
            customer,
            is_tax=is_tax,
            is_receipt=is_receipt,
            is_simplified=is_simplified,
            show_zatca_qr=show_zatca_qr,
            vat_number=vat_number,
            line_items=line_items,
        ),
        'whatsapp_payment_url': whatsapp_payment_url,
        'show_whatsapp_payment': show_whatsapp_payment,
        'invoice_id': invo.id,
    }
