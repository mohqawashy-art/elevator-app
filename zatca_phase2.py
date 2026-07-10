"""ZATCA Phase 2 — فواتير ضريبية: UBL + تبليغ (B2C) + clearance (B2B).

الشرائح:
1) فاتورة مبسّطة + hash + mock/reporting
2) ECDSA + QR tags 6–8 + مصادقة CSID
3) فاتورة قياسية (B2B) + Clearance API + سلسلة PIH

XAdES-in-XML الكامل عبر SDK الهيئة يبقى لاحقاً؛ يُضمَّن حالياً توقيع ECDSA خفيف عبر zatca_xades.
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

# PIH لأول فاتورة — SHA-256 لسلسلة فارغة (base64) حسب ممارسة Fatoora الشائعة
DEFAULT_PIH = '47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSqg='

_ZATCA_UA = 'LiftCore/1.0 (+https://liftcoreapp.com; zatca-phase2)'


def is_simplified_tax_invoice(invoice_type: str | None) -> bool:
    return is_tax_invoice(invoice_type) and 'مبسطة' in (invoice_type or '')


def is_standard_tax_invoice(invoice_type: str | None) -> bool:
    """فاتورة ضريبية قياسية (B2B) — ليست مبسّطة."""
    return is_tax_invoice(invoice_type) and not is_simplified_tax_invoice(invoice_type)


def phase2_enabled() -> bool:
    """افتراضياً مفعّل؛ عطّل بـ LIFTCORE_ZATCA_PHASE2=0."""
    raw = os.environ.get('LIFTCORE_ZATCA_PHASE2', '1').strip().lower()
    return raw not in ('0', 'false', 'no', 'off')


def _fatoora_base(environment: str = 'sandbox') -> str:
    env = (environment or 'sandbox').strip().lower()
    if env == 'production':
        return 'https://gw-fatoora.zatca.gov.sa/e-invoicing/core'
    if env == 'simulation':
        return 'https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation'
    return 'https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal'


def reporting_url(environment: str = 'sandbox') -> str:
    override = os.environ.get('LIFTCORE_ZATCA_REPORT_URL', '').strip()
    if override:
        return override
    return f'{_fatoora_base(environment)}/invoices/reporting/single'


def clearance_url(environment: str = 'sandbox') -> str:
    override = os.environ.get('LIFTCORE_ZATCA_CLEARANCE_URL', '').strip()
    if override:
        return override
    return f'{_fatoora_base(environment)}/invoices/clearance/single'


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


def _pih_block(previous_hash: str) -> str:
    pih = (previous_hash or '').strip() or DEFAULT_PIH
    return f'''  <cac:AdditionalDocumentReference>
    <cbc:ID>PIH</cbc:ID>
    <cac:Attachment>
      <cbc:EmbeddedDocumentBinaryObject mimeCode="text/plain">{_esc(pih)}</cbc:EmbeddedDocumentBinaryObject>
    </cac:Attachment>
  </cac:AdditionalDocumentReference>
'''


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
    previous_hash: str = '',
) -> str:
    """UBL 2.1 مبسّط (B2C) — كافٍ للـ hash والتخزين؛ ليس بديلاً عن SDK الهيئة النهائي."""
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
{_pih_block(previous_hash)}  <cac:AccountingSupplierParty>
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


def build_standard_ubl_xml(
    *,
    invoice_uuid: str,
    invoice_code: str,
    issue_dt: datetime,
    seller_name: str,
    vat_number: str,
    buyer_name: str,
    buyer_vat: str = '',
    line_name: str,
    amount: float,
    tax_amount: float,
    total: float,
    tax_pct: float = 15.0,
    previous_hash: str = '',
) -> str:
    """UBL 2.1 قياسي (B2B) مع طرف المشتري — لمسار Clearance."""
    issue_date = issue_dt.strftime('%Y-%m-%d')
    issue_time = issue_dt.strftime('%H:%M:%S')
    buyer = (buyer_name or '').strip() or 'Customer'
    buyer_tax = ''
    if (buyer_vat or '').strip():
        buyer_tax = f'''
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{_esc(buyer_vat.strip())}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ProfileID>reporting:1.0</cbc:ProfileID>
  <cbc:ID>{_esc(invoice_code)}</cbc:ID>
  <cbc:UUID>{_esc(invoice_uuid)}</cbc:UUID>
  <cbc:IssueDate>{issue_date}</cbc:IssueDate>
  <cbc:IssueTime>{issue_time}</cbc:IssueTime>
  <cbc:InvoiceTypeCode name="0100000">388</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>SAR</cbc:DocumentCurrencyCode>
{_pih_block(previous_hash)}  <cac:AccountingSupplierParty>
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
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>{_esc(buyer)}</cbc:RegistrationName>
      </cac:PartyLegalEntity>{buyer_tax}
    </cac:Party>
  </cac:AccountingCustomerParty>
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


def previous_invoice_hash(*, exclude_invoice_id: int | None = None) -> str:
    """آخر hash ناجح في المؤسسة الحالية — لسلسلة PIH."""
    from models import Invoice
    from tenant_scope import tenant_query

    q = tenant_query(Invoice).filter(
        Invoice.zatca_status.in_(('reported', 'cleared')),
        Invoice.zatca_invoice_hash.isnot(None),
    )
    if exclude_invoice_id:
        q = q.filter(Invoice.id != exclude_invoice_id)
    prev = q.order_by(Invoice.id.desc()).first()
    if prev and (prev.zatca_invoice_hash or '').strip():
        return prev.zatca_invoice_hash.strip()
    return DEFAULT_PIH


def submit_zatca_document(
    *,
    xml_text: str,
    invoice_hash: str,
    invoice_uuid: str,
    mode: str = 'reporting',
    environment: str = 'sandbox',
    binary_security_token: str = '',
    api_secret: str = '',
) -> dict:
    """يرسل XML لـ reporting (B2C) أو clearance (B2B) أو يعيد نتيجة mock."""
    mode = (mode or 'reporting').strip().lower()
    success_status = 'cleared' if mode == 'clearance' else 'reported'

    if use_mock_client():
        return {
            'ok': True,
            'mock': True,
            'status': success_status,
            'mode': mode,
            'message': f'mock {mode} accepted',
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

    url = clearance_url(environment) if mode == 'clearance' else reporting_url(environment)
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Accept-Version': 'V2',
        'Accept-Language': 'ar',
        'User-Agent': _ZATCA_UA,
    }
    if mode == 'clearance':
        headers['Clearance-Status'] = '1'
    if binary_security_token and api_secret:
        headers['Authorization'] = basic_auth_header(binary_security_token, api_secret)

    req = urlrequest.Request(url, data=payload, headers=headers, method='POST')
    try:
        with urlrequest.urlopen(req, timeout=45) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            ok = 200 <= resp.status < 300
            return {
                'ok': ok,
                'mock': False,
                'status': success_status if ok else 'failed',
                'mode': mode,
                'http_status': resp.status,
                'body': body[:2000],
            }
    except urlerror.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace') if exc.fp else str(exc)
        # developer-portal قد يعيد 303 عند تعطيل clearance
        if mode == 'clearance' and exc.code == 303:
            return {
                'ok': False,
                'mock': False,
                'status': 'failed',
                'mode': mode,
                'http_status': 303,
                'body': body[:2000],
                'message': 'Clearance غير مفعّل في هذه البيئة — جرّب simulation أو reporting للمبسّطة.',
            }
        return {
            'ok': False,
            'mock': False,
            'status': 'failed',
            'mode': mode,
            'http_status': exc.code,
            'body': body[:2000],
            'message': str(exc),
        }
    except urlerror.URLError as exc:
        return {
            'ok': False,
            'mock': False,
            'status': 'failed',
            'mode': mode,
            'message': str(exc.reason or exc),
        }


def submit_simplified_report(
    *,
    xml_text: str,
    invoice_hash: str,
    invoice_uuid: str,
    environment: str = 'sandbox',
    binary_security_token: str = '',
    api_secret: str = '',
) -> dict:
    """توافق خلفي — تبليغ فاتورة مبسّطة."""
    return submit_zatca_document(
        xml_text=xml_text,
        invoice_hash=invoice_hash,
        invoice_uuid=invoice_uuid,
        mode='reporting',
        environment=environment,
        binary_security_token=binary_security_token,
        api_secret=api_secret,
    )


def _apply_result_to_invoice(invoice, *, invoice_uuid: str, inv_hash: str, qr_payload: str, result: dict) -> dict:
    from models import db

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


def process_simplified_invoice(invoice, settings) -> dict:
    """بعد إنشاء فاتورة مبسطة — يبني XML ويحدّث حقول zatca_* على السجل."""
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
    pih = previous_invoice_hash(exclude_invoice_id=getattr(invoice, 'id', None))

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
        previous_hash=pih,
    )
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
            from zatca_xades import embed_ecdsa_signature
            signature_b64 = sign_invoice_hash(inv_hash, key_pem)
            public_key_b64 = certificate_public_key_b64(cert_pem)
            xml_text = embed_ecdsa_signature(
                xml_text,
                invoice_hash_b64=inv_hash,
                private_key_pem=key_pem,
                certificate_pem=cert_pem,
            )
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
    result = submit_zatca_document(
        xml_text=xml_text,
        invoice_hash=inv_hash,
        invoice_uuid=invoice_uuid,
        mode='reporting',
        environment=env,
        binary_security_token=_cred_plain(creds, 'csid') if creds else '',
        api_secret=_cred_plain(creds, 'api_secret') if creds else '',
    )
    return _apply_result_to_invoice(
        invoice,
        invoice_uuid=invoice_uuid,
        inv_hash=inv_hash,
        qr_payload=qr_payload,
        result=result,
    )


def process_standard_invoice(invoice, settings) -> dict:
    """فاتورة ضريبية قياسية (B2B) — Clearance."""
    if not phase2_enabled():
        invoice.zatca_status = 'skipped'
        return {'ok': True, 'status': 'skipped', 'reason': 'phase2_disabled'}

    if not is_standard_tax_invoice(invoice.invoice_type):
        invoice.zatca_status = 'skipped'
        return {'ok': True, 'status': 'skipped', 'reason': 'not_standard'}

    vat = tenant_vat_number()
    if not vat:
        invoice.zatca_status = 'failed'
        invoice.zatca_last_error = 'لا يوجد رقم ضريبي نشط'
        return {'ok': False, 'status': 'failed', 'message': invoice.zatca_last_error}

    seller = (settings.company_name or '').strip() or 'Seller'
    issue_dt = datetime.utcnow()
    if invoice.invoice_date:
        issue_dt = datetime.combine(invoice.invoice_date, issue_dt.time())

    buyer_name = ''
    buyer_vat = ''
    customer = getattr(invoice, 'customer', None)
    if customer is None and getattr(invoice, 'customer_id', None):
        from models import Customer, db
        customer = db.session.get(Customer, invoice.customer_id)
    if customer:
        buyer_name = (customer.name or '').strip()
        buyer_vat = (getattr(customer, 'vat_number', None) or '').strip()

    invoice_uuid = str(uuid.uuid4())
    amount = float(invoice.amount or 0)
    tax_amount = float(invoice.tax_amount or 0)
    total = float(invoice.total or 0)
    line_name = (invoice.description or invoice.code or 'خدمة').strip()
    pih = previous_invoice_hash(exclude_invoice_id=getattr(invoice, 'id', None))

    xml_text = build_standard_ubl_xml(
        invoice_uuid=invoice_uuid,
        invoice_code=invoice.code or '',
        issue_dt=issue_dt,
        seller_name=seller,
        vat_number=vat,
        buyer_name=buyer_name,
        buyer_vat=buyer_vat,
        line_name=line_name,
        amount=amount,
        tax_amount=tax_amount,
        total=total,
        tax_pct=float(getattr(settings, 'tax_pct', None) or 15),
        previous_hash=pih,
    )
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
            from zatca_xades import embed_ecdsa_signature
            signature_b64 = sign_invoice_hash(inv_hash, key_pem)
            public_key_b64 = certificate_public_key_b64(cert_pem)
            xml_text = embed_ecdsa_signature(
                xml_text,
                invoice_hash_b64=inv_hash,
                private_key_pem=key_pem,
                certificate_pem=cert_pem,
            )
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
    result = submit_zatca_document(
        xml_text=xml_text,
        invoice_hash=inv_hash,
        invoice_uuid=invoice_uuid,
        mode='clearance',
        environment=env,
        binary_security_token=_cred_plain(creds, 'csid') if creds else '',
        api_secret=_cred_plain(creds, 'api_secret') if creds else '',
    )
    return _apply_result_to_invoice(
        invoice,
        invoice_uuid=invoice_uuid,
        inv_hash=inv_hash,
        qr_payload=qr_payload,
        result=result,
    )


def process_tax_invoice(invoice, settings) -> dict:
    """مدخل موحّد: مبسّطة → reporting، قياسية → clearance، غير ضريبية → skip."""
    if not is_tax_invoice(invoice.invoice_type):
        invoice.zatca_status = 'skipped'
        return {'ok': True, 'status': 'skipped', 'reason': 'not_tax_invoice'}
    if is_simplified_tax_invoice(invoice.invoice_type):
        return process_simplified_invoice(invoice, settings)
    return process_standard_invoice(invoice, settings)


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
