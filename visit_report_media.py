"""صور محضر الصيانة — تخزين ملفات بدل base64 داخل checklist_json."""

from __future__ import annotations

import base64
import os
import re
import uuid

DATA_URL_RE = re.compile(r'^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$', re.DOTALL)

EXT_BY_MIME = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/gif': 'gif',
}

MAX_PHOTO_BYTES = 8 * 1024 * 1024


def visit_upload_dir(root_path: str, visit_id: int) -> str:
    path = os.path.join(root_path, 'static', 'uploads', 'visits', str(int(visit_id)))
    os.makedirs(path, exist_ok=True)
    return path


def is_persisted_visit_photo_url(url: str) -> bool:
    u = (url or '').strip()
    return u.startswith('/static/uploads/visits/')


def persist_data_url_photo(root_path: str, visit_id: int, data_url: str) -> str:
    """حفظ data URL كملف — يُرجع مسار /static/uploads/visits/..."""
    data_url = (data_url or '').strip()
    if not data_url:
        return ''
    if is_persisted_visit_photo_url(data_url):
        return data_url
    if data_url.startswith('http://') or data_url.startswith('https://'):
        return data_url

    m = DATA_URL_RE.match(data_url)
    if not m:
        return ''
    mime, b64 = m.group(1), m.group(2)
    ext = EXT_BY_MIME.get(mime.lower(), 'jpg')
    try:
        raw = base64.b64decode(b64, validate=False)
    except (TypeError, ValueError):
        return ''
    if not raw or len(raw) > MAX_PHOTO_BYTES:
        raise ValueError('حجم الصورة كبير جداً')

    name = f'{uuid.uuid4().hex[:12]}.{ext}'
    folder = visit_upload_dir(root_path, visit_id)
    abs_path = os.path.join(folder, name)
    with open(abs_path, 'wb') as fh:
        fh.write(raw)
    return f'/static/uploads/visits/{int(visit_id)}/{name}'


def save_visit_report_photo_bytes(
    root_path: str,
    visit_id: int,
    raw: bytes,
    *,
    ext: str = 'jpg',
) -> str:
    ext = (ext or 'jpg').lower().lstrip('.')
    if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
        ext = 'jpg'
    if not raw or len(raw) > MAX_PHOTO_BYTES:
        raise ValueError('حجم الصورة كبير جداً')
    name = f'{uuid.uuid4().hex[:12]}.{ext}'
    folder = visit_upload_dir(root_path, visit_id)
    with open(os.path.join(folder, name), 'wb') as fh:
        fh.write(raw)
    return f'/static/uploads/visits/{int(visit_id)}/{name}'


def normalize_report_photos(root_path: str, visit_id: int, photos: list | None) -> list[dict[str, str]]:
    """توحيد قائمة الصور — data URL → ملف، مع captions."""
    out: list[dict[str, str]] = []
    for ph in photos or []:
        if not isinstance(ph, dict):
            continue
        url = persist_data_url_photo(root_path, visit_id, ph.get('url') or '')
        if not url:
            continue
        out.append({
            'url': url,
            'caption': (ph.get('caption') or '').strip(),
        })
    return out


def photos_need_migration(photos: list | None) -> bool:
    for ph in photos or []:
        if not isinstance(ph, dict):
            continue
        url = (ph.get('url') or '').strip()
        if url.startswith('data:'):
            return True
    return False
