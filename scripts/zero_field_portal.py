#!/usr/bin/env python3
"""تصفير بوابة الفني — إغلاق الأعطال المفتوحة وإلغاء الزيارات النشطة وحذف زيارات نوع «عطل».

الاستخدام (السيرفر):
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/zero_field_portal.py --slug jama --dry-run
  python scripts/zero_field_portal.py --slug jama --yes

محلياً:
  python scripts/zero_field_portal.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ZERO_NOTE = 'تصفير بوابة الفني للاختبار'


def zero_field_portal(*, org_id: int | None = None, dry_run: bool = False) -> dict:
    from models import Fault, MaintenanceVisit, db
    from operations import (
        FAULT_OPEN,
        VISIT_ACTIVE,
        is_fault_visit_type,
        repair_field_portal_stale,
    )
    from tenant_scope import tenant_query

    stats = {
        'faults_closed': 0,
        'visits_cancelled': 0,
        'fault_visits_deleted': 0,
        'repair': {},
    }

    fault_q = tenant_query(Fault).filter(Fault.status.in_(FAULT_OPEN))
    visit_q = tenant_query(MaintenanceVisit).filter(MaintenanceVisit.status.in_(VISIT_ACTIVE))
    if org_id:
        fault_q = fault_q.filter(Fault.organization_id == org_id)
        visit_q = visit_q.filter(MaintenanceVisit.organization_id == org_id)

    open_faults = fault_q.all()
    active_visits = visit_q.all()
    fault_visits = [v for v in active_visits if is_fault_visit_type(v.visit_type)]
    maintenance_visits = [v for v in active_visits if not is_fault_visit_type(v.visit_type)]

    # زيارات «عطل» قديمة غير نشطة لكنها تظهر إن أُعيدت لليوم — احذف كل زيارة نوع عطل
    all_fault_type_visits = [
        v for v in tenant_query(MaintenanceVisit).all()
        if is_fault_visit_type(v.visit_type) and (not org_id or v.organization_id == org_id)
    ]

    stats['faults_closed'] = len(open_faults)
    stats['visits_cancelled'] = len(maintenance_visits)
    stats['fault_visits_deleted'] = len(all_fault_type_visits)

    if dry_run:
        return stats

    now = datetime.utcnow()
    for f in open_faults:
        f.status = 'تم الاصلاح'
        f.resolution = (f.resolution or '').strip() or ZERO_NOTE
        f.resolved_at = f.resolved_at or now

    for v in maintenance_visits:
        v.status = 'ملغاة'
        v.observations = ((v.observations or '').strip() + f'\n[{ZERO_NOTE}]').strip()

    for v in all_fault_type_visits:
        for fault in tenant_query(Fault).filter_by(visit_id=v.id).all():
            fault.visit_id = None
        if v.fault_id:
            fault = db.session.get(Fault, v.fault_id)
            if fault and fault.visit_id == v.id:
                fault.visit_id = None
        db.session.delete(v)

    db.session.commit()
    stats['repair'] = repair_field_portal_stale(org_id)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description='Zero field technician portal tasks')
    parser.add_argument('--slug', default='', help='Organization slug (مثال: jama)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true', help='تنفيذ بدون تأكيد تفاعلي')
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print('أضف --yes للتنفيذ أو --dry-run للمعاينة')
        return 2

    from flask import g

    from app import app
    from models import Organization

    with app.app_context():
        org_id = None
        slug = (args.slug or '').strip().lower()
        if slug:
            org = Organization.query.filter_by(slug=slug).first()
            if not org:
                print(f'ERROR: لا توجد مؤسسة slug={slug}')
                return 1
            g.organization = org
            g.organization_id = org.id
            org_id = org.id
            print(f'==> {org.name} ({slug}) id={org_id}')

        stats = zero_field_portal(org_id=org_id, dry_run=args.dry_run)
        label = 'DRY-RUN' if args.dry_run else 'تم'
        print(f'{label}:')
        print(f'  أعطال مفتوحة → تم الاصلاح: {stats["faults_closed"]}')
        print(f'  زيارات نشطة → ملغاة: {stats["visits_cancelled"]}')
        print(f'  زيارات نوع عطل (حُذفت): {stats["fault_visits_deleted"]}')
        repair = stats.get('repair') or {}
        if repair:
            print(f'  إصلاح ذيل البوابة: {repair}')
        if not args.dry_run:
            print('بوابة الفني الآن فارغة — جرّب إسناد عطل أو زيارة جديدة.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
