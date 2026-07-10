"""اختبارات تشغيل إنتاج — محاكاة LIFTCORE_HTTPS + SECRET_KEY."""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _boot_subprocess(secret_key: str, *, https: str = '1') -> subprocess.CompletedProcess[str]:
    code = f"""
import os
os.environ['LIFTCORE_HTTPS'] = {https!r}
os.environ['SECRET_KEY'] = {secret_key!r}
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from app import app
c = app.test_client()
with app.app_context():
    from models import db
    db.create_all()
r = c.get('/api/health')
print('STATUS', r.status_code)
print('BODY', r.get_json())
"""
    return subprocess.run(
        [sys.executable, '-c', code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        stdin=subprocess.DEVNULL,
    )


def test_production_health_ok_with_strong_secret():
    proc = _boot_subprocess('qa-production-secret-key-min-32-chars')
    assert proc.returncode == 0, (proc.stderr or '') + (proc.stdout or '')
    assert 'STATUS 200' in proc.stdout
    assert "'ok': True" in proc.stdout or '"ok": True' in proc.stdout


def test_production_rejects_weak_secret_subprocess():
    proc = _boot_subprocess('liftcore-secret-2025')
    assert proc.returncode != 0
    assert 'SECRET_KEY' in (proc.stderr + proc.stdout)


def test_production_rejects_missing_secret_subprocess():
    """بدون SECRET_KEY في الإنتاج — فشل فوري بلا fallback."""
    code = """
import os
os.environ['LIFTCORE_HTTPS'] = '1'
# سلسلة فارغة تمنع .env من ملء المفتاح (override فقط إن غاب المفتاح)
os.environ['SECRET_KEY'] = ''
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from app import app  # noqa: F401
"""
    proc = subprocess.run(
        [sys.executable, '-c', code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        stdin=subprocess.DEVNULL,
    )
    assert proc.returncode != 0
    assert 'SECRET_KEY' in (proc.stderr + proc.stdout)


def test_flask_migrate_importable():
    import flask_migrate  # noqa: F401


def test_inprocess_health(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('database') is True
