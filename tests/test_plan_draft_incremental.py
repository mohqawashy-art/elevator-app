"""اختبار إضافة مسودة التخطيط دون حذف الزيارات الموجودة."""
from datetime import date

from models import (
    Contract, ContractElevator, Customer, Elevator, MaintenanceTeam,
    MaintenanceVisit, Organization, Technician, db,
)
from maintenance_teams import assign_visits_to_team
from operations import assign_visits_to_technician, create_plan_from_draft, get_plan


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


def test_draft_assigns_team_or_technician(client):
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        elev_team, contract_team = _seed_contract_elevator(org, 'TM')
        elev_tech, contract_tech = _seed_contract_elevator(org, 'TC')
        leader = Technician(
            organization_id=org.id, code='T-PLAN-L', name='رئيس الفرقة', team='صيانة', status='متاح',
        )
        solo = Technician(
            organization_id=org.id, code='T-PLAN-S', name='فني منفرد', team='صيانة', status='متاح',
        )
        db.session.add_all([leader, solo])
        db.session.flush()
        team = MaintenanceTeam(
            organization_id=org.id, code='MT-PLAN', name='فرقة شمال', leader_id=leader.id, active=True,
        )
        db.session.add(team)
        db.session.commit()
        plan_month = '2026-10'
        result = create_plan_from_draft(
            plan_month,
            [
                {
                    'elevator_id': elev_team.id,
                    'contract_id': contract_team.id,
                    'visit_date': '2026-10-05',
                    'route_order': 1,
                    'district': 'حي اختبار',
                    'team_id': team.id,
                },
                {
                    'elevator_id': elev_tech.id,
                    'contract_id': contract_tech.id,
                    'visit_date': '2026-10-06',
                    'route_order': 1,
                    'district': 'حي اختبار',
                    'technician_id': solo.id,
                },
            ],
            replace_draft=False,
        )
        assert result.get('created') == 2
        by_elev = {v['elevator']: v for v in result['visits']}
        team_row = by_elev[elev_team.code]
        tech_row = by_elev[elev_tech.code]
        assert team_row['team_id'] == team.id
        assert team_row['technician_id'] == leader.id
        assert team_row['technician_name'] == 'رئيس الفرقة'
        assert tech_row['team_id'] is None
        assert tech_row['technician_id'] == solo.id
        assert tech_row['technician_name'] == 'فني منفرد'
        stored = MaintenanceVisit.query.filter_by(elevator_id=elev_tech.id, plan_month=plan_month).one()
        assert stored.maintenance_team_id is None
        assert stored.technician_id == solo.id

        assert assign_visits_to_team([stored.id], team.id, plan_month) == 1
        db.session.refresh(stored)
        assert stored.maintenance_team_id == team.id
        assert stored.technician_id == leader.id

        assert assign_visits_to_technician([stored.id], solo.id, plan_month) == 1
        db.session.refresh(stored)
        assert stored.maintenance_team_id is None
        assert stored.technician_id == solo.id
