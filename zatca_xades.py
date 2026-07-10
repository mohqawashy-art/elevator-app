"""تضمين توقيع خفيف داخل UBL — خطوة نحو XAdES (ليس بديلاً عن SDK الهيئة).

يُدرج UBLExtensions + ds:Signature بقيمة ECDSA ومرجع الشهادة.
لا ينفّذ C14N كاملاً ولا SignedProperties XAdES-BES الرسمية.
"""
from __future__ import annotations

import re

from zatca_crypto import certificate_hash_b64, sign_invoice_hash


_EXTENSION_NS = (
    'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
    'xmlns:sig="urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2" '
    'xmlns:sac="urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2" '
    'xmlns:sbc="urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2" '
    'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"'
)


def embed_ecdsa_signature(xml_text: str, *, invoice_hash_b64: str, private_key_pem: str, certificate_pem: str) -> str:
    """يعيد XML مع كتلة توقيع بعد جذر Invoice — أو النص الأصلي إن فشل."""
    if not (xml_text or '').strip():
        return xml_text
    if 'Id="LiftCoreSignature"' in xml_text:
        return xml_text

    signature_b64 = sign_invoice_hash(invoice_hash_b64, private_key_pem)
    cert_digest = certificate_hash_b64(certificate_pem)
    block = f'''  <ext:UBLExtensions>
    <ext:UBLExtension>
      <ext:ExtensionContent>
        <sig:UBLDocumentSignatures>
          <sac:SignatureInformation>
            <ds:Signature Id="LiftCoreSignature">
              <ds:SignedInfo>
                <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2006/12/xml-c14n11"/>
                <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256"/>
                <ds:Reference URI="">
                  <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                  <ds:DigestValue>{_esc(invoice_hash_b64)}</ds:DigestValue>
                </ds:Reference>
              </ds:SignedInfo>
              <ds:SignatureValue>{_esc(signature_b64)}</ds:SignatureValue>
              <ds:KeyInfo>
                <ds:X509Data>
                  <ds:X509Certificate>{_esc(_cert_body(certificate_pem))}</ds:X509Certificate>
                </ds:X509Data>
              </ds:KeyInfo>
              <ds:Object>
                <sbc:CertDigest>{_esc(cert_digest)}</sbc:CertDigest>
              </ds:Object>
            </ds:Signature>
          </sac:SignatureInformation>
        </sig:UBLDocumentSignatures>
      </ext:ExtensionContent>
    </ext:UBLExtension>
  </ext:UBLExtensions>
'''

    # أضف namespaces على جذر Invoice إن لزم
    out = xml_text
    if 'xmlns:ext=' not in out:
        out = re.sub(
            r'(<Invoice\b[^>]*)(>)',
            lambda m: m.group(1) + ' ' + _EXTENSION_NS + m.group(2),
            out,
            count=1,
        )
    # أدرج الكتلة بعد DocumentCurrencyCode أو بعد IssueTime
    anchor = re.search(r'</cbc:DocumentCurrencyCode>\s*', out)
    if not anchor:
        anchor = re.search(r'</cbc:IssueTime>\s*', out)
    if not anchor:
        return xml_text
    insert_at = anchor.end()
    return out[:insert_at] + block + out[insert_at:]


def _cert_body(pem: str) -> str:
    lines = []
    for line in (pem or '').splitlines():
        s = line.strip()
        if not s or s.startswith('-----'):
            continue
        lines.append(s)
    return ''.join(lines)


def _esc(text: str) -> str:
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )
