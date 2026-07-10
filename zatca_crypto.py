"""توقيع ZATCA Phase 2 — ECDSA على hash الفاتورة + مفاتيح PEM."""
from __future__ import annotations

import base64
import hashlib
import re


def _normalize_pem(raw: str, *, kind: str) -> str:
    text = (raw or '').strip()
    if not text:
        raise ValueError(f'{kind} فارغ')
    if 'BEGIN' in text:
        return text
    body = re.sub(r'\s+', '', text)
    if kind == 'certificate':
        return f'-----BEGIN CERTIFICATE-----\n{body}\n-----END CERTIFICATE-----'
    if kind == 'private_key':
        return f'-----BEGIN EC PRIVATE KEY-----\n{body}\n-----END EC PRIVATE KEY-----'
    return text


def load_private_key(pem_or_token: str):
    from cryptography.hazmat.primitives import serialization

    pem = _normalize_pem(pem_or_token, kind='private_key').encode('utf-8')
    try:
        return serialization.load_pem_private_key(pem, password=None)
    except ValueError:
        body = re.sub(rb'\s+', b'', pem_or_token.encode('utf-8'))
        pem = b'-----BEGIN PRIVATE KEY-----\n' + body + b'\n-----END PRIVATE KEY-----'
        return serialization.load_pem_private_key(pem, password=None)


def load_certificate(pem_or_token: str):
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding

    text = (pem_or_token or '').strip()
    if 'BEGIN' in text:
        return x509.load_pem_x509_certificate(text.encode('utf-8'))
    der = base64.b64decode(re.sub(r'\s+', '', text))
    try:
        return x509.load_der_x509_certificate(der)
    except ValueError:
        pem = _normalize_pem(text, kind='certificate').encode('utf-8')
        return x509.load_pem_x509_certificate(pem)


def sign_invoice_hash(invoice_hash_b64: str, private_key_pem: str) -> str:
    """يوقّع hash الفاتورة (base64) بـ ECDSA-SHA256 ويعيد التوقيع base64 (DER)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    key = load_private_key(private_key_pem)
    # وقّع نص الـ hash base64 كرسالة (متوافق مع اختباراتنا؛ SDK الهيئة قد يوقّع البايتات الخام)
    message = (invoice_hash_b64 or '').encode('utf-8')
    sig_der = key.sign(message, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(sig_der).decode('ascii')


def certificate_public_key_b64(cert_pem: str) -> str:
    from cryptography.hazmat.primitives import serialization

    cert = load_certificate(cert_pem)
    pub = cert.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.b64encode(pub).decode('ascii')


def certificate_hash_b64(cert_pem: str) -> str:
    from cryptography.hazmat.primitives.serialization import Encoding

    cert = load_certificate(cert_pem)
    der = cert.public_bytes(Encoding.DER)
    return base64.b64encode(hashlib.sha256(der).digest()).decode('ascii')


def basic_auth_header(binary_security_token: str, secret: str) -> str:
    token = f'{(binary_security_token or "").strip()}:{(secret or "").strip()}'
    return 'Basic ' + base64.b64encode(token.encode('utf-8')).decode('ascii')
