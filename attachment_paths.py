"""تخزين عدة مسارات مرفقات في عمود واحد (متوافق مع المسار المفرد)."""

from __future__ import annotations

import json
import os

MULTI_ATTACH_PREFIX = 'JSON:'


def parse_attachment_paths(raw: str | None) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    s = str(raw).strip()
    if s.startswith(MULTI_ATTACH_PREFIX):
        try:
            data = json.loads(s[len(MULTI_ATTACH_PREFIX):])
            if isinstance(data, list):
                out = []
                for p in data:
                    text = str(p or '').strip()
                    if text:
                        out.append(text)
                return out
        except (json.JSONDecodeError, TypeError, ValueError):
            return []
        return []
    return [s]


def serialize_attachment_paths(paths: list[str] | None) -> str | None:
    clean = []
    seen = set()
    for p in paths or []:
        text = str(p or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        clean.append(text)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    return MULTI_ATTACH_PREFIX + json.dumps(clean, ensure_ascii=False)


def attachment_has(raw: str | None) -> bool:
    return bool(parse_attachment_paths(raw))


def attachment_primary(raw: str | None) -> str | None:
    paths = parse_attachment_paths(raw)
    return paths[0] if paths else None


def attachment_items(
    raw: str | None,
    url_fn,
    *,
    name_fn=None,
) -> list[dict]:
    items = []
    for idx, path in enumerate(parse_attachment_paths(raw)):
        base = os.path.basename(path.replace('\\', '/'))
        name = name_fn(path) if name_fn else base
        items.append({
            'index': idx,
            'path': path,
            'url': url_fn(path) if path else '',
            'name': name or base or 'مستند',
        })
    return items


def delete_attachment_file(app_root: str, relative_path: str) -> None:
    if not relative_path:
        return
    full = os.path.join(app_root, 'static', relative_path.replace('/', os.sep))
    if os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass
