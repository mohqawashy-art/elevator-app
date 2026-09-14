"""إصدار حسابات تجريبية مؤقتة من لوحة المنصة للعملاء المحتملين."""

from __future__ import annotations

import os
import secrets
import string
from datetime import date, datetime, timedelta

from models import (
    Contract,
    ContractElevator,
    Customer,
    Elevator,
    Fault,
    MaintenanceVisit,
    Organization,
    Technician,
    db,
)
from tenant_signup import create_tenant_signup, normalize_slug, validate_company_name


DEMO_NOTE_MARKER = '[DEMO]'
DEMO_USERNAME = 'demo'


def demo_days_default() -> int:
    try:
        return max(1, min(90, int(os.environ.get('LIFTCORE_DEMO_DAYS', '7') or 7)))
    except (TypeError, ValueError):
        return 7


def organization_access_allowed(org) -> bool:
    """هل يُسمح بالدخول للمؤسسة؟ (إيقاف / انتهاء التجربة)."""
    if not org:
        return False
    status = (getattr(org, 'status', None) or '').strip().lower()
    if status == 'suspended':
        return False
    if status == 'trial':
        end = getattr(org, 'trial_ends_at', None)
        if end is not None and end < datetime.utcnow():
            return False
    return True


def is_demo_org(org) -> bool:
    notes = (getattr(org, 'notes', None) or '')
    return DEMO_NOTE_MARKER in notes


def _unique_demo_slug(company_hint: str = '') -> str:
    base = normalize_slug(company_hint) if company_hint else ''
    base = base[:20].strip('-') if base else ''
    alphabet = string.ascii_lowercase + string.digits
    for _ in range(40):
        token = ''.join(secrets.choice(alphabet) for _ in range(4))
        slug = f'demo-{base}-{token}' if base else f'demo-{token}'
        slug = normalize_slug(slug)[:63]
        if len(slug) < 5:
            continue
        if not Organization.query.filter_by(slug=slug).first():
            return slug
    raise RuntimeError('تعذّر توليد معرّف تجريبي فريد')


def _generate_temp_password(length: int = 14) -> str:
    # يطابق سياسة كلمات المرور الشائعة: حروف + أرقام + رمز
    alphabet = string.ascii_letters + string.digits + '@#$!&'
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in '@#$!&' for c in pwd)
        ):
            return pwd


def seed_lightweight_demo(organization_id: int) -> dict:
    """بيانات بسيطة: عميلان، 4 مصاعد، فني، عقد، زيارتان، عطل واحد — مكة."""
    oid = int(organization_id)
    today = date.today()

    c1 = Customer(
        organization_id=oid,
        code='C-0001',
        name='برج الصفا التجريبي',
        city='مكة المكرمة',
        district='العزيزية',
        address='حي تجريبي — للعرض فقط',
        phone='0500000001',
        contact_person='مشرف المبنى',
        status='نشط',
        entity_type='شركة',
        notes='بيانات تجريبية',
    )
    c2 = Customer(
        organization_id=oid,
        code='C-0002',
        name='مجمّع الشوقية التجريبي',
        city='مكة المكرمة',
        district='الشوقية',
        address='حي تجريبي — للعرض فقط',
        phone='0500000002',
        contact_person='مسؤول الصيانة',
        status='نشط',
        entity_type='شركة',
        notes='بيانات تجريبية',
    )
    db.session.add_all([c1, c2])
    db.session.flush()

    elev_specs = [
        (c1, 'EL-0001', 'برج الصفا — مصعد ركاب 1', 'مصعد ركاب', 'Otis', 'MR', 8, 630),
        (c1, 'EL-0002', 'برج الصفا — مصعد خدمة', 'مصعد بضائع', 'Kone', 'MR', 6, 1000),
        (c2, 'EL-0003', 'الشوقية — مصعد ركاب', 'مصعد ركاب', 'Schindler', 'MRL', 10, 800),
        (c2, 'EL-0004', 'الشوقية — مصعد مستشفى', 'مصعد مستشفى', 'Mitsubishi', 'MR', 7, 1600),
    ]
    elevators = []
    for cust, code, building, etype, brand, machine, floors, kg in elev_specs:
        el = Elevator(
            organization_id=oid,
            code=code,
            customer_id=cust.id,
            building_name=building,
            city='مكة المكرمة',
            district=cust.district,
            elev_type=etype,
            brand=brand,
            floors=floors,
            stops=floors,
            capacity_kg=kg,
            machine_type=machine,
            status='نشط',
            last_maintenance=today - timedelta(days=20),
            next_maintenance=today + timedelta(days=10),
            maint_frequency='شهري',
            notes='مصعد تجريبي للعرض',
        )
        elevators.append(el)
    db.session.add_all(elevators)
    db.session.flush()

    tech = Technician(
        organization_id=oid,
        code='Tech-001',
        name='فني تجريبي',
        phone='0500000099',
        job_title='فني صيانة',
        specialization='مصاعد ركاب',
        city='مكة المكرمة',
        status='متاح',
        team='صيانة',
        notes='حساب عرض — بدون PIN ميداني',
    )
    db.session.add(tech)
    db.session.flush()

    contract = Contract(
        organization_id=oid,
        code='CN-00001',
        customer_id=c1.id,
        contract_type='عقد صيانة',
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=335),
        duration_months=12,
        maint_frequency='شهري',
        visits_per_month=1,
        value=24000,
        tax_pct=15,
        tax_amount=3600,
        total=27600,
        payment_terms='ربع سنوي',
        invoice_status='غير مدفوع',
        status='نشط',
        city='مكة المكرمة',
        notes='عقد تجريبي للعرض',
    )
    db.session.add(contract)
    db.session.flush()
    for el in elevators:
        db.session.add(ContractElevator(
            organization_id=oid,
            contract_id=contract.id,
            elevator_id=el.id,
        ))

    v_done = MaintenanceVisit(
        organization_id=oid,
        code='VI-00001',
        contract_id=contract.id,
        elevator_id=elevators[0].id,
        technician_id=tech.id,
        visit_type='دورية',
        visit_date=today - timedelta(days=7),
        visit_time='10:00',
        status='مكتملة',
        works_done='فحص دوري — تشغيل طبيعي',
        completed_at=datetime.utcnow() - timedelta(days=7),
        notes='زيارة تجريبية مكتملة',
    )
    v_sched = MaintenanceVisit(
        organization_id=oid,
        code='VI-00002',
        contract_id=contract.id,
        elevator_id=elevators[2].id,
        technician_id=tech.id,
        visit_type='دورية',
        visit_date=today + timedelta(days=5),
        visit_time='11:00',
        status='مجدولة',
        notes='زيارة تجريبية مجدولة',
    )
    db.session.add_all([v_done, v_sched])

    fault = Fault(
        organization_id=oid,
        code='FA-00001',
        elevator_id=elevators[1].id,
        technician_id=tech.id,
        fault_type='باب',
        description='تأخر إغلاق الباب — بلاغ تجريبي',
        client_report='الباب يبطئ أحياناً',
        reporter_name='مشرف المبنى',
        reporter_phone='0500000001',
        priority='عادية',
        status='مفتوح',
        reported_at=datetime.utcnow() - timedelta(hours=6),
        notes='عطل تجريبي للعرض',
    )
    db.session.add(fault)
    db.session.flush()

    return {
        'customers': 2,
        'elevators': 4,
        'technicians': 1,
        'contracts': 1,
        'visits': 2,
        'faults': 1,
    }


