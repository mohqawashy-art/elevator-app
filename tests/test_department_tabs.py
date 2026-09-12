"""اختبارات تبويبات منصات الأقسام."""
from department_portals import (
    department_href_is_active,
    resolve_department_slug,
    resolve_report_group_slug,
)


def test_resolve_department_from_query():
    slug = resolve_department_slug(
        '/clients',
        {'scope': 'maintenance', 'department': 'maintenance'},
        None,
    )
    assert slug == 'maintenance'


def test_resolve_department_from_path_and_scope():
    slug = resolve_department_slug(
        '/clients',
        {'scope': 'maintenance'},
        'installations',
    )
    assert slug == 'maintenance'


def test_resolve_department_installation_path():
    slug = resolve_department_slug('/installation/projects', {}, None)
    assert slug == 'installations'


def test_resolve_department_sales_path():
    slug = resolve_department_slug('/sales/quotes', {'kind': 'install'}, None)
    assert slug == 'marketing'


def test_department_href_is_active_matches_scope():
    assert department_href_is_active(
        '/clients?scope=maintenance&department=maintenance',
        '/clients',
        {'scope': 'maintenance', 'department': 'maintenance'},
    )


def test_department_href_is_active_rejects_wrong_scope():
    assert not department_href_is_active(
        '/clients?scope=maintenance&department=maintenance',
        '/clients',
        {'scope': 'installation', 'department': 'installations'},
    )


def test_resolve_department_reports_path():
    slug = resolve_department_slug('/reports/faults', {}, None)
    assert slug == 'reports'


def test_resolve_department_reports_home():
    slug = resolve_department_slug('/reports', {'department': 'reports'}, None)
    assert slug == 'reports'


def test_resolve_report_group_maintenance():
    assert resolve_report_group_slug('/reports/faults', {}) == 'maintenance'
    assert resolve_report_group_slug('/reports/financial', {}) == 'finance'
    assert resolve_report_group_slug('/reports', {}) is None


def test_resolve_department_maintenance_quote_edit_ignores_stale_session():
    slug = resolve_department_slug(
        '/sales/maintenance-quotes/42',
        {},
        'maintenance',
    )
    assert slug == 'marketing'


def test_resolve_department_install_quote_form_ignores_stale_session():
    slug = resolve_department_slug(
        '/installation/projects/7/quote',
        {},
        'maintenance',
    )
    assert slug == 'marketing'


def test_resolve_department_project_detail_is_installations():
    slug = resolve_department_slug(
        '/installation/projects/7',
        {},
        'marketing',
    )
    assert slug == 'installations'


def test_resolve_department_faults_is_maintenance():
    slug = resolve_department_slug('/faults/12/report', {}, 'marketing')
    assert slug == 'maintenance'


def test_department_href_active_on_maintenance_quote_edit():
    assert department_href_is_active(
        '/sales/maintenance-quotes?department=marketing',
        '/sales/maintenance-quotes/42',
        {'department': 'marketing'},
    )


def test_department_href_active_on_install_quote_form():
    assert department_href_is_active(
        '/sales/quotes?kind=install&department=marketing',
        '/installation/projects/7/quote',
        {'department': 'marketing'},
    )
