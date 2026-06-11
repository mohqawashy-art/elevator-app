"""LiftCore — تشفير ملفات التوقيع المحفوظة."""

from __future__ import annotations

import base64
import os
from hashlib import sha256

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None
    InvalidToken = Exception


def _fernet(secret: str):
    if not Fernet:
        raise RuntimeError('حزمة cryptography غير مثبتة على السيرفر')
    key = base64.urlsafe_b64encode(sha256((secret or 'liftcore').encode('utf-8')).digest())
    return Fernet(key)


def encrypt_bytes(data: bytes, secret: str) -> bytes:
    return _fernet(secret).encrypt(data)


def decrypt_bytes(token: bytes, secret: str) -> bytes:
    try:
        return _fernet(secret).decrypt(token)
    except InvalidToken as exc:
        raise ValueError('تعذّر فك تشفير التوقيع') from exc


def _image_mime(raw: bytes) -> str:
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if raw[:3] == b'\xff\xd8\xff':
        return 'jpeg'
    if raw[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    if len(raw) >= 12 and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'webp'
    return 'png'


def image_data_url(raw: bytes) -> str:
    mime = _image_mime(raw)
    b64 = base64.b64encode(raw).decode('ascii')
    return f'data:image/{mime};base64,{b64}'


def signatures_root(app_root: str) -> str:
    path = os.path.join(app_root, 'uploads', 'signatures')
    os.makedirs(path, exist_ok=True)
    return path


def encrypted_signature_path(signatory_id: int) -> str:
    return f'uploads/signatures/{signatory_id}.enc'


def save_encrypted_signature(app_root: str, secret: str, signatory_id: int, raw: bytes) -> str:
    folder = signatures_root(app_root)
    rel = encrypted_signature_path(signatory_id)
    abs_path = os.path.join(app_root, rel.replace('/', os.sep))
    with open(abs_path, 'wb') as fh:
        fh.write(encrypt_bytes(raw, secret))
    return rel


def load_encrypted_signature(app_root: str, secret: str, relative_path: str) -> bytes:
    abs_path = os.path.join(app_root, relative_path.replace('/', os.sep))
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(relative_path)
    with open(abs_path, 'rb') as fh:
        return decrypt_bytes(fh.read(), secret)