def create_demo_account(
    *,
    company_name: str | None = None,
    contact_name: str | None = None,
    contact_email: str | None = None,
    days: int | None = None,
    password_hasher,
) -> dict:
    """ينشئ مؤسسة تجريبية + يوزر مؤقت + بيانات عيّنة (4 مصاعد)."""
    from liftcore_security import password_policy_error

    days_n = int(days) if days is not None else demo_days_default()
    days_n = max(1, min(90, days_n))

    label = (company_name or '').strip() or 'حساب تجريبي LiftCore'
    err = validate_company_name(label)
    if err:
        return {'ok': False, 'errors': [err]}

    admin_name = (contact_name or '').strip() or 'مستخدم تجريبي'
    email = (contact_email or '').strip().lower()
    if not email:
        # بريد داخلي غير حقيقي — لا يُرسل عليه شيء افتراضياً
        email = f'demo+{secrets.token_hex(3)}@demo.liftcoreapp.com'
    elif '@' not in email or '.' not in email.split('@')[-1]:
        return {'ok': False, 'errors': ['البريد الإلكتروني غير صالح.']}

    slug = _unique_demo_slug(label if label != 'حساب تجريبي LiftCore' else '')
    password = _generate_temp_password(14)
    pwd_err = password_policy_error(password)
    if pwd_err:
        return {'ok': False, 'errors': [pwd_err]}

    result = create_tenant_signup(
        company_name=label,
        slug=slug,
        admin_email=email,
        admin_name=admin_name,
        password_hash=password_hasher(password),
        username=DEMO_USERNAME,
        trial_days=days_n,
        elevators_limit=4,
        technicians_limit=3,
        office_users_limit=3,
        billing_status='complimentary',
        notes=(
            f'{DEMO_NOTE_MARKER} حساب تجريبي مؤقت للعملاء المحتملين. '
            f'يوزر مؤقت: {DEMO_USERNAME}. ينتهي تلقائياً بعد انتهاء التجربة.'
        ),
    )
    if not result.get('ok'):
        return result

    org_id = result['organization_id']
    try:
        counts = seed_lightweight_demo(org_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        org = db.session.get(Organization, org_id)
        if org:
            try:
                from tenant_lifecycle import wipe_tenant

                wipe_tenant(org, keep_users=False, delete_organization=True)
            except Exception:
                db.session.rollback()
        raise

    org = db.session.get(Organization, org_id)
    login_url = result.get('login_url') or f'https://{slug}.liftcoreapp.com/login'
    return {
        'ok': True,
        'organization_id': org_id,
        'slug': slug,
        'username': DEMO_USERNAME,
        'password': password,
        'login_url': login_url,
        'trial_ends_at': org.trial_ends_at if org else None,
        'days': days_n,
        'seed': counts,
        'admin_email': email,
        'company_name': label,
    }
