"""إيرادات الصحة المالية: مكتسب / غير مكتسب / محصّل."""
from datetime import date

from app import app, db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit
from models import ContractElevator, Customer, Organization
from report_data import get_financial_health_report


def test_financial_health_revenue_kpi_uses_earned_for_period(client):
    with app.app_context():
        from flask import g

        org = Organization.query.filter_by(slug='default').first()
        g.organization_id = org.id

        db.session.add_all([
            Revenue(
                organization_id=org.id,
                code='REV-FH1',
                revenue_date=date(2024, 3, 15),
                amount=1000,
                total=1000,
                status='محصّل',
            ),
            Revenue(
                organization_id=org.id,
                code='REV-FH2',
                revenue_date=date(2025, 6, 1),
                amount=500,
                total=500,
                status='ملغي',
            ),
            Revenue(
                organization_id=org.id,
                code='REV-FH3',
                revenue_date=date(2027, 1, 1),
                amount=200,
                total=200,
                status='محصّل',
            ),
        ])
        db.session.commit()

        report = get_financial_health_report(
            db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit,
            date_from='2026-01-01',
            date_to='2026-08-31',
            today=date(2026, 8, 31),
        )
        s = report['summary']
        assert s['revenue'] == 0.0
        assert s['revenue_earned'] == 0.0
        assert s['revenue_collected'] == 0.0
        assert s['revenue_unearned'] == 0.0
        assert s['revenue_all_time'] == 1700.0


def test_financial_health_maintenance_earned_unearned_collected(client):
    with app.app_context():
        from flask import g

        org = Organization(slug='fh-maint', name='صحة مالية', status='active')
        db.session.add(org)
        db.session.commit()
        g.organization_id = org.id

        cust = Customer(
            organization_id=org.id,
            code='CL-FH',
            name='عميل',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()

        elev = Elevator(
            organization_id=org.id,
            code='EL-FH',
            customer_id=cust.id,
            status='نشط',
        )
        db.session.add(elev)
        db.session.flush()

        contract = Contract(
            organization_id=org.id,
            code='CN-FH01',
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
                code=f'VI-FH{i:02d}',
                contract_id=contract.id,
                elevator_id=elev.id,
                visit_date=date(2026, 2, 1 + i),
                status='مكتملة',
            ))

        db.session.add(Revenue(
            organization_id=org.id,
            code='REV-FH-M',
            contract_id=contract.id,
            customer_id=cust.id,
            revenue_date=date(2026, 1, 5),
            revenue_type='تجديد عقد',
            amount=1200,
            total=1200,
            status='محصّل',
        ))
        db.session.add(Revenue(
            organization_id=org.id,
            code='REV-FH-P',
            revenue_date=date(2026, 3, 10),
            revenue_type='قطع غيار',
            amount=300,
            total=300,
            status='محصّل',
        ))
        db.session.commit()

        report = get_financial_health_report(
            db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit,
            date_from='2026-01-01',
            date_to='2026-12-31',
            today=date(2026, 12, 31),
        )
        s = report['summary']
        assert s['revenue_earned'] == 1000.0  # محصّل 1500 − غير مكتسب 500
        assert s['revenue_unearned'] == 500.0
        assert s['revenue_collected'] == 1500.0
        assert s['revenue'] == s['revenue_earned']


def test_financial_health_empty_status_counts_as_collected(client):
    with app.app_context():
        from flask import g

        org = Organization(slug='fh-empty-st', name='حالة فارغة', status='active')
        db.session.add(org)
        db.session.commit()
        g.organization_id = org.id

        db.session.add(Revenue(
            organization_id=org.id,
            code='REV-EMPTY',
            revenue_date=date(2026, 5, 1),
            amount=800,
            total=800,
            status='',
        ))
        db.session.commit()

        report = get_financial_health_report(
            db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit,
            date_from='2026-01-01',
            date_to='2026-12-31',
            today=date(2026, 12, 31),
        )
        assert report['summary']['revenue_collected'] == 800.0
        assert report['summary']['revenue_earned'] == 800.0


def test_financial_health_jama_style_visits_unearned(client):
    """visits_per_month=1 في الاستيراد القديم + برنامج شهري → 12 زيارة."""
    with app.app_context():
        from flask import g

        org = Organization(slug='fh-jama-v', name='جما زيارات', status='active')
        db.session.add(org)
        db.session.commit()
        g.organization_id = org.id

        cust = Customer(organization_id=org.id, code='CL-JV', name='عميل', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=org.id, code='EL-JV', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()

        contract = Contract(
            organization_id=org.id,
            code='CN-JV01',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            duration_months=12,
            maint_frequency='شهري',
            visits_per_month=1,
            total=1200.0,
            value=1200.0,
            status='نشط',
        )
        db.session.add(contract)
        db.session.flush()
        db.session.add(ContractElevator(
            organization_id=org.id, contract_id=contract.id, elevator_id=elev.id,
        ))
        db.session.add(Revenue(
            organization_id=org.id,
            code='REV-JV',
            contract_id=contract.id,
            customer_id=cust.id,
            revenue_date=date(2026, 1, 10),
            revenue_type='تجديد عقد',
            amount=1200,
            total=1200,
            status='محصل',
        ))
        db.session.commit()

        report = get_financial_health_report(
            db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit,
            date_from='2026-01-01',
            date_to='2026-12-31',
            today=date(2026, 12, 31),
        )
        s = report['summary']
        assert s['revenue_collected'] == 1200.0
        assert s['revenue_unearned'] == 1200.0
        assert s['revenue_earned'] == 0.0
