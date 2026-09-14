"""عروض التسعير تبقى في المبيعات ولا تظهر في مشاريع التركيب."""
from installation.models import InstallProject, InstallQuotation, db
from installation.project_scope import (
    is_sales_stage_install_project,
    operational_install_projects_query,
)
from tenant_scope import assign_organization
from tests.conftest import login_as


def _make_pricing_project(*, code='PRJ-SCOPE1', status='تسعير'):
    from models import Organization

    org = Organization.query.filter_by(slug='default').first()
    project = InstallProject(
        organization_id=org.id,
        code=code,
        title='عرض تحت التسعير',
        status=status,
    )
    assign_organization(project)
    db.session.add(project)
    db.session.flush()
    quote = InstallQuotation(
        organization_id=org.id,
        code='Q-SCOPE1',
        project_id=project.id,
        status='مسودة',
        grand_total=100000,
    )
    assign_organization(quote)
    db.session.add(quote)
    db.session.commit()
    return project.id, quote.id


def test_sales_stage_project_hidden_from_projects_list(client):
    login_as(client, role='admin')
    with client.application.app_context():
        pid, _ = _make_pricing_project()

    page = client.get('/installation/projects')
    assert page.status_code == 200
    assert f'/installation/projects/{pid}'.encode() not in page.data


def test_sales_stage_project_detail_redirects_to_sales_quote(client):
    login_as(client, role='admin')
    with client.application.app_context():
        pid, qid = _make_pricing_project()

    resp = client.get(f'/installation/projects/{pid}', follow_redirects=False)
    assert resp.status_code in (302, 303)
    loc = resp.headers.get('Location') or ''
    assert f'/installation/projects/{pid}/quote' in loc
    assert f'quotation_id={qid}' in loc or f'quotation_id={qid}&' in loc.replace('?', '&')


def test_accepted_project_appears_in_projects_list(client):
    login_as(client, role='admin')
    with client.application.app_context():
        pid, qid = _make_pricing_project(code='PRJ-SCOPE2')
        project = db.session.get(InstallProject, pid)
        quote = db.session.get(InstallQuotation, qid)
        quote.status = 'مقبول'
        project.accepted_quotation_id = quote.id
        project.status = 'عقد'
        db.session.commit()

    with client.application.app_context():
        assert operational_install_projects_query().filter_by(id=pid).count() == 1

    page = client.get('/installation/projects')
    assert page.status_code == 200
    assert f'/installation/projects/{pid}'.encode() in page.data


def test_is_sales_stage_install_project_rules(client):
    from models import Organization

    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-SCOPE3',
            title='test',
            status='تسعير',
        )
        assert is_sales_stage_install_project(project) is True
        project.status = 'عقد'
        assert is_sales_stage_install_project(project) is False
        project.status = 'تسعير'
        project.accepted_quotation_id = 99
        assert is_sales_stage_install_project(project) is False
