"""LiftCore — تشفير ملفات التوقيع المحفوظة."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from hashlib import sha256

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None
    InvalidToken = Exception

_FALLBACK_MAGIC = b'LCX1'


def _derive_key(secret: str) -> bytes:
    return sha256((secret or 'liftcore').encode('utf-8')).digest()


def _fernet(secret: str):
    if not Fernet:
        return None
    key = base64.urlsafe_b64encode(_derive_key(secret))
    return Fernet(key)


def _fallback_encrypt(data: bytes, secret: str) -> bytes:
    key = _derive_key(secret)
    payload = bytearray(b ^ key[i % len(key)] for i, b in enumerate(data))
    sig = hmac.new(key, bytes(payload), hashlib.sha256).digest()
    return _FALLBACK_MAGIC + sig + bytes(payload)


def _fallback_decrypt(token: bytes, secret: str) -> bytes:
    if not token.startswith(_FALLBACK_MAGIC) or len(token) < len(_FALLBACK_MAGIC) + 32:
        raise ValueError('تعذّر فك تشفير التوقيع')
    key = _derive_key(secret)
    sig = token[len(_FALLBACK_MAGIC):len(_FALLBACK_MAGIC) + 32]
    payload = token[len(_FALLBACK_MAGIC) + 32:]
    expected = hmac.new(key, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError('تعذّر فك تشفير التوقيع')
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(payload))


def encrypt_bytes(data: bytes, secret: str) -> bytes:
    fernet = _fernet(secret)
    if fernet:
        return fernet.encrypt(data)
    return _fallback_encrypt(data, secret)


def decrypt_bytes(token: bytes, secret: str) -> bytes:
    if token.startswith(_FALLBACK_MAGIC):
        return _fallback_decrypt(token, secret)
    fernet = _fernet(secret)
    if not fernet:
        raise ValueError('تعذّر فك تشفير التوقيع')
    try:
        return fernet.decrypt(token)
    except InvalidToken as exc:
        raise ValueError('تعذّر فك تشفير التوقيع') from exc


def using_strong_crypto() -> bool:
    return Fernet is not None


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
