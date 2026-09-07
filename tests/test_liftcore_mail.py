"""اختبارات بريد المنصة — محتوى الدعوة وHTML."""
import json
from unittest.mock import MagicMock, patch

from liftcore_mail import _plain_to_html, send_onboarding_invite_email


def test_plain_to_html_rtl_and_links():
    html_out = _plain_to_html('مرحباً\nhttps://liftcoreapp.com/onboard/abc')
    assert 'dir="rtl"' in html_out
    assert 'charset="utf-8"' in html_out
    assert 'href="https://liftcoreapp.com/onboard/abc"' in html_out
    assert 'مرحباً' in html_out


def test_invite_email_requires_url():
    result = send_onboarding_invite_email(
        to_email='client@example.com',
        contact_name='عميل',
        invite_url='',
        plan='basic',
        days=7,
    )
    assert result['ok'] is False
    assert result['reason'] == 'empty_invite_url'


def test_invite_email_payload_includes_html(monkeypatch):
    monkeypatch.setenv('MAIL_API_KEY', 're_test_key')
    captured = {}

    def fake_urlopen(req, timeout=15):
        captured['payload'] = json.loads(req.data.decode('utf-8'))
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch('liftcore_mail.urllib.request.urlopen', fake_urlopen):
        result = send_onboarding_invite_email(
            to_email='client@example.com',
            contact_name='أحمد',
            invite_url='https://liftcoreapp.com/onboard/token123',
            plan='basic',
            days=14,
        )

    assert result['ok'] is True
    payload = captured['payload']
    assert payload['subject']
    assert payload['text'].strip()
    assert 'أحمد' in payload['text']
    assert 'https://liftcoreapp.com/onboard/token123' in payload['text']
    assert payload['html'].strip()
    assert 'dir="rtl"' in payload['html']
    assert 'https://liftcoreapp.com/onboard/token123' in payload['html']
    assert 'إكمال بيانات الشركة' in payload['html']
    assert 'أساسي' in payload['html']
