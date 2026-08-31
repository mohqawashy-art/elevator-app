"""إجمالي الإيرادات في الصحة المالية = صفحة الإيرادات (نفس الفترة والمنطق)."""
from datetime import date

from app import app, db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit
from models import Organization
from report_data import (
    get_financial_health_report,
    summarize_revenue_rows,
    _tenant_revenue_date_bounds,
)
from tenant_scope import tenant_query


def test_financial_health_revenue_matches_summarize(client):
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
        ])
        db.session.commit()

        today = date(2026, 8, 31)
        df, dt = _tenant_revenue_date_bounds(Revenue, today)
        expected = summarize_revenue_rows(tenant_query(Revenue).all())['total']

        report = get_financial_health_report(
            db, Revenue, Expense, Contract, Technician, Elevator, MaintenanceVisit,
            date_from=df.isoformat(),
            date_to=dt.isoformat(),
            today=today,
        )
        assert report['summary']['revenue'] == expected
        assert report['summary']['revenue'] == 1500.0
