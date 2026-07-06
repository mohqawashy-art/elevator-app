#!/usr/bin/env python3
"""تحقق من النواقص التشغيلية — محلياً أو ضد إنتاج.

  python scripts/verify_production_ops.py
  python scripts/verify_production_ops.py --url https://app.liftcoreapp.com
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def fetch_health(url: str) -> dict:
    health_url = url.rstrip('/') + '/api/health'
    with urllib.request.urlopen(health_url, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))


def main() -> int:
    parser = argparse.ArgumentParser(description='LiftCore production ops verify')
    parser.add_argument('--url', default='https://app.liftcoreapp.com', help='Base URL')
    args = parser.parse_args()

    warns = 0
    print(f'==> GET {args.url}/api/health')
    try:
        health = fetch_health(args.url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f'FAIL: {exc}')
        return 1

    print(json.dumps(health, indent=2, ensure_ascii=False))

    if not health.get('ok'):
        print('FAIL: health not ok')
        return 1

    monitoring = health.get('monitoring') or {}
    if not monitoring.get('sentry_configured'):
        print('WARN: Sentry غير مضبوط (أضف SENTRY_DSN في platform.env على السيرفر)')
        warns += 1
    else:
        print('OK: Sentry configured')

    version = health.get('version', '')
    if version and version not in ('4a0a9d8-auth', 'unknown'):
        print(f'OK: version {version}')
    else:
        print(f'WARN: version قديم أو غير معروف: {version!r}')
        warns += 1

    print('')
    print('على السيرفر شغّل: bash deploy/setup_production_ops.sh')
    print('يدوياً: deploy/REGRESSION_CHECKLIST.txt')
    if warns:
        print(f'==> OK with {warns} warning(s)')
        return 0
    print('==> OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
