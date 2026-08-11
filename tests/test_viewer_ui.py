"""P2 I6 — viewer يخفي أزرار التعديل."""
from __future__ import annotations

import re

from tests.conftest import login_as


def test_viewer_clients_page_hides_add_button(client):
    login_as(client, 'viewer')
    r = client.get('/clients')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'liftcore-viewer-ui.js' in html
    m = re.search(r'__LC_CAN_WRITE\s*=\s*(true|false)', html)
    assert m and m.group(1) == 'false'


def test_viewer_contracts_page_loads(client):
    login_as(client, 'viewer')
    assert client.get('/contracts', follow_redirects=True).status_code == 200
