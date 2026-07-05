"""P2 J1 — تغطية ملف الترجمة EN."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANS = ROOT / 'static' / 'liftcore-translations.js'


def _parse_translations() -> dict[str, str]:
    text = TRANS.read_text(encoding='utf-8')
    pairs = re.findall(r"'((?:\\'|[^'])*)'\s*:\s*'((?:\\'|[^'])*)'", text)
    return {ar: en for ar, en in pairs}


def test_translations_file_exists():
    assert TRANS.is_file()


def test_all_arabic_keys_have_english():
    data = _parse_translations()
    assert len(data) >= 100
    missing = [k for k, v in data.items() if not (v or '').strip()]
    assert not missing, f'missing EN for: {missing[:10]}'


def test_parsed_translation_dict_is_usable():
    data = _parse_translations()
    # آخر تعريف يفوز عند التكرار في الملف
    assert len(data) >= 100
