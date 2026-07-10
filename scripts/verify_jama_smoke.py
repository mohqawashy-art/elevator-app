#!/usr/bin/env python3
"""Smoke HTTP لـ tenant جما — بدون تسجيل دخول كامل.

  python scripts/verify_jama_smoke.py
  python scripts/verify_jama_smoke.py --url https://jama.liftcoreapp.com
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _get(url: str, *, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'LiftCore-JamaSmoke/1.0', 'Accept': 'text/html,application/json'},
        method='GET',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace') if exc.fp else ''
        return exc.code, body


def main() -> int:
    parser = argparse.ArgumentParser(description='LiftCore Jama tenant smoke')
    parser.add_argument('--url', default='https://jama.liftcoreapp.com', help='Jama base URL')
    args = parser.parse_args()
    base = args.url.rstrip('/')
    fails = 0

    print(f'==> Jama smoke: {base}')

    code, body = _get(f'{base}/api/health')
    if code != 200:
        print(f'FAIL: /api/health HTTP {code}')
        fails += 1
    else:
        try:
            health = json.loads(body)
        except json.JSONDecodeError:
            print('FAIL: /api/health not JSON')
            fails += 1
            health = {}
        else:
            if not health.get('ok'):
                print('FAIL: health.ok is false')
                fails += 1
            else:
                print(f"OK: health ok backend={health.get('database_backend')}")

    code, body = _get(f'{base}/login')
    if code != 200:
        print(f'FAIL: /login HTTP {code}')
        fails += 1
    elif 'password' not in body.lower() and 'كلمة' not in body and 'login' not in body.lower():
        print('WARN: /login 200 لكن المحتوى غير متوقع')
    else:
        print('OK: /login')

    # صفحات محمية — يُقبل 302 إلى login أو 401؛ يُرفض 500/404
    for path in ('/dashboard', '/clients', '/contracts', '/invoices', '/settings'):
        code, _ = _get(f'{base}{path}')
        if code >= 500:
            print(f'FAIL: {path} HTTP {code}')
            fails += 1
        elif code == 404:
            print(f'FAIL: {path} HTTP 404 (tenant/route؟)')
            fails += 1
        else:
            print(f'OK: {path} HTTP {code}')

    if fails:
        print(f'==> FAIL ({fails})')
        return 1
    print('==> OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
