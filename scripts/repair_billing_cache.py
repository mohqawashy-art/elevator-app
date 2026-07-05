#!/usr/bin/env python3
"""إصلاح كاش الفوترة — عقود / فواتير / قطع (G7)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from app import app, db  # noqa: E402
from billing_consistency import audit_billing_consistency, repair_billing_consistency  # noqa: E402


def main() -> int:
    dry = '--dry-run' in sys.argv or '-n' in sys.argv
    with app.app_context():
        before = audit_billing_consistency()
        print(f'Issues before: {before["issue_count"]}')
        if dry:
            for row in before.get('issues', [])[:20]:
                print(f'  {row["entity"]} {row.get("code") or row["id"]}: '
                      f'stored={row["stored"]} computed={row["computed"]}')
            return 0
        result = repair_billing_consistency(commit=True)
        db.session.commit()
        print('Repair:', result)
        after = audit_billing_consistency()
        print(f'Issues after: {after["issue_count"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
