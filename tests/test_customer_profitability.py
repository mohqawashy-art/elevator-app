"""تقرير ربحية العميل."""
from datetime import date

from app import app, db, Customer, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit, PartsBilling
from models import Organization
from report_data import get_customer_profitability_report


def test_customer_profitability_revenue_and_cost(client):
    with app.app_context():
        from flask import g

        org = Organization.query.filter_by(slug='default').first()
        g.organization_id = org.id

        cust = Customer(
            organization_id=org.id,
            code='C-PROF1',
            name='عميل ربحية',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()

        ct = Contract(
            organization_id=org.id,
            customer_id=cust.id,
            code='CN-PROF1',
            contract_type='عقد صيانة',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            total=12000,
            status='نشط',
            visits_per_month=12,
            duration_months=12,
        )
        db.session.add(ct)
        db.session.flush()

        db.session.add(Revenue(
            organization_id=org.id,
            customer_id=cust.id,
            contract_id=ct.id,
            code='REV-PROF1',
            revenue_date=date(2026, 3, 1),
            revenue_type='عقد صيانة',
            amount=5000,
            total=5000,
            status='محصّل',
        ))
        db.session.add(Expense(
            organization_id=org.id,
            code='EXP-PROF1',
            expense_date=date(2026, 3, 1),
            expense_type='وقود',
            amount=1000,
            description='وقود',
        ))
        db.session.commit()

        report = get_customer_profitability_report(
            cust.id,
            db, Customer, Revenue, Expense, Contract, Technician, Elevator,
            MaintenanceVisit, PartsBilling,
            date_from='2026-01-01',
            date_to='2026-06-30',
            today=date(2026, 6, 30),
            contract_status_fn=lambda c: c.status or '',
        )

        assert report['summary']['revenue_total'] == 5000.0
        assert report['summary']['active_contracts'] == 1
        assert report['contracts'][0]['revenue'] == 5000.0
        assert report['summary']['total_cost'] >= 0
        assert report['summary']['net_profit'] == round(
            report['summary']['revenue_total'] - report['summary']['total_cost'], 2
        )
