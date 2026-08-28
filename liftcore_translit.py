"""LiftCore — تحويل الأسماء العربية إلى لاتيني (Transliteration)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_CHAR_MAP = {
    'ا': 'a', 'أ': 'a', 'إ': 'i', 'آ': 'aa', 'ٱ': 'a',
    'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'h', 'خ': 'kh',
    'د': 'd', 'ذ': 'th', 'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh',
    'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': '', 'غ': 'gh',
    'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
    'ه': 'h', 'و': 'o', 'ؤ': 'o', 'ي': 'i', 'ى': 'a', 'ئ': 'i',
    'ة': 'a', 'ء': '', 'ـ': '',
    'َ': '', 'ُ': '', 'ِ': '', 'ّ': '', 'ْ': '', 'ً': '', 'ٌ': '', 'ٍ': '',
}

_DIGIT_MAP = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_TASHKEEL_RE = re.compile(r'[\u064B-\u065F\u0670\u0640]')
_ALEF_RE = re.compile('[أإآٱ]')


@lru_cache(maxsize=1)
def _load_dictionary() -> tuple[list[tuple[str, str]], dict[str, str]]:
    path = Path(__file__).resolve().parent / 'static' / 'translit-dictionary.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    phrases = [(p[0], p[1]) for p in data.get('phrases', [])]
    phrases.sort(key=lambda item: len(item[0]), reverse=True)
    words = {str(k): str(v) for k, v in (data.get('words') or {}).items()}
    return phrases, words


def _normalize_ar(text: str) -> str:
    text = _TASHKEEL_RE.sub('', text)
    text = _ALEF_RE.sub('ا', text)
    return text.translate(_DIGIT_MAP).strip()


def _title_word(word: str) -> str:
    if not word:
        return ''
    if '-' in word:
        return '-'.join(_title_word(part) for part in word.split('-'))
    return word[0].upper() + word[1:]


def _lookup_word(word: str, words: dict[str, str]) -> str | None:
    if word in words:
        mapped = words[word]
        if word.startswith('ال') and len(word) > 2 and not mapped.startswith('Al'):
            return f'Al-{mapped}'
        return mapped
    if word.startswith('ال') and len(word) > 2:
        stem = word[2:]
        if stem in words:
            mapped = words[stem]
            if mapped.startswith('Al'):
                return mapped
            return f'Al-{mapped}'
    return None


def _phonetic_word(word: str) -> str:
    if word.endswith('ية') and len(word) > 2:
        base = word[:-2]
        body = ''.join(_CHAR_MAP.get(ch, ch) for ch in base if ch in _CHAR_MAP or re.match(r'[\w]', ch))
        body = re.sub(r'y+', 'i', body)
        body = re.sub(r'aa+', 'a', body)
        return _title_word(f'{body}ia')

    out = []
    for ch in word:
        if ch in _CHAR_MAP:
            out.append(_CHAR_MAP[ch])
        elif ch in (' ', '-', '_', '.'):
            out.append(ch)
        elif re.match(r'[\w]', ch):
            out.append(ch)
    text = ''.join(out)
    text = re.sub(r'y+', 'i', text)
    text = re.sub(r'oo+', 'o', text)
    text = re.sub(r'aa+', 'a', text)
    text = text.strip('-')
    if not text:
        return ''
    return _title_word(text)


def _transliterate_word(word: str, words: dict[str, str]) -> str:
    word = _normalize_ar(word)
    if not word:
        return ''
    if re.fullmatch(r'[\w.\-]+', word, flags=re.ASCII):
        return word

    hit = _lookup_word(word, words)
    if hit:
        return hit

    if word.startswith('ال') and len(word) > 2:
        stem = word[2:]
        hit = _lookup_word(stem, words)
        if hit:
            if hit.startswith('Al'):
                return hit
            return f'Al-{hit}'
        mapped = _phonetic_word(stem)
        if mapped:
            return f'Al-{mapped}'
        return 'Al'

    return _phonetic_word(word)


def arabic_to_latin(text: str | None) -> str:
    if not text or not str(text).strip():
        return ''

    phrases, words = _load_dictionary()
    parts = _normalize_ar(str(text)).split()
    if not parts:
        return ''

    converted: list[str] = []
    i = 0
    while i < len(parts):
        matched = False
        for phrase_ar, phrase_en in phrases:
            phrase_parts = phrase_ar.split()
            if parts[i:i + len(phrase_parts)] == phrase_parts:
                converted.append(phrase_en)
                i += len(phrase_parts)
                matched = True
                break
        if matched:
            continue
        converted.append(_transliterate_word(parts[i], words))
        i += 1

    return ' '.join(converted)
