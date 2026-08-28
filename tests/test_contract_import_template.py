"""اختبارات نموذج استيراد العقود."""
from __future__ import annotations

import io
import re
import zipfile

from tests.conftest import login_as


def _xlsx_rows(content: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        xml = zf.read('xl/worksheets/sheet1.xml').decode('utf-8')
    cells = re.findall(r'<t>([^<]*)</t>', xml)
    if not cells:
        return []
    width = len([c for c in cells if cells.index(c) < 20])  # fallback
    # headers row is first 13 columns in our template
    width = 13
    rows = []
    for i in range(0, len(cells), width):
        rows.append(cells[i:i + width])
    return rows


def test_contracts_import_template_ar(client):
    login_as(client, 'admin')
    r = client.get('/contracts/template?lang=ar')
    assert r.status_code == 200
    assert 'spreadsheetml' in (r.headers.get('Content-Type') or '')
    rows = _xlsx_rows(r.data)
    assert rows[0][0] == 'كود العميل'
    assert 'نوع العقد' in rows[0]


def test_contracts_import_template_en(client):
    login_as(client, 'admin')
    r = client.get('/contracts/template?lang=en')
    assert r.status_code == 200
    rows = _xlsx_rows(r.data)
    assert rows[0][0] == 'Client Code'
    assert 'Contract Type' in rows[0]
    assert len(rows) >= 2
    assert rows[1][2] == 'Maintenance Contract'
