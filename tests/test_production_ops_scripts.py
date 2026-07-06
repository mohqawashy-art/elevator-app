"""سكربتات النواقص التشغيلية."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / 'deploy'


def test_production_ops_scripts_exist():
    for name in (
        'setup_production_ops.sh',
        'check_production_ops.sh',
    ):
        assert (DEPLOY / name).is_file(), f'missing deploy/{name}'


def test_setup_ops_references_backup_and_auto_update():
    text = (DEPLOY / 'setup_production_ops.sh').read_text(encoding='utf-8')
    assert 'install_backup_cron.sh' in text
    assert 'install_auto_update_cron.sh' in text
    assert 'check_production_ops.sh' in text


def test_check_ops_mentions_sentry_and_backup():
    text = (DEPLOY / 'check_production_ops.sh').read_text(encoding='utf-8')
    assert 'SENTRY_DSN' in text
    assert 'liftcore-daily-backup' in text


def test_install_sh_has_ops_commands():
    text = (DEPLOY / 'install.sh').read_text(encoding='utf-8')
    assert 'ops)' in text
    assert 'ops-check)' in text
