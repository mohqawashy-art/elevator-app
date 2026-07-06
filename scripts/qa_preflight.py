#!/usr/bin/env python3
"""LiftCore QA preflight — شغّل قبل النشر أو بعد تغييرات كبيرة.

  python scripts/qa_preflight.py
  python scripts/qa_preflight.py --e2e
  python scripts/qa_preflight.py --url https://app.liftcoreapp.com
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd: list[str], *, env: dict | None = None) -> int:
    print(f'\n>> {" ".join(cmd)}')
    use_shell = os.name == 'nt' and cmd and cmd[0] in ('npm', 'npx')
    return subprocess.call(cmd, cwd=ROOT, env=env, shell=use_shell)


def check_remote_health(url: str) -> bool:
    health_url = url.rstrip('/') + '/api/health'
    print(f'\n>> GET {health_url}')
    try:
        with urllib.request.urlopen(health_url, timeout=15) as resp:
            body = resp.read().decode('utf-8', errors='replace')
        print(f'  {body[:300]}')
        ok = '"ok":true' in body.replace(' ', '').lower() or "'ok':true" in body.replace(' ', '').lower()
        if not ok:
            print('  FAIL: health not ok')
        return ok
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f'  FAIL: {exc}')
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description='LiftCore QA preflight')
    parser.add_argument('--e2e', action='store_true', help='تشغيل Playwright E2E')
    parser.add_argument('--url', help='فحص /api/health على إنتاج أو staging')
    args = parser.parse_args()

    failures = 0

    print('=' * 60)
    print('LiftCore QA Preflight')
    print('=' * 60)

    if run([sys.executable, 'scripts/security_audit.py']) != 0:
        failures += 1

    env = os.environ.copy()
    env['LIFTCORE_HTTPS'] = '1'
    env.setdefault('SECRET_KEY', 'qa-preflight-secret-key-48chars-minimum-xx')

  # production boot subprocess tests
    if run([sys.executable, '-m', 'pytest', 'tests/test_production_boot.py', '-q', '--tb=short']) != 0:
        failures += 1

    if run([sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=line']) != 0:
        failures += 1

    if args.e2e:
        e2e_env = os.environ.copy()
        e2e_env['CI'] = 'true'
        if run(['npm', 'run', 'test:e2e'], env=e2e_env) != 0:
            failures += 1

    if args.url:
        if not check_remote_health(args.url):
            failures += 1

    print('\n' + '=' * 60)
    if failures:
        print(f'PREFLIGHT FAILED ({failures} step(s))')
        return 1
    print('PREFLIGHT OK — جاهز للنشر')
    print('  تالي: bash deploy/recover_502_now.sh  (على السيرفر)')
    print('  أو:   bash deploy/verify_deploy.sh https://app.liftcoreapp.com')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
