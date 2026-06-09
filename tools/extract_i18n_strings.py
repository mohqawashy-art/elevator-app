"""Extract Arabic UI strings from templates for i18n dictionary."""
import re
import pathlib

root = pathlib.Path(__file__).resolve().parents[1] / 'templates'
strings = set()
AR = re.compile(r'[\u0600-\u06FF]')

for p in root.rglob('*.html'):
    t = p.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'placeholder="([^"]+)"', t):
        if AR.search(m.group(1)):
            strings.add(m.group(1))
    for m in re.finditer(r'>([^<{}][^<{}]*)<', t):
        s = m.group(1).strip()
        if AR.search(s) and len(s) < 120 and '{%' not in s and '{{' not in s:
            strings.add(s)
    for m in re.finditer(r'<option[^>]*>([^<]+)</option>', t):
        s = m.group(1).strip()
        if AR.search(s):
            strings.add(s)

for s in sorted(strings, key=len):
    if len(s) > 1:
        print(s)
