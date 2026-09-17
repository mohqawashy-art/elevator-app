"""عرض المرفقات — صفحة view/upload مع زر إغلاق."""
from __future__ import annotations

import os

from app import app, upload_url, upload_view_url
from tests.conftest import login_as


def test_upload_view_url_for_pdf():
    url = upload_view_url('uploads/financial_proofs/revenues/1/proof.pdf')
    assert '/view/upload/financial_proofs/revenues/1/proof.pdf' in url


def test_upload_view_url_for_non_viewable():
    url = upload_view_url('uploads/data/file.docx')
    assert url.startswith('/static/uploads/')


def test_view_upload_page_has_close_button(client, tmp_path):
    login_as(client, 'admin')
    rel = 'uploads/financial_proofs/revenues/99/sample.pdf'
    full = os.path.join(app.root_path, 'static', rel.replace('/', os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'wb') as fh:
        fh.write(b'%PDF-1.4 test')

    try:
        r = client.get('/view/upload/financial_proofs/revenues/99/sample.pdf')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'إغلاق' in html
        assert upload_url(rel) in html
    finally:
        if os.path.isfile(full):
            os.remove(full)
