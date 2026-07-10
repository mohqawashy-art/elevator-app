#!/usr/bin/env python3
"""التجربة النهائية لـ LiftCore — فحوصات آلية + قائمة يدوية.

  # من جهازك أو السيرفر:
  python scripts/final_acceptance.py
  python scripts/final_acceptance.py --base https://liftcoreapp.com

يفحص: health للمنصة + app + jama، وsmoke جما، ثم يطبع خطوات التجربة اليدوية.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _get_json(url: str, timeout: int = 20) -> tuple[int, dict | None, str]:
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'LiftCore-FinalAcceptance/1.0', 'Accept': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            try:
                return resp.status, json.loads(raw), raw
            except json.JSONDecodeError:
                return resp.status, None, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace') if exc.fp else ''
        return exc.code, None, raw
    except (urllib.error.URLError, TimeoutError) as exc:
        return 0, None, str(exc)


def check_health(label: str, base: str) -> bool:
    url = base.rstrip('/') + '/api/health'
    print(f'\n==> [{label}] {url}')
    code, data, raw = _get_json(url)
    if code != 200 or not data:
        print(f'  FAIL HTTP {code}: {raw[:200]}')
        return False
    ok = bool(data.get('ok'))
    backend = data.get('database_backend')
    db = data.get('database')
    print(f'  ok={ok} database={db} backend={backend} version={data.get("version")}')
    if not ok or not db:
        print('  FAIL: health not healthy')
        return False
    if backend and backend != 'postgresql':
        print(f'  WARN: expected postgresql, got {backend}')
    return True


def print_manual() -> None:
    print(
        '''
============================================================
التجربة اليدوية النهائية (~20 دقيقة)
============================================================

أ) المنصة / التسجيل
  [ ] https://liftcoreapp.com — الصفحة التسويقية تفتح
  [ ] /signup — إنشاء مؤسسة تجريبية (أو تخطَّ إن وُجدت)
  [ ] بعد التسجيل: الدخول على {slug}.liftcoreapp.com

ب) tenant default — https://app.liftcoreapp.com  (أو default.*)
  [ ] دخول admin
  [ ] لوحة التحكم — البطاقات تعمل
  [ ] عملاء: إضافة عميل تجريبي وحفظ
  [ ] عقود: فتح القائمة
  [ ] زيارات صيانة: الصفحة تفتح
  [ ] فواتير: إصدار فاتورة ضريبية مبسطة → طباعة → ظهور QR إن وُجد رقم ضريبي
  [ ] إعدادات → الفوترة الإلكترونية: الصفحة تفتح
  [ ] إعدادات → الباقة: تظهر بدون 500 (Moyasar قد يكون معطّلاً)
  [ ] /field/login — صفحة الفني

ج) tenant جما — https://jama.liftcoreapp.com
  [ ] دخول admin / admin123 (أو بياناتك)
  [ ] عملاء / عقود / زيارات / أعطال / فواتير تفتح
  [ ] عزل: لا تظهر بيانات مؤسسة أخرى

د) أمان سريع
  [ ] حساب viewer: لا أزرار إضافة؛ محاولة POST تُرفض
  [ ] جلسة منتهية → إعادة توجيه لـ /login

هـ) تشغيلي
  [ ] تذكيرات: python scripts/send_contract_reminders.py --days-ahead 3
  [ ] نسخة احتياطية موجودة / cron backup يعمل

عند اكتمال كل البنود: التجربة النهائية ناجحة.
'''
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='LiftCore final acceptance')
    parser.add_argument('--base', default='https://liftcoreapp.com', help='Marketing / apex domain')
    parser.add_argument('--app-url', default='https://app.liftcoreapp.com')
    parser.add_argument('--jama-url', default='https://jama.liftcoreapp.com')
    parser.add_argument('--skip-manual', action='store_true', help='Automated checks only')
    args = parser.parse_args()

    print('=' * 60)
    print('LiftCore — التجربة النهائية (آلي)')
    print('=' * 60)

    fails = 0
    if not check_health('apex', args.base):
        # apex قد يوجّه لصفحة تسويق بدون /api/health — لا نفشل بقوة
        print('  WARN: apex health failed (قد يكون طبيعياً إن لم يُوجَّه للـ app)')
    if not check_health('app', args.app_url):
        fails += 1
    if not check_health('jama', args.jama_url):
        fails += 1

    smoke = ROOT / 'scripts' / 'verify_jama_smoke.py'
    print(f'\n==> Jama smoke script')
    rc = subprocess.call([sys.executable, str(smoke), '--url', args.jama_url], cwd=str(ROOT))
    if rc != 0:
        fails += 1

    ops = ROOT / 'scripts' / 'verify_production_ops.py'
    print(f'\n==> Production ops verify')
    rc = subprocess.call(
        [sys.executable, str(ops), '--url', args.app_url, '--jama-url', args.jama_url],
        cwd=str(ROOT),
    )
    if rc != 0:
        fails += 1

    if not args.skip_manual:
        print_manual()

    print('=' * 60)
    if fails:
        print(f'النتيجة الآلية: FAIL ({fails} فحص/فحوصات)')
        return 1
    print('النتيجة الآلية: OK — أكمل القائمة اليدوية أعلاه')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
