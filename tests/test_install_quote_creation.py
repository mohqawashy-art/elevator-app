"""منع إنشاء مشاريع تركيب تلقائياً دون تأكيد المستخدم."""
from installation.models import InstallProject, db
from tests.conftest import login_as


def _project_count():
    return InstallProject.query.count()


def test_install_quote_get_does_not_create_project(client):
    login_as(client, role='admin')
    with client.application.app_context():
        before = _project_count()

    resp = client.get('/sales/install/quotes/new')
    assert resp.status_code == 200
    assert 'تركيب مصعد جديد'.encode('utf-8') in resp.data

    with client.application.app_context():
        assert _project_count() == before


def test_install_quote_get_with_legacy_go_param_does_not_create_project(client):
    login_as(client, role='admin')
    with client.application.app_context():
        before = _project_count()

    resp = client.get('/sales/install/quotes/new?go=1&quote_kind=upgrade')
    assert resp.status_code == 200

    with client.application.app_context():
        assert _project_count() == before


def test_install_quote_post_creates_project(client):
    login_as(client, role='admin')
    with client.application.app_context():
        before = _project_count()
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        '/sales/install/quotes/new',
        data={
            'csrf_token': 'test-csrf',
            'quote_kind': 'new',
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        assert _project_count() == before + 1
        project = InstallProject.query.order_by(InstallProject.id.desc()).first()
        assert project is not None
        assert project.status == 'تسعير'
        assert 'من مبيعات التركيبات' in (project.notes or '')
