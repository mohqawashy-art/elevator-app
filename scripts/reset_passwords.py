#!/usr/bin/env python3
"""تشخيص وإعادة ضبط دخول المكتب + PIN الفنيين (بدون مسح البيانات).

  python scripts/reset_passwords.py              # تشخيص فقط
  python scripts/reset_passwords.py --apply        # إعادة الضبط
  ADMIN_PASSWORD='MyPass123!' FIELD_PIN=123456 python scripts/reset_passwords.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def diagnose() -> bool:
    from app import app, verify_password
    from field_auth import find_technician_by_login, technician_has_field_pin, verify_technician_pin
    from models import User, Technician

    ok = True
    with app.app_context():
        users = User.query.order_by(User.id).all()
        print('==> مستخدمو المكتب')
        if not users:
            print('  (لا يوجد مستخدمون — شغّل --apply لإنشاء admin)')
            ok = False
        for u in users:
            active = 'نشط' if u.is_active else 'معطّل'
            print(f'  - {u.username} | {u.email or "—"} | {u.role} | {active}')

        techs = Technician.query.order_by(Technician.code).all()
        print('==> الفنيون (بوابة الجوال)')
        if not techs:
            print('  (لا يوجد فنيون)')
        for t in techs[:20]:
            pin_ok = technician_has_field_pin(t)
            print(
                f'  - {t.code} | {t.phone or "—"} | {t.status or "—"} | PIN: {"نعم" if pin_ok else "لا"}'
            )
        if len(techs) > 20:
            print(f'  ... و {len(techs) - 20} فني إضافي')

        admin = User.query.filter_by(username='admin').first()
        if admin and verify_password(admin.password_hash, 'admin123'):
            print('  تحقق admin/admin123 ........ OK')
        else:
            print('  تحقق admin/admin123 ........ FAIL (كلمة المرور ليست admin123)')
            ok = False

        tech = find_technician_by_login('Tech-001')
        if tech and verify_technician_pin(tech, '123456'):
            print('  تحقق Tech-001/123456 ....... OK')
        else:
            print('  تحقق Tech-001/123456 ....... FAIL')
    return ok


def apply_reset() -> None:
    from app import app, db, hash_password
    from liftcore_security import is_weak_password
    from models import User, Technician

    admin_pwd = (os.environ.get('ADMIN_PASSWORD') or 'LiftCore@2026').strip()
    field_pin = (os.environ.get('FIELD_PIN') or '123456').strip()
    if len(field_pin) != 6 or not field_pin.isdigit():
        raise SystemExit('FIELD_PIN يجب أن يكون 6 أرقام')

    pin_hash = hash_password(field_pin)
    active = frozenset({'نشط', 'متاح', 'مشغول'})

    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                password_hash=hash_password(admin_pwd),
                full_name='مدير النظام',
                email='admin@liftcoreapp.com',
                role='admin',
                is_active=True,
            )
            db.session.add(admin)
        else:
            admin.password_hash = hash_password(admin_pwd)
            admin.is_active = True
        admin.must_change_password = is_weak_password(admin_pwd)

        tech_count = 0
        for tech in Technician.query.all():
            if (tech.status or 'متاح') in active:
                tech.sign_pin_hash = pin_hash
                tech_count += 1

        db.session.commit()

    print('')
    print('==> تم إعادة الضبط')
    print(f'  المكتب:  https://app.liftcoreapp.com/login')
    print(f'           admin / {admin_pwd}')
    if is_weak_password(admin_pwd):
        print('           (ستُطلب تغيير كلمة المرور بعد الدخول)')
    print(f'  الفني:   https://app.liftcoreapp.com/field/login')
    print(f'           Tech-001 أو جوال الفني / {field_pin}')
    print(f'           ({tech_count} فني نشط — نفس PIN)')


def main() -> int:
    parser = argparse.ArgumentParser(description='تشخيص / إعادة ضبط كلمات المرور')
    parser.add_argument('--apply', action='store_true', help='تطبيق إعادة الضبط')
    args = parser.parse_args()

    if args.apply:
        apply_reset()
        return 0
    diagnose()
    print('')
    print('لإصلاح الأكواد على السيرفر:')
    print('  bash deploy/reset_passwords_now.sh')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
