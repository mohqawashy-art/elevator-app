"""اختبارات تبويبات منصات الأقسام."""
from department_portals import department_href_is_active, resolve_department_slug


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
