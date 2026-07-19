#!/usr/bin/env python3
"""
تفريغ أو حذف مستأجر بالكامل.

أ) تفريغ البيانات مع الإبقاء على المؤسسة:
  python scripts/wipe_tenant_data.py --slug jama --confirm JAMA_WIPE

ب) حذف الحساب كاملاً (بيانات + مؤسسة) لإعادة دعوة كعميل جديد:
  python scripts/wipe_tenant_data.py --slug jama --delete-org --confirm JAMA_DELETE_ORG

لا يمسّ مستأجرين آخرين (default وغيره).
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CONFIRM_TOKEN = 'JAMA_WIPE'
DELETE_ORG_TOKEN = 'JAMA_DELETE_ORG'


def main() -> int:
    parser = argparse.ArgumentParser(description='تفريغ أو حذف مستأجر')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--confirm', default='', help=f'{CONFIRM_TOKEN} أو {DELETE_ORG_TOKEN}')
    parser.add_argument('--keep-users', action='store_true')
    parser.add_argument('--delete-org', action='store_true', help='حذف المؤسسة بالكامل')
    parser.add_argument('--print-only', action='store_true')
    args = parser.parse_args()

    from app import app
    from models import (
        Customer, Elevator, Contract, MaintenanceVisit, Fault,
        Technician, User, InventoryItem, WhatsAppInbox, Organization,
    )
    from tenant_lifecycle import wipe_tenant

    slug = (args.slug or 'jama').strip().lower()
    delete_org = bool(args.delete_org)
    expected = DELETE_ORG_TOKEN if delete_org else CONFIRM_TOKEN

    def _count(model, org_id: int) -> int:
        return (
            model.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org_id)
            .count()
        )

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'OK: لا توجد مؤسسة slug={slug} — الحساب غير موجود أصلاً')
            return 0

        print(f'==> مستأجر: {org.slug} (id={org.id}) — {org.name}')
        before = {
            'customers': _count(Customer, org.id),
            'elevators': _count(Elevator, org.id),
            'contracts': _count(Contract, org.id),
            'visits': _count(MaintenanceVisit, org.id),
            'faults': _count(Fault, org.id),
            'technicians': _count(Technician, org.id),
            'users': _count(User, org.id),
            'inventory': _count(InventoryItem, org.id),
            'whatsapp': _count(WhatsAppInbox, org.id),
        }
        for k, v in before.items():
            print(f'  {k}: {v}')

        if args.print_only:
            return 0

        if (args.confirm or '').strip() != expected:
            print('')
            if delete_org:
                print(f'لحذف الحساب كاملاً: --delete-org --confirm {DELETE_ORG_TOKEN}')
                print('تحذير: يحذف المؤسسة وكل بياناتها — لا يمكن التراجع.')
            else:
                print(f'لتفريغ البيانات فقط: --confirm {CONFIRM_TOKEN}')
            return 2

        result = wipe_tenant(
            org,
            keep_users=bool(args.keep_users) and not delete_org,
            delete_organization=delete_org,
        )
        print('')
        if result.get('organization_deleted'):
            print(f"==> تم حذف الحساب بالكامل: slug={result.get('slug')}")
            print('  قبل:', result['before'])
            print('')
            print('الخطوة التالية — دعوة كعميل جديد:')
            print('  1) https://admin.liftcoreapp.com/operator/onboarding')
            print(f'  2) المعرّف المقترح: {slug}')
            print(f'  3) بعد التفعيل: https://{slug}.liftcoreapp.com/login')
        else:
            print('==> تم التفريغ (المؤسسة ما زالت موجودة)')
            print('  قبل:', result['before'])
            print('  بعد:', result['after'])
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
