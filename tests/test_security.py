"""اختبارات الأمان — كلمات مرور، CSRF، rate limit."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from liftcore_security import (
    BANNED_PASSWORDS,
    check_login_rate_limit,
    clear_login_attempts,
    is_weak_password,
    password_policy_error,
    record_login_failure,
    validate_production_config,
    validate_upload_file,
)


class _FakeFile:
    def __init__(self, filename, size=100, content_type='image/png'):
        self.filename = filename
        self.content_type = content_type
        self.stream = self
        self._size = size
        self._pos = 0

    def seek(self, pos, whence=0):
        if whence == 2:
            self._pos = self._size
        else:
            self._pos = pos

    def tell(self):
        return self._pos


def test_weak_passwords_detected():
    assert is_weak_password('admin123')
    assert is_weak_password('123456')
    assert not is_weak_password('Str0ng!Pass')


def test_password_policy_min_length():
    err = password_policy_error('abc')
    assert err is not None
    assert password_policy_error('ValidPass1!') is None


def test_banned_list_not_empty():
    assert 'admin123' in BANNED_PASSWORDS


def test_login_rate_limit(monkeypatch):
    monkeypatch.setenv('LIFTCORE_HTTPS', '1')
    monkeypatch.setenv('LIFTCORE_RATE_LIMIT_STORE', 'memory')
    import liftcore_security as sec
    sec._db_store_disabled = False
    clear_login_attempts()
    for _ in range(5):
        record_login_failure()
    allowed, retry = check_login_rate_limit()
    assert allowed is False
    assert retry > 0
    clear_login_attempts()


def test_login_rate_limit_db_shared_across_checks(client, monkeypatch):
    """تخزين DB — نفس المفتاح يُحسب عبر استدعاءات منفصلة (محاكاة workers)."""
    monkeypatch.setenv('LIFTCORE_HTTPS', '1')
    monkeypatch.delenv('LIFTCORE_RATE_LIMIT_STORE', raising=False)
    import liftcore_security as sec
    from models import RateLimitEvent, db

    sec._db_store_disabled = False
    with client.application.app_context():
        RateLimitEvent.query.delete()
        db.session.commit()
        clear_login_attempts()
        for _ in range(5):
            record_login_failure()
        allowed, retry = check_login_rate_limit()
        assert allowed is False
        assert retry > 0
        assert RateLimitEvent.query.filter_by(scope='login').count() >= 5
        clear_login_attempts()
        assert RateLimitEvent.query.filter_by(scope='login').count() == 0


def test_upload_rejects_bad_ext():
    f = _FakeFile('virus.exe')
    ok, err = validate_upload_file(f, allowed_ext={'png', 'jpg'})
    assert ok is False
    assert err


def test_upload_rejects_oversize():
    f = _FakeFile('big.png', size=50 * 1024 * 1024)
    ok, err = validate_upload_file(f, allowed_ext={'png'})
    assert ok is False


def test_production_rejects_missing_or_weak_secret_key(monkeypatch):
    import pytest

    monkeypatch.setenv('LIFTCORE_HTTPS', '1')

    class _App:
        config = {'SECRET_KEY': 'liftcore-secret-2025'}

    with pytest.raises(RuntimeError):
        validate_production_config(_App())

    _App.config = {'SECRET_KEY': ''}
    with pytest.raises(RuntimeError):
        validate_production_config(_App())
