"""اختبار سياسة جلسة واحدة لكل مستخدم مكتب."""
from app import app, db, hash_password
from models import Organization, Settings, User


def _client_pair():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-not-default'
    app.config['SESSION_COOKIE_SECURE'] = False
    with app.app_context():
        db.engine.dispose()
        db.session.remove()
        db.drop_all()
        db.create_all()
        org = Organization(slug='default', name='Seat Org', status='active', plan='pro')
        db.session.add(org)
        db.session.flush()
        db.session.add(Settings(organization_id=org.id, company_name='Seat Org', tax_pct=15))
        db.session.add(User(
            organization_id=org.id,
            username='seat_user',
            password_hash=hash_password('SeatPass123!'),
            full_name='Seat User',
            role='admin',
            is_active=True,
            session_version=0,
        ))
        db.session.commit()
    return app.test_client(), app.test_client()


def test_second_login_kicks_first_session():
    a, b = _client_pair()
    r1 = a.post(
        '/login',
        data={'username': 'seat_user', 'password': 'SeatPass123!'},
        follow_redirects=False,
    )
    assert r1.status_code in (302, 303)

    # الجلسة الأولى ما زالت صالحة
    r = a.get('/dashboard', follow_redirects=False)
    assert r.status_code in (200, 302)

    # دخول من متصفح ثانٍ
    r2 = b.post(
        '/login',
        data={'username': 'seat_user', 'password': 'SeatPass123!'},
        follow_redirects=False,
    )
    assert r2.status_code in (302, 303)

    # الجلسة الأولى تُرفض وتُحوَّل لتسجيل الدخول
    r_old = a.get('/dashboard', follow_redirects=False)
    assert r_old.status_code in (302, 303)
    assert '/login' in (r_old.headers.get('Location') or '')

    # الجلسة الجديدة تعمل
    r_new = b.get('/dashboard', follow_redirects=False)
    assert r_new.status_code in (200, 302)
    loc = r_new.headers.get('Location') or ''
    assert '/login' not in loc
