"""إجمالي الإيرادات في الصحة المالية = صفحة الإيرادات."""
from datetime import date

from app import app, db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit
from models import Organization
from report_data import get_financial_health_report, tenant_revenue_totals


def test_financial_health_revenue_kpi_matches_revenues_page(client):
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

        expected = tenant_revenue_totals(Revenue)['total']
        report = get_financial_health_report(
            db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit,
            date_from='2026-01-01',
            date_to='2026-08-31',
            today=date(2026, 8, 31),
        )
        assert report['summary']['revenue'] == expected
        assert report['summary']['revenue'] == 1700.0
        assert report['summary']['revenue_period'] == 0.0
