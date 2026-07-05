"""P0-D3 — كل ملف static مُشار إليه في liftcore_head يجب أن يكون موجوداً (لا 404 في Console)."""
from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD = os.path.join(ROOT, 'templates', 'partials', 'liftcore_head.html')
STATIC = os.path.join(ROOT, 'static')


def _static_refs_from_head() -> list[str]:
    text = open(HEAD, encoding='utf-8').read()
    # url_for('static', filename='liftcore-shell.js')
    refs = re.findall(r"filename='([^']+)'", text)
    return sorted(set(refs))


def test_liftcore_head_static_files_exist():
    missing = []
    for name in _static_refs_from_head():
        path = os.path.join(STATIC, name.replace('/', os.sep))
        if not os.path.isfile(path):
            missing.append(name)
    assert not missing, f'Missing static files referenced in liftcore_head: {missing}'


def test_report_parts_template_exists():
    path = os.path.join(ROOT, 'templates', 'report-parts.html')
    assert os.path.isfile(path), 'report-parts.html required by /reports/parts-billing'
