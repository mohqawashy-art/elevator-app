"""بوابة الأقسام — ظهور الأقسام والروابط حسب الصلاحيات."""
from __future__ import annotations

from liftcore_permissions import dump_permissions_extra
from models import User, db
from tests.conftest import login_as


def test_home_requires_login(client):
    response = client.get('/home', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in (response.headers.get('Location') or '')


def test_admin_sees_all_department_cards_and_sidebar_home(client):
    login_as(client, 'admin')
    response = client.get('/home')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for title in (
        'الصيانة والأعطال',
        'التركيبات والتحديث',
        'التسويق والمبيعات',
        'المخازن والمشتريات',
        'شؤون العاملين',
        'الحسابات والمالية',
        'الإدارة والمتابعة',
    ):
        assert title in html
    assert 'href="/home"' in html
    assert 'href="/departments/maintenance"' in html
    assert 'href="/departments/installations"' in html
    assert 'href="/departments/marketing"' in html
    assert 'data-nav-group' not in html

    portal = client.get('/departments/maintenance')
    assert portal.status_code == 200
    portal_html = portal.get_data(as_text=True)
    assert 'منصة الصيانة والأعطال' in portal_html
    assert 'عملاء الصيانة' in portal_html
    assert '/clients?scope=maintenance' in portal_html
    assert '/contracts?scope=maintenance' in portal_html
    assert 'class="department-tabs"' in portal_html
    assert 'data-nav-group' not in portal_html

    inner_page = client.get('/faults')
    assert inner_page.status_code == 200
    inner_html = inner_page.get_data(as_text=True)
    assert 'كل الأقسام' in inner_html
    assert 'عملاء الصيانة' in inner_html
    assert 'عقود الصيانة' in inner_html
    assert 'الحسابات والمالية' not in inner_html
    assert 'إدارة المخازن' not in inner_html
    assert 'class="department-nav-marker"' in inner_html
    assert 'department-tabs-label' in inner_html
    assert 'department-tab--report' in inner_html
    assert 'class="department-tabs-title"' in inner_html
    assert 'الصيانة والأعطال' in inner_html

    client.get('/home')
    explicit_page = client.get('/faults?department=maintenance')
    explicit_html = explicit_page.get_data(as_text=True)
    assert 'عملاء الصيانة' in explicit_html
    assert 'إدارة المخازن' not in explicit_html

    installation_page = client.get('/installation/?department=installations')
    assert installation_page.status_code == 200
    installation_html = installation_page.get_data(as_text=True)
    assert 'data-department="installations"' in installation_html
    assert '← النظام الرئيسي' not in installation_html


def test_all_department_portals_use_the_same_tab_chrome(client):
    login_as(client, 'admin')
    inner_pages = {
        'maintenance': '/faults?department=maintenance',
        'installations': '/installation/?department=installations',
        'marketing': '/sales/?department=marketing',
        'inventory': '/inventory?department=inventory',
        'personnel': '/technicians?department=personnel',
        'accounting': '/revenues?department=accounting',
        'management': '/dashboard?department=management',
    }
    titles = {
        'maintenance': 'الصيانة والأعطال',
        'installations': 'التركيبات والتحديث',
        'marketing': 'التسويق والمبيعات',
        'inventory': 'المخازن والمشتريات',
        'personnel': 'شؤون العاملين',
        'accounting': 'الحسابات والمالية',
        'management': 'الإدارة والمتابعة',
    }
    for slug, inner_url in inner_pages.items():
        portal = client.get(f'/departments/{slug}')
        assert portal.status_code == 200, slug
        portal_html = portal.get_data(as_text=True)
        assert 'class="department-tabs"' in portal_html, slug
        assert 'كل الأقسام' in portal_html, slug
        assert 'department-tabs-label' in portal_html, slug
        assert 'class="department-tabs-title"' in portal_html, slug
        assert titles[slug] in portal_html, slug
        assert f'data-department="{slug}"' in portal_html, slug

        inner = client.get(inner_url)
        assert inner.status_code == 200, inner_url
        inner_html = inner.get_data(as_text=True)
        assert 'class="department-nav-marker"' in inner_html, inner_url
        assert 'كل الأقسام' in inner_html, inner_url
        assert 'department-tabs-label' in inner_html, inner_url
        assert 'class="department-tabs-title"' in inner_html, inner_url
        assert titles[slug] in inner_html, inner_url
        assert f'data-department="{slug}"' in inner_html, inner_url

    settings_page = client.get('/settings?department=management')
    assert settings_page.status_code == 200
    settings_html = settings_page.get_data(as_text=True)
    assert 'class="department-tabs"' in settings_html
    assert 'class="department-tabs-title"' in settings_html
    assert 'الإدارة والمتابعة' in settings_html
    assert 'data-department="management"' in settings_html
    assert 'كل الأقسام' in settings_html


def test_custom_finance_user_only_sees_authorized_department(client):
    with client.application.app_context():
        user = db.session.get(User, client._user_ids['viewer'])
        user.role = 'custom'
        user.permissions_extra = dump_permissions_extra([
            'revenues.read',
            'report_revenues.read',
        ])
        db.session.commit()

    login_as(client, 'viewer')
    response = client.get('/home')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'الحسابات والمالية' in html
    assert 'href="/departments/accounting"' in html
    assert 'الصيانة والأعطال' not in html
    assert 'المخازن والمشتريات' not in html
    assert 'التركيبات والتحديث' not in html
    assert 'شؤون العاملين' not in html

    portal = client.get('/departments/accounting')
    assert portal.status_code == 200
    portal_html = portal.get_data(as_text=True)
    assert 'href="/revenues?department=accounting"' in portal_html
    assert 'href="/reports/revenues?department=accounting"' in portal_html
    assert 'href="/expenses"' not in portal_html
    assert 'href="/reports/expenses"' not in portal_html
    assert client.get('/departments/maintenance').status_code == 403


def test_custom_user_without_grants_gets_safe_empty_state(client):
    with client.application.app_context():
        user = db.session.get(User, client._user_ids['viewer'])
        user.role = 'custom'
        user.permissions_extra = dump_permissions_extra([])
        db.session.commit()

    login_as(client, 'viewer')
    response = client.get('/home')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'لا توجد منصات متاحة لصلاحيات حسابك' in html
    assert '/departments/' not in html


def test_authenticated_root_redirects_to_home(client):
    base_url = 'https://app.liftcoreapp.com'
    with client.application.app_context():
        user = db.session.get(User, client._user_ids['admin'])
        session_version = int(user.session_version or 0)
    with client.session_transaction(base_url=base_url) as session:
        session['user_id'] = user.id
        session['session_version'] = session_version
        session['lang'] = 'ar'
    response = client.get(
        '/',
        base_url=base_url,
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert '/home' in (response.headers.get('Location') or '')


def test_marketing_portal_lists_sales_links(client):
    login_as(client, 'admin')
    portal = client.get('/departments/marketing')
    assert portal.status_code == 200
    html = portal.get_data(as_text=True)
    assert 'منصة التسويق والمبيعات' in html
    assert '/sales/?department=marketing' in html
    assert '/sales/maintenance-quotes?department=marketing' in html
    assert '/elevator-estimates?department=marketing' in html

    sales_page = client.get('/sales/?department=marketing')
    assert sales_page.status_code == 200
    sales_html = sales_page.get_data(as_text=True)
    assert 'data-department="marketing"' in sales_html
    assert 'التسويق والمبيعات' in sales_html


def test_department_customer_and_contract_scopes_are_labeled(client):
    login_as(client, 'admin')

    maintenance_clients = client.get('/clients?scope=maintenance')
    assert maintenance_clients.status_code == 200
    assert 'عملاء الصيانة' in maintenance_clients.get_data(as_text=True)
    assert 'var CLIENT_SCOPE = "maintenance"' in maintenance_clients.get_data(as_text=True)

    installation_contracts = client.get('/contracts?scope=installation&z=4')
    assert installation_contracts.status_code == 200
    contracts_html = installation_contracts.get_data(as_text=True)
    assert 'عقود التركيبات والتحديث' in contracts_html
    assert 'var CONTRACT_SCOPE = "installation"' in contracts_html


def test_department_scopes_filter_clients_and_contracts_by_type(client):
    """عملاء/عقود الصيانة منفصلون عن التركيبات حسب نوع العقد."""
    from datetime import date, timedelta

    from models import Contract, Customer, db

    with client.application.app_context():
        oid = db.session.get(Customer, 1).organization_id if db.session.get(Customer, 1) else None
        if oid is None:
            from models import Organization
            oid = Organization.query.filter_by(slug='default').first().id
        maint_cust = Customer(organization_id=oid, code='C-M01', name='عميل صيانة فقط', status='نشط')
        inst_cust = Customer(organization_id=oid, code='C-I01', name='عميل تركيب فقط', status='نشط')
        both_cust = Customer(organization_id=oid, code='C-B01', name='عميل بالنوعين', status='نشط')
        none_cust = Customer(organization_id=oid, code='C-N01', name='بدون عقود', status='نشط')
        db.session.add_all([maint_cust, inst_cust, both_cust, none_cust])
        db.session.flush()
        start = date.today()
        end = start + timedelta(days=365)
        db.session.add_all([
            Contract(
                organization_id=oid, code='CN-00091', customer_id=maint_cust.id,
                contract_type='عقد صيانة', start_date=start, end_date=end, status='نشط', value=1000,
            ),
            Contract(
                organization_id=oid, code='CI-00091', customer_id=inst_cust.id,
                contract_type='عقد تركيب', start_date=start, end_date=end, status='نشط', value=5000,
            ),
            Contract(
                organization_id=oid, code='CN-00092', customer_id=both_cust.id,
                contract_type='عقد ضمان', start_date=start, end_date=end, status='نشط', value=800,
            ),
            Contract(
                organization_id=oid, code='CI-00092', customer_id=both_cust.id,
                contract_type='عقد تحديث', start_date=start, end_date=end, status='نشط', value=3000,
            ),
        ])
        db.session.commit()

    login_as(client, 'admin')

    maint_html = client.get('/clients?scope=maintenance').get_data(as_text=True)
    assert 'C-M01' in maint_html
    assert 'C-B01' in maint_html
    assert 'C-I01' not in maint_html
    assert 'C-N01' not in maint_html

    inst_html = client.get('/clients?scope=installation').get_data(as_text=True)
    assert 'C-I01' in inst_html
    assert 'C-B01' in inst_html
    assert 'C-M01' not in inst_html
    assert 'C-N01' not in inst_html

    maint_contracts = client.get('/contracts?scope=maintenance&z=4').get_data(as_text=True)
    assert 'CN-00091' in maint_contracts
    assert 'CN-00092' in maint_contracts
    assert 'CI-00091' not in maint_contracts
    assert 'CI-00092' not in maint_contracts

    inst_contracts = client.get('/contracts?scope=installation&z=4').get_data(as_text=True)
    assert 'CI-00091' in inst_contracts
    assert 'CI-00092' in inst_contracts
    assert 'CN-00091' not in inst_contracts
    assert 'CN-00092' not in inst_contracts


def test_department_css_lets_tables_fill_the_workspace():
    from pathlib import Path

    css = Path('static/liftcore-departments.css').read_text(encoding='utf-8')
    content_rule = css.split('body:has(#sidebar .department-nav-marker) .main > .content {', 1)[1]
    content_rule = content_rule.split('}', 1)[0]
    assert 'max-width: none' in content_rule
    assert 'max-width: 1380px' not in content_rule
    assert 'min-height: 52vh' in css
    assert 'max-height: none !important' in css
    assert 'body:not(:has(.department-nav-marker))' in Path('static/liftcore-shell.css').read_text(encoding='utf-8')
    assert '.department-tabs-title' in css
    assert 'html.lc-layout-topnav body:has(#sidebar .department-nav-marker)' in css
    assert 'justify-content: flex-start !important' in css
    assert 'justify-content: center' not in css
    assert '#c9a14a' not in css
