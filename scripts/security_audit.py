#!/usr/bin/env py
"""فحص أمني سريع — يُشغَّل قبل النشر: py scripts/security_audit.py"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILURES: list[str] = []
WARNINGS: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)


def warn(msg: str) -> None:
    WARNINGS.append(msg)


def check_secret_key() -> None:
    from liftcore_security import DEFAULT_SECRET_KEYS, is_production_env
    from app import app
    key = (app.config.get('SECRET_KEY') or '').strip()
    if not key:
        fail('SECRET_KEY فارغ')
    elif key in DEFAULT_SECRET_KEYS:
        if is_production_env():
            fail('SECRET_KEY افتراضي في بيئة إنتاج (LIFTCORE_HTTPS=1)')
        else:
            warn('SECRET_KEY افتراضي — عيّنه قبل الإنتاج')


def check_delete_routes() -> None:
    app_py = os.path.join(ROOT, 'app.py')
    text = open(app_py, encoding='utf-8').read()
    for m in re.finditer(
        r"@app\.route\('([^']*)/delete[^']*'.*?\)\s*\ndef (\w+)\([^)]*\):",
        text,
        re.DOTALL,
    ):
        route, func_name = m.group(1), m.group(2)
        start = m.end()
        next_def = re.search(r'\n@app\.route|\ndef _|\n# =+', text[start:])
        end = start + (next_def.start() if next_def else 800)
        body = text[start:end]
        if 'enforce_admin_delete' not in body:
            fail(f'مسار حذف بدون enforce_admin_delete: {route} ({func_name})')


def check_rbac_module() -> None:
    path = os.path.join(ROOT, 'liftcore_rbac.py')
    if not os.path.isfile(path):
        fail('liftcore_rbac.py غير موجود')
        return
    text = open(path, encoding='utf-8').read()
    if 'ROLE_VIEWER' not in text or 'check_rbac' not in text:
        fail('liftcore_rbac.py ناقص')


def check_csrf_js() -> None:
    path = os.path.join(ROOT, 'static', 'liftcore-csrf.js')
    if not os.path.isfile(path):
        fail('liftcore-csrf.js غير موجود')


def check_audit_model() -> None:
    from models import AuditLog
    if not AuditLog.__tablename__:
        fail('AuditLog model غير صالح')


def main() -> int:
    os.chdir(ROOT)
    print('LiftCore Security Audit')
    print('=' * 40)
    check_rbac_module()
    check_csrf_js()
    check_audit_model()
    check_secret_key()
    check_delete_routes()

    for w in WARNINGS:
        print(f'  WARN: {w}')
    for f in FAILURES:
        print(f'  FAIL: {f}')

    if FAILURES:
        print(f'\n{len(FAILURES)} failure(s) — أصلح قبل النشر')
        return 1
    print(f'\nOK — {len(WARNINGS)} warning(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
