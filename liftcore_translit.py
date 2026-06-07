"""LiftCore — تحويل الأسماء العربية إلى لاتيني (Transliteration)."""

from __future__ import annotations

import re

_CHAR_MAP = {
    'ا': 'a', 'أ': 'a', 'إ': 'i', 'آ': 'aa', 'ٱ': 'a',
    'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'h', 'خ': 'kh',
    'د': 'd', 'ذ': 'th', 'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh',
    'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh',
    'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
    'ه': 'h', 'و': 'w', 'ؤ': 'u', 'ي': 'y', 'ى': 'a', 'ئ': 'e',
    'ة': 'h', 'ء': '', 'ـ': '',
    'َ': '', 'ُ': '', 'ِ': '', 'ّ': '', 'ْ': '', 'ً': '', 'ٌ': '', 'ٍ': '',
}

_DIGIT_MAP = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def _transliterate_word(word: str) -> str:
    word = word.translate(_DIGIT_MAP).strip()
    if not word:
        return ''
    if re.fullmatch(r'[\w.\-]+', word, flags=re.ASCII):
        return word

    prefix = ''
    if word.startswith('ال') and len(word) > 2:
        prefix = 'Al-'
        word = word[2:]
    elif word.startswith('ال'):
        return 'Al'

    out = []
    for ch in word:
        if ch in _CHAR_MAP:
            out.append(_CHAR_MAP[ch])
        elif ch in (' ', '-', '_', '.'):
            out.append(ch)
        elif re.match(r'[\w]', ch, flags=re.ASCII):
            out.append(ch)
    text = ''.join(out).strip('-')
    if not text:
        return prefix.rstrip('-')
    return prefix + text[0].upper() + text[1:]


def arabic_to_latin(text: str | None) -> str:
    if not text or not str(text).strip():
        return ''
    parts = re.split(r'(\s+)', str(text).strip())
    converted = []
    for part in parts:
        if not part.strip():
            converted.append(part)
            continue
        converted.append(_transliterate_word(part))
    result = ''.join(converted)
    result = re.sub(r'\s+', ' ', result).strip()
    return result
