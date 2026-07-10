"""ZATCA Phase 2 — فاتورة ضريبية مبسّطة: UBL خفيف + تبليغ sandbox.

الشريحة الأولى:
- بناء XML مبسّط + hash SHA-256
- تخزين uuid/hash/QR payload وحالة التبليغ على Invoice
- عميل HTTP للـ sandbox (أو وضع mock للاختبارات بدون شبكة)

التوقيع الكامل (ECDSA + CSID) وB2B clearance يُضافان لاحقاً.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib import error as urlerror
from urllib import request as urlrequest

from zatca_qr import is_tax_invoice, zatca_phase1_tlv_base64
from zatca_tenant import active_zatca_credentials, decrypt_zatca_field, tenant_vat_number


def is_simplified_tax_invoice(invoice_type: str | None) -> bool:
    return is_tax_invoice(invoice_type) and 'مبسطة' in (invoice_type or '')


def phase2_enabled() -> bool:
    """افتراضياً مفعّل؛ عطّل بـ LIFTCORE_ZATCA_PHASE2=0."""
    raw = os.environ.get('LIFTCORE_ZATCA_PHASE2', '1').strip().lower()
    return raw not in ('0', 'false', 'no', 'off')


def reporting_url(environment: str = 'sandbox') -> str:
    override = os.environ.get('LIFTCORE_ZATCA_REPORT_URL', '').strip()
    if override:
        return override
    env = (environment or 'sandbox').strip().lower()
    if env == 'production':
        return 'https://gw-fatoora.zatca.gov.sa/e-invoicing/core/invoices/reporting/single'
    if env == 'simulation':
        return 'https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation/invoices/reporting/single'
    # sandbox / developer-portal
    return 'https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal/invoices/reporting/single'


def sandbox_reporting_url() -> str:
    return reporting_url('sandbox')


def _cred_plain(creds, field: str) -> str:
    raw = getattr(creds, field, None) if creds else None
    return (decrypt_zatca_field(raw) or (raw or '')).strip()


def use_mock_client() -> bool:
    """mock عند غياب اعتمادات كاملة أو LIFTCORE_ZATCA_MOCK=1."""
    if os.environ.get('LIFTCORE_ZATCA_MOCK', '').strip().lower() in ('1', 'true', 'yes'):
        return True
    creds = active_zatca_credentials()
    if not creds:
        return True
    has_cert = bool(_cred_plain(creds, 'certificate'))
    has_key = bool(_cred_plain(creds, 'private_key'))
    has_csid = bool(_cred_plain(creds, 'csid'))
    has_secret = bool(_cred_plain(creds, 'api_secret'))
    return not (has_cert and has_key and has_csid and has_secret)


def _esc(text: str) -> str:
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def build_simplified_ubl_xml(
    *,
    invoice_uuid: str,
    invoice_code: str,
    issue_dt: datetime,
    seller_name: str,
    vat_number: str,
    line_name: str,
    amount: float,
    tax_amount: float,
    total: float,
    tax_pct: float = 15.0,
) -> str:
    """UBL 2.1 مبسّط — كافٍ للـ hash والتخزين؛ ليس بديلاً عن SDK الهيئة النهائي."""
    issue_date = issue_dt.strftime('%Y-%m-%d')
    issue_time = issue_dt.strftime('%H:%M:%S')
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ProfileID>reporting:1.0</cbc:ProfileID>
  <cbc:ID>{_esc(invoice_code)}</cbc:ID>
  <cbc:UUID>{_esc(invoice_uuid)}</cbc:UUID>
  <cbc:IssueDate>{issue_date}</cbc:IssueDate>
  <cbc:IssueTime>{issue_time}</cbc:IssueTime>
  <cbc:InvoiceTypeCode name="0200000">388</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>SAR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>{_esc(seller_name)}</cbc:RegistrationName>
      </cac:PartyLegalEntity>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{_esc(vat_number)}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="SAR">{tax_amount:.2f}</cbc:TaxAmount>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="SAR">{amount:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="SAR">{amount:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="SAR">{total:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="SAR">{total:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="PCE">1</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="SAR">{amount:.2f}</cbc:LineExtensionAmount>
    <cac:Item>
      <cbc:Name>{_esc(line_name or 'خدمة')}</cbc:Name>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="SAR">{amount:.2f}</cbc:PriceAmount>
    </cac:Price>
    <cac:TaxTotal>
      <cbc:TaxAmount currencyID="SAR">{tax_amount:.2f}</cbc:TaxAmount>
      <cac:TaxSubtotal>
        <cbc:TaxableAmount currencyID="SAR">{amount:.2f}</cbc:TaxableAmount>
        <cbc:TaxAmount currencyID="SAR">{tax_amount:.2f}</cbc:TaxAmount>
        <cac:TaxCategory>
          <cbc:ID>S</cbc:ID>
          <cbc:Percent>{tax_pct:.2f}</cbc:Percent>
          <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
        </cac:TaxCategory>
      </cac:TaxSubtotal>
    </cac:TaxTotal>
  </cac:InvoiceLine>
</Invoice>
'''


def invoice_hash_from_xml(xml_text: str) -> str:
    digest = hashlib.sha256(xml_text.encode('utf-8')).digest()
    import base64
    return base64.b64encode(digest).decode('ascii')


def build_phase2_qr_payload(
    *,
    seller_name: str,
    vat_number: str,
    invoice_date,
    invoice_total: float,
    vat_total: float,
    invoice_hash: str,
    signature_b64: str = '',
    public_key_b64: str = '',
    timestamp: datetime | None = None,
) -> str:
    """JSON للتتبع + TLV للطباعة (Phase 2 إن وُجد توقيع، وإلا Phase 1)."""
    from zatca_qr import zatca_phase2_tlv_base64

    if signature_b64 and public_key_b64:
        tlv = zatca_phase2_tlv_base64(
            seller_name=seller_name,
            vat_number=vat_number,
            invoice_date=invoice_date,
            invoice_total=invoice_total,
            vat_total=vat_total,
            invoice_hash_b64=invoice_hash,
            signature_b64=signature_b64,
            public_key_b64=public_key_b64,
            timestamp=timestamp,
        )
        phase = 2
    else:
        tlv = zatca_phase1_tlv_base64(
            seller_name=seller_name,
            vat_number=vat_number,
            invoice_date=invoice_date,
            invoice_total=invoice_total,
            vat_total=vat_total,
            timestamp=timestamp,
        )
        phase = 1
    return json.dumps({
        'tlv': tlv,
        'hash': invoice_hash,
        'signature': signature_b64 or None,
        'phase': phase,
    }, ensure_ascii=False)


def submit_simplified_report(
    *,
    xml_text: str,
    invoice_hash: str,
    invoice_uuid: str,
    environment: str = 'sandbox',
    binary_security_token: str = '',
    api_secret: str = '',
) -> dict:
    """يرسل XML للـ sandbox/simulation/production أو يعيد نتيجة mock."""
    if use_mock_client():
        return {
            'ok': True,
            'mock': True,
            'status': 'reported',
            'message': 'mock report accepted',
            'environment': environment or 'sandbox',
            'hash': invoice_hash,
        }

    import base64

    from zatca_crypto import basic_auth_header

    payload = json.dumps({
        'invoiceHash': invoice_hash,
        'uuid': invoice_uuid,
        'invoice': base64.b64encode(xml_text.encode('utf-8')).decode('ascii'),
    }).encode('utf-8')

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Accept-Version': 'V2',
        'Accept-Language': 'ar',
    }
    if binary_security_token and api_secret:
        headers['Authorization'] = basic_auth_header(binary_security_token, api_secret)

    req = urlrequest.Request(
        reporting_url(environment),
        data=payload,
        headers=headers,
        method='POST',
    )
    try:
        with urlrequest.urlopen(req, timeout=45) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            return {
                'ok': 200 <= resp.status < 300,
                'mock': False,
                'status': 'reported' if 200 <= resp.status < 300 else 'failed',
                'http_status': resp.status,
                'body': body[:2000],
            }
    except urlerror.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace') if exc.fp else str(exc)
        return {
            'ok': False,
            'mock': False,
            'status': 'failed',
            'http_status': exc.code,
            'body': body[:2000],
            'message': str(exc),
        }
    except urlerror.URLError as exc:
        return {
            'ok': False,
            'mock': False,
            'status': 'failed',
            'message': str(exc.reason or exc),
        }


def process_simplified_invoice(invoice, settings) -> dict:
    """بعد إنشاء فاتورة مبسطة — يبني XML ويحدّث حقول zatca_* على السجل."""
    from models import db

    if not phase2_enabled():
        invoice.zatca_status = 'skipped'
        return {'ok': True, 'status': 'skipped', 'reason': 'phase2_disabled'}

    if not is_simplified_tax_invoice(invoice.invoice_type):
        invoice.zatca_status = 'skipped'
        return {'ok': True, 'status': 'skipped', 'reason': 'not_simplified'}

    vat = tenant_vat_number()
    if not vat:
        invoice.zatca_status = 'failed'
        invoice.zatca_last_error = 'لا يوجد رقم ضريبي نشط'
        return {'ok': False, 'status': 'failed', 'message': invoice.zatca_last_error}

    seller = (settings.company_name or '').strip() or 'Seller'
    issue_dt = datetime.utcnow()
    if invoice.invoice_date:
        issue_dt = datetime.combine(invoice.invoice_date, issue_dt.time())

    invoice_uuid = str(uuid.uuid4())
    amount = float(invoice.amount or 0)
    tax_amount = float(invoice.tax_amount or 0)
    total = float(invoice.total or 0)
    line_name = (invoice.description or invoice.code or 'خدمة').strip()

    xml_text = build_simplified_ubl_xml(
        invoice_uuid=invoice_uuid,
        invoice_code=invoice.code or '',
        issue_dt=issue_dt,
        seller_name=seller,
        vat_number=vat,
        line_name=line_name,
        amount=amount,
        tax_amount=tax_amount,
        total=total,
        tax_pct=float(getattr(settings, 'tax_pct', None) or 15),
    )
    # تحقق أن XML قابل للتحليل
    ET.fromstring(xml_text)

    inv_hash = invoice_hash_from_xml(xml_text)

    signature_b64 = ''
    public_key_b64 = ''
    creds = active_zatca_credentials()
    key_pem = _cred_plain(creds, 'private_key') if creds else ''
    cert_pem = _cred_plain(creds, 'certificate') if creds else ''
    if key_pem and cert_pem:
        try:
            from zatca_crypto import certificate_public_key_b64, sign_invoice_hash
            signature_b64 = sign_invoice_hash(inv_hash, key_pem)
            public_key_b64 = certificate_public_key_b64(cert_pem)
        except Exception as exc:
            invoice.zatca_status = 'failed'
            invoice.zatca_last_error = f'فشل التوقيع: {exc}'[:2000]
            return {'ok': False, 'status': 'failed', 'message': invoice.zatca_last_error}

    qr_payload = build_phase2_qr_payload(
        seller_name=seller,
        vat_number=vat,
        invoice_date=invoice.invoice_date or issue_dt.date(),
        invoice_total=total,
        vat_total=tax_amount,
        invoice_hash=inv_hash,
        signature_b64=signature_b64,
        public_key_b64=public_key_b64,
        timestamp=issue_dt,
    )

    env = (creds.environment if creds else None) or 'sandbox'
    result = submit_simplified_report(
        xml_text=xml_text,
        invoice_hash=inv_hash,
        invoice_uuid=invoice_uuid,
        environment=env,
        binary_security_token=_cred_plain(creds, 'csid') if creds else '',
        api_secret=_cred_plain(creds, 'api_secret') if creds else '',
    )

    invoice.zatca_uuid = invoice_uuid
    invoice.zatca_invoice_hash = inv_hash
    invoice.zatca_qr_payload = qr_payload
    invoice.zatca_status = result.get('status') or ('reported' if result.get('ok') else 'failed')
    if result.get('ok'):
        invoice.zatca_reported_at = datetime.utcnow()
        invoice.zatca_last_error = None
    else:
        invoice.zatca_last_error = (result.get('message') or result.get('body') or 'report failed')[:2000]

    db.session.add(invoice)
    return result


def sync_zatca_credentials_from_settings(settings) -> None:
    """مزامنة الرقم الضريبي/السجل من إعدادات الشركة إلى zatca_credentials."""
    from models import ZatcaCredentials, db
    from tenant_scope import assign_organization, tenant_query

    vat = (settings.vat_number or '').strip().replace(' ', '')
    cr = (settings.cr_number or '').strip()
    if not vat:
        return

    creds = tenant_query(ZatcaCredentials).first()
    if not creds:
        creds = ZatcaCredentials(
            vat_number=vat,
            cr_number=cr or None,
            status='active',
            environment='sandbox',
        )
        assign_organization(creds)
        db.session.add(creds)
    else:
        creds.vat_number = vat
        if cr:
            creds.cr_number = cr
        if creds.status == 'pending' and vat:
            creds.status = 'active'


def save_zatca_credentials_form(form) -> str | None:
    """يحفظ نموذج إعدادات الفوترة الإلكترونية. يعيد رسالة خطأ أو None."""
    from datetime import datetime

    from models import ZatcaCredentials, db
    from tenant_scope import assign_organization, tenant_query
    from zatca_tenant import encrypt_zatca_field

    vat = (form.get('zatca_vat_number') or '').strip().replace(' ', '')
    if not vat:
        return 'الرقم الضريبي مطلوب للفوترة الإلكترونية.'

    cr = (form.get('zatca_cr_number') or '').strip()
    environment = (form.get('zatca_environment') or 'sandbox').strip().lower()
    if environment not in ('sandbox', 'simulation', 'production'):
        environment = 'sandbox'
    status = (form.get('zatca_status') or 'active').strip().lower()
    if status not in ('pending', 'active', 'expired'):
        status = 'active'

    csid_plain = (form.get('zatca_csid') or '').strip()
    cert_plain = (form.get('zatca_certificate') or '').strip()
    key_plain = (form.get('zatca_private_key') or '').strip()
    secret_plain = (form.get('zatca_api_secret') or '').strip()

    creds = tenant_query(ZatcaCredentials).first()
    if not creds:
        creds = ZatcaCredentials(vat_number=vat)
        assign_organization(creds)
        db.session.add(creds)

    creds.vat_number = vat
    creds.cr_number = cr or None
    creds.environment = environment
    creds.status = status
    if csid_plain:
        creds.csid = encrypt_zatca_field(csid_plain)
    if cert_plain:
        creds.certificate = encrypt_zatca_field(cert_plain)
    if key_plain:
        creds.private_key = encrypt_zatca_field(key_plain)
    if secret_plain:
        creds.api_secret = encrypt_zatca_field(secret_plain)
    if status == 'active' and (creds.certificate or creds.csid):
        creds.onboarded_at = creds.onboarded_at or datetime.utcnow()

    # مزامنة عكسية لـ settings الظاهرة في الطباعة
    from models import Settings
    from tenant_scope import tenant_query as tq

    s = tq(Settings).first()
    if s:
        s.vat_number = vat
        if cr:
            s.cr_number = cr

    db.session.commit()
    return None


def qr_tlv_from_invoice(invoice) -> str | None:
    """TLV للطباعة — من payload Phase 2 إن وُجد."""
    raw = (getattr(invoice, 'zatca_qr_payload', None) or '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return (data.get('tlv') or '').strip() or None
    except (TypeError, ValueError, json.JSONDecodeError):
        # قد يكون TLV مباشرة
        return raw if len(raw) > 20 else None
