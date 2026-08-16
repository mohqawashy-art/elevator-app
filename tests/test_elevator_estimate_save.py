"""حفظ تقدير المصعد يعيّن organization_id على البنود."""
from datetime import date

from models import ElevatorEstimate, ElevatorEstimateLine, Organization, db
from tests.conftest import login_as


def test_elevator_estimate_save_assigns_org_on_lines(client):
    login_as(client, role='admin')
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        assert org is not None

    resp = client.post(
        '/elevator-estimates/save',
        data={
            'project_name': 'برج اختبار',
            'city': 'مكة',
            'machine_type': 'MR',
            'elev_type': 'مصعد ركاب',
            'floors': '3',
            'stops': '3',
            'capacity_kg': '630',
            'doors_count': '3',
            'include_installation': '1',
            'include_install_materials': '0',
            'margin_pct': '12',
            'vat_pct': '15',
            'status': 'مسودة',
            'estimate_date': date.today().isoformat(),
            'line_category': ['مكينة'],
            'line_description': ['مجموعة مكينة اختبار'],
            'line_quantity': ['1'],
            'line_unit': ['مجموعة'],
            'line_unit_price': ['1000'],
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert '/elevator-estimates/print/' in (resp.headers.get('Location') or '')

    with client.application.app_context():
        est = ElevatorEstimate.query.order_by(ElevatorEstimate.id.desc()).first()
        assert est is not None
        assert est.lines
        for line in est.lines:
            assert line.organization_id == est.organization_id
            assert line.organization_id is not None
