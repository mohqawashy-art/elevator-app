"""تحقق من سكربتات النشر — وجود ومحتوى أساسي."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / 'deploy'


def test_deploy_scripts_exist():
    required = [
        'gcp_update.sh',
        'fix_502.sh',
        'recover_502_now.sh',
        'ensure_platform_env.sh',
        'check_platform_env.sh',
        'verify_deploy.sh',
        '_common.sh',
    ]
    for name in required:
        assert (DEPLOY / name).is_file(), f'missing deploy/{name}'


def test_common_sh_defines_venv_resolver():
    text = (DEPLOY / '_common.sh').read_text(encoding='utf-8')
    assert 'lc_resolve_venv' in text
    assert 'lc_pip_install_requirements' in text
    assert 'flask_migrate' in text


def test_gcp_update_uses_common_and_venv_resolver():
    text = (DEPLOY / 'gcp_update.sh').read_text(encoding='utf-8')
    assert '_common.sh' in text
    assert 'lc_resolve_venv' in text
    assert 'lc_pip_install_requirements' in text


def test_requirements_has_production_deps():
    req = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
    for pkg in ('Flask-Migrate', 'sentry-sdk', 'gunicorn', 'cryptography'):
        assert pkg.lower() in req.lower()
