#!/usr/bin/env python3
"""حذف وتصفير كل الأعطال لمستأجر محدّد (افتراضي: jama).

يحذف كل سجلات الأعطال مع تنظيف التبعيات بنفس منطق واجهة حذف العطل:
  - حذف روابط الفنيين (fault_technicians)
  - تفريغ fault_id من زيارات الصيانة (maintenance_visits)
  - تفريغ fault_id من فوترة القطع (parts_billing)
  - تفريغ fault_id من وارد واتساب (whatsapp_inbox)
بعد الحذف يعود ترقيم الأعطال تلقائياً إلى FA-00001.

  cd ~/liftcore/jama-elevator-app
  source .venv/bin/activate
  export DATABASE_URL="sqlite:///$PWD/instance/jama.db"   # أو: set -a; source /etc/liftcore/platform.env; set +a
  python scripts/delete_all_faults.py --slug jama --dry-run
  python scripts/delete_all_faults.py --slug jama --yes
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description='حذف وتصفير كل الأعطال لمستأجر')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL غير مضبوط — source /etc/liftcore/platform.env أولاً')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes للتأكيد أو --dry-run للمعاينة')
        return 2

    from flask import g
    from app import app
    from models import (
        Fault,
        FaultTechnician,
        MaintenanceVisit,
        Organization,
        PartsBilling,
        WhatsAppInbox,
        db,
    )
    from operations import next_code

    with app.app_context():
        slug = (args.slug or 'jama').strip().lower()
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
            return 1
        g.organization = org
        g.organization_id = org.id
        print(f'Tenant: {org.name} ({org.slug}) id={org.id}')

        faults = (
            Fault.query.filter_by(organization_id=org.id)
            .order_by(Fault.id)
            .all()
        )
        total = len(faults)
        if total == 0:
            print('لا توجد أعطال لهذا المستأجر — لا شيء للحذف.')
            return 0

        before_next = next_code(Fault, 'FA-', digits=5)
        print(f'إجمالي الأعطال: {total} — next_code قبل الحذف: {before_next}')
        for f in faults[:20]:
            print(f'  id={f.id} code={f.code} status={f.status} reported_at={f.reported_at}')
        if total > 20:
            print(f'  ... و {total - 20} أخرى')

        if args.dry_run:
            print('معاينة فقط — لم يُحذف شيء')
            return 0

        fault_ids = [f.id for f in faults]

        FaultTechnician.query.filter(
            FaultTechnician.fault_id.in_(fault_ids)
        ).delete(synchronize_session=False)
        MaintenanceVisit.query.filter(
            MaintenanceVisit.fault_id.in_(fault_ids)
        ).update({MaintenanceVisit.fault_id: None}, synchronize_session=False)
        PartsBilling.query.filter(
            PartsBilling.fault_id.in_(fault_ids)
        ).update({PartsBilling.fault_id: None}, synchronize_session=False)
        WhatsAppInbox.query.filter(
            WhatsAppInbox.fault_id.in_(fault_ids)
        ).update({WhatsAppInbox.fault_id: None}, synchronize_session=False)

        deleted = (
            Fault.query.filter(Fault.id.in_(fault_ids))
            .delete(synchronize_session=False)
        )
        db.session.commit()

        after_next = next_code(Fault, 'FA-', digits=5)
        print(f'حُذف {deleted} عطل — next_code بعد الحذف: {after_next}')
        print('تم الحذف والتصفير. عاد ترقيم الأعطال إلى البداية.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
