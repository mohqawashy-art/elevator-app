"""أيقونة دعم المنصة داخل تطبيق المكتب."""
from tests.conftest import login_as


def test_support_widget_on_dashboard(client, monkeypatch):
    monkeypatch.setenv('LIFTCORE_SUPPORT_EMAIL', 'info@liftcoreapp.com')
    monkeypatch.setenv('LIFTCORE_SUPPORT_WHATSAPP', '0555076078')
    login_as(client, 'admin')
    r = client.get('/dashboard')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'lc-support' in html
    assert 'liftcore-support.css' in html
    assert 'wa.me/' in html
    assert 'mailto:info@liftcoreapp.com' in html
    assert 'واتساب' in html or 'WhatsApp' in html


def test_support_widget_email_only_when_whatsapp_disabled(client, monkeypatch):
    monkeypatch.setenv('LIFTCORE_SUPPORT_EMAIL', 'help@liftcoreapp.com')
    monkeypatch.setenv('LIFTCORE_SUPPORT_WHATSAPP', '')
    login_as(client, 'manager')
    html = client.get('/dashboard').get_data(as_text=True)
    assert 'lc-support' in html
    assert 'mailto:help@liftcoreapp.com' in html
    assert 'wa.me/' not in html


def test_support_widget_uses_default_whatsapp(client, monkeypatch):
    monkeypatch.setenv('LIFTCORE_SUPPORT_EMAIL', 'info@liftcoreapp.com')
    monkeypatch.delenv('LIFTCORE_SUPPORT_WHATSAPP', raising=False)
    login_as(client, 'admin')
    html = client.get('/dashboard').get_data(as_text=True)
    assert 'wa.me/966566299626' in html
