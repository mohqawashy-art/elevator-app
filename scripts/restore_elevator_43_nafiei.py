#!/usr/bin/env python3
"""إرجاع EL-0043 لمبارك هلال النفيعى كما كان أصلاً، وعكس ترحيل الأرقام إن وُجد.

الحالة الأصلية (من بيانات جما):
  EL-0043 → مبارك هلال النفيعى + عقد CN-00044

إذا نُفّذ ترحيل (+1 من 43) ثم أُضيف مصعد باقيس على 43:
  1) يحذف EL-0043 الخاطئ (عبد الرحمن باقيس) إن وُجد
  2) يرحّل كل مصعد رقمه > 43 بمقدار -1 (فيعود مبارك إلى EL-0043)
  3) يضمن الربط بعقد CN-00044

  cd ~/liftcore/jama-elevator-app
  source .venv/bin/activate
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/restore_elevator_43_nafiei.py --slug jama --dry-run
  python scripts/restore_elevator_43_nafiei.py --slug jama --yes
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TARGET_CODE = 'EL-0043'
TARGET_CUSTOMER = 'مبارك هلال النفيعى'
TARGET_CONTRACT = 'CN-00044'
WRONG_CUSTOMER = 'عبد الرحمن باقيس'
DIGITS = 4


def _code_num(code: str) -> int | None:
    m = re.match(r'^EL-(\d+)$', (code or '').strip().upper())
    return int(m.group(1)) if m else None


def _fmt(n: int) -> str:
    return f'EL-{n:0{DIGITS}d}'


def _name_match(name: str, needle: str) -> bool:
    return needle.replace('ى', 'ي') in (name or '').replace('ى', 'ي')


def main() -> int:
    parser = argparse.ArgumentParser(description='إرجاع EL-0043 لمبارك هلال النفيعى')
    parser.add_argument('--slug', default='jama')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()

    if not (os.environ.get('DATABASE_URL') or '').strip():
        print('ERROR: DATABASE_URL غير مضبوط')
        return 1
    if not args.dry_run and not args.yes:
        print('أضف --yes للتأكيد أو --dry-run للمعاينة')
        return 2

    from flask import g
    from app import app
    from models import Contract, ContractElevator, Customer, Elevator, Organization, db
    from tenant_scope import assign_organization

    with app.app_context():
        slug = (args.slug or 'jama').strip().lower()
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug!r}')
            return 1
        g.organization = org
        g.organization_id = org.id
        print(f'Tenant: {org.name} ({org.slug})')

        elevs = Elevator.query.filter_by(organization_id=org.id).all()
        el43 = next((e for e in elevs if (e.code or '').upper() == TARGET_CODE), None)
        cust43 = el43.customer.name if el43 and el43.customer else None

        nafiei = (
            Customer.query.filter_by(organization_id=org.id)
            .filter(Customer.name.contains('النفيع'))
            .first()
        )
        if not nafiei:
            nafiei = (
                Customer.query.filter_by(organization_id=org.id)
                .filter(Customer.name.contains('مبارك هلال'))
                .first()
            )
        if not nafiei:
            print(f'ERROR: لم يُعثر على عميل «{TARGET_CUSTOMER}»')
            return 1
        print(f'عميل الهدف: id={nafiei.id} code={nafiei.code} name={nafiei.name}')

        contract = Contract.query.filter_by(
            organization_id=org.id, code=TARGET_CONTRACT
        ).first()
        if contract:
            print(f'عقد الهدف: {contract.code}')
        else:
            print(f'تحذير: العقد {TARGET_CONTRACT} غير موجود')

        # هل الوضع أصلاً صحيح؟
        if el43 and el43.customer_id == nafiei.id:
            print(f'{TARGET_CODE} مربوط أصلاً بـ {cust43} — لا حاجة لترحيل عكسي.')
            if contract:
                link = ContractElevator.query.filter_by(
                    contract_id=contract.id, elevator_id=el43.id
                ).first()
                if not link and not args.dry_run:
                    link = ContractElevator(contract_id=contract.id, elevator_id=el43.id)
                    assign_organization(link)
                    db.session.add(link)
                    db.session.commit()
                    print(f'رُبط {TARGET_CODE} بعقد {TARGET_CONTRACT}')
                elif not link:
                    print(f'[dry-run] سيُربط {TARGET_CODE} بعقد {TARGET_CONTRACT}')
            print('تم.')
            return 0

        # كشف الترحيل: EL-0043 لباقيس أو غير مبارك، ويوجد مصعد لمبارك برقم أعلى
        wrong_43 = bool(
            el43 and cust43 and _name_match(cust43, WRONG_CUSTOMER)
        )
        nafiei_elevs = [
            e for e in elevs
            if e.customer_id == nafiei.id and _code_num(e.code or '') is not None
        ]
        nafiei_elevs.sort(key=lambda e: _code_num(e.code) or 0)
        print(f'مصاعد مبارك الحالية: {[e.code for e in nafiei_elevs]}')
        print(f'EL-0043 الحالي: {cust43 or "—"}')

        actions = []
        if wrong_43 or (el43 and el43.customer_id != nafiei.id):
            actions.append(f'حذف {TARGET_CODE} الحالي (عميل: {cust43})')
        # إن وُجد مصعد مبارك برقم > 43 فالترحيل حصل غالباً
        shifted = any((_code_num(e.code) or 0) > 43 for e in nafiei_elevs)
        # أيضاً: إن كان أعلى رقم عند مبارك كان 43 وأصبح 44
        if el43 is None or wrong_43 or shifted:
            to_down = [
                e for e in elevs
                if (_code_num(e.code or '') or 0) > 43
            ]
            actions.append(f'ترحيل عكسي لـ {len(to_down)} مصعد (رقم > 43 → −1)')

        if not actions:
            # لا ترحيل — فقط أعد تعيين العميل على 43 إن وُجد فارغ/خطأ
            if el43:
                actions.append(f'إعادة ربط {TARGET_CODE} بـ {nafiei.name}')
            else:
                actions.append(f'إنشاء {TARGET_CODE} لـ {nafiei.name}')

        print('الخطة:')
        for a in actions:
            print(' -', a)

        if args.dry_run:
            print('معاينة فقط — لم يُغيَّر شيء')
            return 0

        # 1) احذف EL-0043 الخاطئ إن لزم
        if el43 and el43.customer_id != nafiei.id:
            ContractElevator.query.filter_by(elevator_id=el43.id).delete(
                synchronize_session=False
            )
            print(f'حذف {el43.code} (كان لـ {cust43})')
            db.session.delete(el43)
            db.session.flush()
            elevs = Elevator.query.filter_by(organization_id=org.id).all()

        # 2) ترحيل عكسي: كل رقم > 43 ينقص 1 (ممرّان عبر أكواد مؤقتة)
        to_shift = []
        for e in elevs:
            n = _code_num(e.code or '')
            if n is not None and n > 43:
                to_shift.append((n, e))
        to_shift.sort(key=lambda x: x[0])  # من الأصغر للأكبر عند النزول

        if to_shift:
            temp = '__TMP__'
            mapping = []
            for n, e in to_shift:
                old = e.code
                new = _fmt(n - 1)
                mapping.append((e, old, new))

            for e, old, new in mapping:
                e.code = f'{temp}{old}'
                bn = e.building_name or ''
                if old in bn:
                    e.building_name = bn.replace(old, f'{temp}{old}')
            db.session.flush()

            for e, old, new in mapping:
                e.code = new
                bn = e.building_name or ''
                tmp = f'{temp}{old}'
                if tmp in bn:
                    e.building_name = bn.replace(tmp, new)
                elif old in bn:
                    e.building_name = bn.replace(old, new)
            print(f'ترحيل عكسي: {len(mapping)} مصعد')
            db.session.flush()

        # 3) تأكد أن EL-0043 لمبارك + ربط العقد
        elevs = Elevator.query.filter_by(organization_id=org.id).all()
        el43 = next((e for e in elevs if (e.code or '').upper() == TARGET_CODE), None)
        if not el43:
            # أنشئ من مواصفات المصدر: اتوماتيك، 2 وقفات، 450 كجم
            el43 = Elevator(
                code=TARGET_CODE,
                customer_id=nafiei.id,
                building_name=TARGET_CUSTOMER,
                city=nafiei.city or '',
                district=nafiei.district or '',
                address=nafiei.address or '',
                elev_type='اتوماتيك',
                capacity_kg=450,
                stops=2,
                floors=2,
                door_type='أوتوماتيك',
                status='نشط',
                notes='أُعيد بعد التراجع عن ترحيل الأرقام',
            )
            assign_organization(el43)
            db.session.add(el43)
            db.session.flush()
            print(f'أُنشئ {TARGET_CODE} لـ {nafiei.name}')
        elif el43.customer_id != nafiei.id:
            el43.customer_id = nafiei.id
            el43.building_name = TARGET_CUSTOMER
            print(f'أُعيد ربط {TARGET_CODE} بـ {nafiei.name}')
        else:
            print(f'{TARGET_CODE} صحيح: {nafiei.name}')

        if contract:
            # أزل ربط هذا المصعد من عقود أخرى ثم اربطه بـ CN-00044
            ContractElevator.query.filter_by(elevator_id=el43.id).delete(
                synchronize_session=False
            )
            link = ContractElevator(contract_id=contract.id, elevator_id=el43.id)
            assign_organization(link)
            db.session.add(link)
            print(f'رُبط {TARGET_CODE} ← {TARGET_CONTRACT}')

        db.session.commit()
        print('تم إرجاع الوضع.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
