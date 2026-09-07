"""اختبارات إيراد عقود الصيانة في قائمة الدخل."""
from datetime import date

from accounting_journals import income_statement, post_revenue_journal
from chart_of_accounts import ensure_chart_for_org
from contract_cost_allocation import maintenance_contracts_pnl_summary
from models import Contract, ContractElevator, Customer, Elevator, MaintenanceVisit, Organization, Revenue, db


def test_maintenance_pnl_earned_by_visits_not_full_contract(client):
    with client.application.app_context():
        org = Organization(slug='pnl-maint', name='صيانة', status='active')
        db.session.add(org)
        db.session.commit()
        ensure_chart_for_org(org.id)

        from flask import g
        g.organization_id = org.id
        g.organization = org

        cust = Customer(
            organization_id=org.id,
            code='CL-900',
            name='عميل اختبار',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()

        elev = Elevator(
            organization_id=org.id,
            code='EL-900',
            customer_id=cust.id,
            status='نشط',
        )
        db.session.add(elev)
        db.session.flush()

        contract = Contract(
            organization_id=org.id,
            code='CN-00900',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            duration_months=12,
            visits_per_month=12,
            total=1200.0,
            value=1200.0,
            status='نشط',
        )
        db.session.add(contract)
        db.session.flush()
        db.session.add(ContractElevator(
            organization_id=org.id,
            contract_id=contract.id,
            elevator_id=elev.id,
        ))

        for i in range(7):
            db.session.add(MaintenanceVisit(
                organization_id=org.id,
                code=f'VI-9{i:03d}',
                contract_id=contract.id,
                elevator_id=elev.id,
                visit_date=date(2026, 1, 10 + i),
                status='مكتملة',
            ))
        db.session.commit()

        summary = maintenance_contracts_pnl_summary(
            period_from=date(2026, 1, 1),
            period_to=date(2026, 12, 31),
        )
        assert summary['earned_in_period'] == 700.0
        assert summary['unearned_total'] == 500.0

        rev = Revenue(
            organization_id=org.id,
            code='REV-900',
            customer_id=cust.id,
            contract_id=contract.id,
            revenue_date=date(2026, 1, 5),
            revenue_type='عقد صيانة',
            amount=1200.0,
            tax_amount=0,
            total=1200.0,
            status='محصّل',
        )
        db.session.add(rev)
        db.session.commit()
        from accounting_journals import ensure_journal_schema
        ensure_journal_schema()
        post_revenue_journal(rev)
        db.session.commit()

        pnl = income_statement(date_from=date(2026, 1, 1), date_to=date(2026, 12, 31))
        assert pnl['revenue'] == 700.0
        assert pnl['unearned_revenue'] == 500.0
        assert any(
            ln.get('name') == 'عقود صيانة — مستحق بالزيارات' and ln.get('amount') == 700.0
            for ln in pnl['revenue_lines']
        )
