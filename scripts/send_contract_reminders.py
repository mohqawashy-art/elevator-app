#!/usr/bin/env python3
"""تذكيرات عقود يومية — يولّد روابط wa.me (بدون WhatsApp Business API بعد).

  # كل المؤسسات، تذكيرات اليوم + 3 أيام قادمة:
  python scripts/send_contract_reminders.py --days-ahead 3

  # مؤسسة واحدة + كتابة ملف:
  python scripts/send_contract_reminders.py --slug jama --out /tmp/reminders.json

يتطلّب DATABASE_URL (أو platform.env عبر تحميل التطبيق).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description='LiftCore contract reminder digest')
    parser.add_argument('--slug', default='', help='Organization slug (default: all active)')
    parser.add_argument('--days-ahead', type=int, default=0, help='Include reminders up to N days ahead')
    parser.add_argument('--date', default='', help='Override today YYYY-MM-DD')
    parser.add_argument('--out', default='', help='Write JSON digest path')
    args = parser.parse_args()

    # تحميل التطبيق بعد ضبط المسار
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app import app
    from flask import g
    from models import Organization, Settings
    from operations import contract_reminder_rows

    on_date = date.fromisoformat(args.date) if args.date else date.today()
    digest = {'date': on_date.isoformat(), 'days_ahead': args.days_ahead, 'organizations': []}

    with app.app_context():
        q = Organization.query
        if args.slug:
            q = q.filter_by(slug=args.slug.strip())
        else:
            q = q.filter(Organization.status.in_(('active', 'trialing', 'ok', None, '')))
        orgs = q.order_by(Organization.id.asc()).all()
        if not orgs:
            print('No organizations found', file=sys.stderr)
            return 1

        total = 0
        for org in orgs:
            g.organization = org
            g.organization_id = org.id
            settings = Settings.query.filter_by(organization_id=org.id).first()
            company = (settings.company_name if settings else None) or org.name or org.slug
            rows = contract_reminder_rows(
                on_date=on_date,
                days_ahead=args.days_ahead,
                company_name=company or '',
            )
            digest['organizations'].append({
                'slug': org.slug,
                'name': org.name,
                'count': len(rows),
                'reminders': rows,
            })
            total += len(rows)
            print(f'[{org.slug}] {len(rows)} reminder(s)')
            for r in rows:
                link = r.get('whatsapp_url') or '(no phone)'
                print(f"  - {r.get('code')} {r.get('customer')} {r.get('reminder_date')} → {link[:80]}")

        digest['total'] = total

    if args.out:
        Path(args.out).write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Wrote {args.out}')

    print(f'Total: {total}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
