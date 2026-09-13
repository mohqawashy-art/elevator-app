"""تخطيط الزيارات — عقود مُجدَّدة مبكراً لا تفقد شهر التغطية."""
from datetime import date

from models import Contract, ContractElevator, Customer, Elevator, Organization, db
from operations import generate_monthly_plan, get_plan_coverage_gaps


def _seed_customer_with_elevators(org, suffix: str, n_elevators: int = 2):
    cust = Customer(
        organization_id=org.id,
        code=f'C-RN-{suffix}',
        name=f'عميل تجديد {suffix}',
        district='شارع الحج',
        status='نشط',
    )
    db.session.add(cust)
    db.session.flush()
    elevators = []
    for i in range(n_elevators):
        elev = Elevator(
            organization_id=org.id,
            customer_id=cust.id,
            code=f'EL-RN-{suffix}-{i + 1}',
            building_name=f'مبنى {i + 1}',
            status='نشط',
        )
        db.session.add(elev)
        db.session.flush()
        elevators.append(elev)
    return cust, elevators


def _add_contract(org, cust, elev, code, start, end, status='نشط'):
    c = Contract(
        organization_id=org.id,
        code=code,
        customer_id=cust.id,
        contract_type='عقد صيانة',
        maint_frequency='شهري',
        visits_per_month=1,
        start_date=start,
        end_date=end,
        district='شارع الحج',
        status=status,
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(ContractElevator(contract_id=c.id, elevator_id=elev.id))
    db.session.commit()
    return c


def test_renewed_old_contract_still_planned_for_overlap_month(client):
    """العقد القديم «تم تجديده» يبقى مشمولاً حتى نهاية فترته."""
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust, elevs = _seed_customer_with_elevators(org, 'A', 1)
        elev = elevs[0]
        _add_contract(
            org, cust, elev, 'CN-RN-OLD',
            date(2025, 9, 1), date(2026, 9, 30), status='تم تجديده',
        )
        _add_contract(
            org, cust, elev, 'CN-RN-OLD-2026',
            date(2026, 10, 1), date(2028, 9, 30), status='نشط',
        )
        preview = generate_monthly_plan(2026, 9, preview_only=True)
        assert preview.get('would_create') == 1
        gaps = get_plan_coverage_gaps('2026-09')
        assert gaps.get('missing_elevators') == 1


def test_two_elevators_early_renewal_september(client):
    """مصعدان: واحد يبدأ سبتمبر والثاني أكتوبر — مع القديم المجدّد يُغطى سبتمبر."""
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust, elevs = _seed_customer_with_elevators(org, 'B', 2)
        e1, e2 = elevs
        _add_contract(org, cust, e1, 'CN-RN-54', date(2026, 9, 1), date(2028, 9, 1))
        _add_contract(
            org, cust, e2, 'CN-RN-56-OLD',
            date(2025, 10, 1), date(2026, 9, 30), status='تم تجديده',
        )
        _add_contract(org, cust, e2, 'CN-RN-56-2026', date(2026, 10, 1), date(2028, 8, 1))
        preview = generate_monthly_plan(2026, 9, preview_only=True)
        assert preview.get('would_create') == 2
        assert preview.get('elevators_in_scope') == 2
