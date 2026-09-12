"""اختبار إضافة مسودة التخطيط دون حذف الزيارات الموجودة."""
from datetime import date

from models import Contract, ContractElevator, Customer, Elevator, MaintenanceVisit, Organization, db
from operations import create_plan_from_draft, get_plan


def _seed_contract_elevator(org, code_suffix: str):
    cust = Customer(
        organization_id=org.id,
        code=f'C-PD-{code_suffix}',
        name=f'عميل {code_suffix}',
        status='نشط',
    )
    db.session.add(cust)
    db.session.flush()
    elev = Elevator(
        organization_id=org.id,
        customer_id=cust.id,
        code=f'EL-PD-{code_suffix}',
        status='نشط',
    )
    db.session.add(elev)
    db.session.flush()
    contract = Contract(
        organization_id=org.id,
        code=f'CN-PD-{code_suffix}',
        customer_id=cust.id,
        contract_type='عقد صيانة',
        start_date=date(2026, 1, 1),
        end_date=date(2027, 1, 1),
        district='حي اختبار',
        status='نشط',
    )
    db.session.add(contract)
    db.session.flush()
    db.session.add(ContractElevator(contract_id=contract.id, elevator_id=elev.id))
    db.session.commit()
    return elev, contract


def test_create_plan_from_draft_appends_without_replace(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        elev1, contract1 = _seed_contract_elevator(org, '01')
        elev2, contract2 = _seed_contract_elevator(org, '02')
        plan_month = '2026-09'
        visit_day = '2026-09-07'

        first = create_plan_from_draft(
            plan_month,
            [{
                'elevator_id': elev1.id,
                'contract_id': contract1.id,
                'visit_date': visit_day,
                'route_order': 1,
                'district': 'حي اختبار',
            }],
            replace_draft=False,
        )
        assert first.get('created') == 1

        second = create_plan_from_draft(
            plan_month,
            [{
                'elevator_id': elev2.id,
                'contract_id': contract2.id,
                'visit_date': visit_day,
                'route_order': 1,
                'district': 'حي اختبار',
            }],
            replace_draft=False,
        )
        assert second.get('created') == 1

        plan = get_plan(plan_month)
        day_visits = [v for v in plan['visits'] if v['visit_date'] == visit_day]
        assert len(day_visits) == 2
        elevator_codes = {v['elevator'] for v in day_visits}
        assert elevator_codes == {elev1.code, elev2.code}
        orders = sorted(v['route_order'] for v in day_visits)
        assert orders == [1, 2]
