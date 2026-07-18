#!/usr/bin/env python3
"""
بدء رسمي لفترة اختبار جما — شركة تقنية جما التميز للمصاعد.

لا يمسح بيانات. يضبط اسم الشركة، يمدّد التجربة، وينشئ مستخدمي الاختبار.

على السيرفر (PostgreSQL / tenant jama):
  cd ~/liftcore/elevator-app
  git pull --ff-only origin main
  set -a; source /etc/liftcore/platform.env; set +a
  python scripts/kickoff_jama_formal.py

خيارات:
  --days 21          مدة التجربة بالأيام (افتراضي 21)
  --activate         تفعيل status=active فوراً (بدل trial)
  --print-only       عرض الحالة دون تعديل
  --slug jama        معرّف المؤسسة
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

COMPANY_AR = 'شركة تقنية جما التميز للمصاعد'
COMPANY_EN = 'Jama Elevator Excellence Tech Co.'
DEFAULT_SLUG = 'jama'

# مستخدمو فترة الاختبار — كلمات مرور تُولَّد عشوائياً مرة واحدة
PILOT_USERS = (
    {
        'username': 'jama_admin',
        'full_name': 'مدير جما — اختبار',
        'role': 'admin',
        'email': 'admin@jama.liftcoreapp.com',
    },
    {
        'username': 'jama_ops',
        'full_name': 'تشغيل مكتب جما — اختبار',
        'role': 'manager',
        'email': 'ops@jama.liftcoreapp.com',
    },
)


def _gen_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    # تجنب أحرف ملتبسة
    alphabet = alphabet.replace('O', '').replace('0', '').replace('l', '').replace('I', '')
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _load_app():
    from app import app, db, hash_password
    from flask import g
    from models import Organization, Settings, User
    from platform_billing import ensure_subscription_defaults, extend_trial
    from tenant_scope import assign_organization

    return {
        'app': app,
        'db': db,
        'hash_password': hash_password,
        'g': g,
        'Organization': Organization,
        'Settings': Settings,
        'User': User,
        'ensure_subscription_defaults': ensure_subscription_defaults,
        'extend_trial': extend_trial,
        'assign_organization': assign_organization,
    }


def run(*, slug: str, days: int, activate: bool, print_only: bool) -> int:
    ctx = _load_app()
    app = ctx['app']
    db = ctx['db']
    Organization = ctx['Organization']
    Settings = ctx['Settings']
    User = ctx['User']
    g = ctx['g']
    hash_password = ctx['hash_password']
    assign_organization = ctx['assign_organization']
    ensure_subscription_defaults = ctx['ensure_subscription_defaults']
    extend_trial = ctx['extend_trial']

    credentials: list[dict] = []

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: لا توجد مؤسسة slug={slug}')
            print('  أنشئها أولاً عبر المنصة أو signup، أو تأكد من DATABASE_URL.')
            return 1

        g.organization = org
        g.organization_id = org.id

        print('==> مؤسسة')
        print(f'  id={org.id} slug={org.slug}')
        print(f'  الاسم الحالي: {org.name}')
        print(f'  الحالة: {org.status} | trial_ends_at={org.trial_ends_at}')

        settings = Settings.query.filter_by(organization_id=org.id).first()
        if not settings:
            # قد تكون صف واحداً قديماً بدون عزل — أو لا يوجد بعد
            settings = Settings.query.first()
            if settings and getattr(settings, 'organization_id', None) not in (None, org.id):
                settings = None
        if not settings:
            settings = Settings()
            assign_organization(settings)
            db.session.add(settings)
            print('==> أُنشئ صف إعدادات جديد للمؤسسة')

        print(f'  إعدادات الشركة: {settings.company_name or "—"}')

        if print_only:
            users = User.query.filter_by(organization_id=org.id).order_by(User.id).all()
            print('==> المستخدمون')
            for u in users:
                print(f'  {u.username} | {u.role} | active={u.is_active} | {u.full_name or ""}')
            print(f'==> الرابط: https://{slug}.liftcoreapp.com/login')
            return 0

        # شركة
        org.name = COMPANY_AR
        org.name_en = COMPANY_EN
        org.notes = (
            (org.notes or '').strip()
            + f'\n[{datetime.utcnow().date()}] kickoff pilot — {COMPANY_AR}'
        ).strip()

        if activate:
            org.status = 'active'
            org.suspended_at = None
            org.trial_ends_at = None
            ensure_subscription_defaults(org)
            print(f'==> تم تفعيل المؤسسة active')
        else:
            org.status = 'trial'
            org.suspended_at = None
            extend_trial(org, days=days)
            print(f'==> تجربة حتى: {org.trial_ends_at}')

        if settings:
            settings.company_name = COMPANY_AR
            settings.company_name_en = COMPANY_EN
            db.session.add(settings)

        db.session.add(org)

        # مستخدمو الاختبار
        for spec in PILOT_USERS:
            user = User.query.filter_by(
                organization_id=org.id, username=spec['username'],
            ).first()
            password = _gen_password()
            if not user:
                user = User(
                    username=spec['username'],
                    password_hash=hash_password(password),
                    full_name=spec['full_name'],
                    email=spec['email'],
                    role=spec['role'],
                    is_active=True,
                    must_change_password=True,
                    language='ar',
                )
                assign_organization(user)
                db.session.add(user)
                action = 'created'
            else:
                user.password_hash = hash_password(password)
                user.full_name = spec['full_name']
                user.email = spec['email']
                user.role = spec['role']
                user.is_active = True
                user.must_change_password = True
                action = 'reset'
            credentials.append({
                'username': spec['username'],
                'password': password,
                'role': spec['role'],
                'full_name': spec['full_name'],
                'action': action,
            })

        # تنبيه بخصوص admin التجريبي
        demo_admin = User.query.filter_by(
            organization_id=org.id, username='admin',
        ).first()
        if demo_admin and demo_admin.is_active:
            print('==> تحذير: حساب admin ما زال نشطاً — غيّر كلمة مروره أو عطّله بعد تسليم jama_admin')

        db.session.commit()

    out_dir = os.path.join(ROOT, 'instance')
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(out_dir, f'jama_kickoff_credentials_{stamp}.json')
    payload = {
        'company': COMPANY_AR,
        'slug': slug,
        'login_url': f'https://{slug}.liftcoreapp.com/login',
        'field_login_url': f'https://{slug}.liftcoreapp.com/field/login',
        'generated_at': datetime.utcnow().isoformat(sep=' ', timespec='seconds') + 'Z',
        'trial_days': days if not activate else None,
        'status': 'active' if activate else 'trial',
        'users': credentials,
        'note': 'احذف هذا الملف بعد التسليم الآمن. لا ترفعه إلى Git.',
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print('')
    print('==> تم التجهيز')
    print(f'  الشركة: {COMPANY_AR}')
    print(f'  الدخول: https://{slug}.liftcoreapp.com/login')
    print(f'  بوابة الفني: https://{slug}.liftcoreapp.com/field/login')
    print('')
    print('==> حسابات الاختبار (سلّمها لجما عبر قناة آمنة ثم احذف الملف)')
    for c in credentials:
        print(f"  {c['username']} / {c['password']}  ({c['role']}) [{c['action']}]")
    print('')
    print(f'  حُفظت أيضاً في: {out_path}')
    print('  قالب الملاحظات: deploy/data/jama_kickoff/FEEDBACK_TRACKER.csv')
    print('  نص التسليم: deploy/data/jama_kickoff/HANDOVER_AR.txt')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Kickoff رسمي لفترة اختبار جما')
    parser.add_argument('--slug', default=DEFAULT_SLUG)
    parser.add_argument('--days', type=int, default=21, help='أيام التجربة')
    parser.add_argument('--activate', action='store_true', help='تفعيل active فوراً')
    parser.add_argument('--print-only', action='store_true', help='عرض فقط')
    args = parser.parse_args()
    days = max(7, min(int(args.days or 21), 90))
    return run(
        slug=(args.slug or DEFAULT_SLUG).strip().lower(),
        days=days,
        activate=bool(args.activate),
        print_only=bool(args.print_only),
    )


if __name__ == '__main__':
    raise SystemExit(main())
