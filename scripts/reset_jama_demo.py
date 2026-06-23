#!/usr/bin/env python3
"""
إفراغ قاعدة جما وتحميل سيناريو 10 عملاء (تجربة كاملة للبرنامج).

محلياً:
  python scripts/reset_jama_demo.py

على سيرفر جما:
  cd ~/liftcore/jama-elevator-app
  export DATABASE_URL="sqlite:////home/info/liftcore/jama-elevator-app/instance/jama.db"
  python3 scripts/reset_jama_demo.py
  sudo systemctl restart liftcore-jama
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from seed_data import reset_jama_demo


def main() -> int:
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url:
        print(f'DATABASE_URL = {db_url}')
    else:
        print('DATABASE_URL غير مضبوط — سيُستخدم المسار الافتراضي للتطبيق')
    try:
        ok = reset_jama_demo()
        return 0 if ok else 1
    except Exception as exc:
        print(f'فشل: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
