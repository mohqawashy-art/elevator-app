"""صفحة النماذج في المكتب."""
from __future__ import annotations

from tests.conftest import ensure_test_organization, login_as


def test_office_forms_page_lists_catalog(client):
    with client.application.app_context():
        ensure_test_organization()
    login_as(client, 'admin')
    r = client.get('/forms')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'النماذج' in html
    assert 'محضر صيانة مصعد' in html
    assert 'نموذج فارغ' in html


def test_office_form_blank_maintenance(client):
    with client.application.app_context():
        ensure_test_organization()
    login_as(client, 'admin')
    r = client.get('/forms/blank/maintenance-checklist')
    assert r.status_code == 200
    assert 'محضر صيانة مصعد' in r.get_data(as_text=True)
