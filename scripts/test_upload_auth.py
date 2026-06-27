"""اختبار حماية /static/uploads — جلسة مكتب، فني، ورفض بدون جلسة."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from app import app, db
from models import Customer, Technician, User


def _sample_upload_path():
    cust = Customer.query.filter(
        Customer.building_photo_path.isnot(None),
        Customer.building_photo_path != '',
    ).first()
    if cust and cust.building_photo_path:
        rel = cust.building_photo_path.replace('\\', '/').lstrip('/')
        if not rel.startswith('uploads/'):
            rel = 'uploads/' + rel.split('uploads/', 1)[-1] if 'uploads/' in rel else rel
        return rel, f'customer {cust.id} ({cust.name})', 'customer'
    tech = Technician.query.filter(Technician.photo_path.isnot(None)).first()
    if tech and tech.photo_path:
        rel = tech.photo_path.replace('\\', '/').lstrip('/')
        return rel, f'technician {tech.id} ({tech.code})', 'technician'
    return None, None, None


def _seed_test_upload():
    """إنشاء ملف ومسار تجريبي إن لم يوجد في قاعدة البيانات."""
    rel = 'uploads/test-auth/sample-building.png'
    _ensure_file(rel)
    cust = Customer.query.first()
    tech = Technician.query.first()
    if cust:
        cust.building_photo_path = rel
    if tech:
        if not tech.photo_path:
            tech.photo_path = f'uploads/technicians/{tech.id}/test-photo.png'
            _ensure_file(tech.photo_path)
        if not tech.signature_path:
            tech.signature_path = f'uploads/technicians/{tech.id}/test-sig.png'
            _ensure_file(tech.signature_path)
    db.session.commit()
    return rel, f'customer {cust.id if cust else "?"}', 'customer'


def _ensure_file(rel_path):
    full = os.path.join(ROOT, 'static', rel_path.replace('/', os.sep))
    if os.path.isfile(full):
        return full
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 64)
    return full


def main():
    results = []
    with app.app_context():
        rel, label, kind = _sample_upload_path()
        if not rel:
            rel, label, kind = _seed_test_upload()
        subpath = rel.split('uploads/', 1)[-1] if 'uploads/' in rel else rel
        _ensure_file(rel if rel.startswith('uploads/') else f'uploads/{subpath}')
        upload_url = f'/static/uploads/{subpath}'

        user = User.query.filter_by(is_active=True).first()
        tech = Technician.query.filter(
            Technician.photo_path.isnot(None),
        ).first() or Technician.query.first()

        print(f'Sample upload: {upload_url} ({label})')
        print(f'Office user: id={user.id if user else None} username={getattr(user, "username", None)}')
        print(f'Field tech: id={tech.id if tech else None} code={getattr(tech, "code", None)}')
        print()

        client = app.test_client()

        # 1) بدون جلسة — يجب الرفض
        r = client.get(upload_url, follow_redirects=False)
        ok_anon = r.status_code in (301, 302, 303, 307, 308, 401)
        results.append(('Anonymous direct URL rejected', ok_anon, r.status_code, r.headers.get('Location', '')))

        r2 = client.get(upload_url, follow_redirects=True)
        ok_anon_body = b'\x89PNG' not in (r2.data or b'')[:20]
        results.append(('Anonymous no PNG body after redirects', ok_anon_body, r2.status_code, ''))

        # 2) جلسة مكتب
        if user:
            with client.session_transaction() as sess:
                sess['user_id'] = user.id
            r = client.get(upload_url)
            ok_office = r.status_code == 200 and len(r.data or b'') > 0
            results.append(('Office session serves file', ok_office, r.status_code, len(r.data or b'')))

        # 3) جلسة فني
        if tech:
            with client.session_transaction() as sess:
                sess.clear()
                sess['field_tech_id'] = tech.id
            r = client.get(upload_url)
            ok_field = r.status_code == 200 and len(r.data or b'') > 0
            results.append(('Field session serves file', ok_field, r.status_code, len(r.data or b'')))

        # 4) صفحة عملاء بجلسة مكتب (إن وُجد عميل بصورة)
        cust = Customer.query.filter(
            Customer.building_photo_path.isnot(None),
            Customer.building_photo_path != '',
        ).first()
        if user and cust:
            with client.session_transaction() as sess:
                sess['user_id'] = user.id
            r = client.get('/clients')
            has_photo_url = b'building_photo_url' in (r.data or b'') or b'/static/uploads/' in (r.data or b'')
            results.append(('Clients page loads with office session', r.status_code == 200, r.status_code, has_photo_url))

        # 5) بوابة الفني — صورة الهيدر
        if tech:
            with client.session_transaction() as sess:
                sess.clear()
                sess['field_tech_id'] = tech.id
            r = client.get('/field')
            page_ok = r.status_code == 200
            has_upload_ref = b'/static/uploads/' in (r.data or b'')
            results.append(('Field portal has upload img src', page_ok and has_upload_ref, r.status_code, has_upload_ref))

            if tech.photo_path:
                photo_sub = tech.photo_path.replace('\\', '/').split('uploads/', 1)[-1]
                r_photo = client.get(f'/static/uploads/{photo_sub}')
                results.append(('Field tech photo URL', r_photo.status_code == 200, r_photo.status_code, len(r_photo.data or b'')))

            if tech.signature_path:
                sig_sub = tech.signature_path.replace('\\', '/').split('uploads/', 1)[-1]
                r_sig = client.get(f'/static/uploads/{sig_sub}')
                results.append(('Field tech signature URL', r_sig.status_code == 200, r_sig.status_code, len(r_sig.data or b'')))

    print('=== Results ===')
    all_ok = True
    for name, ok, detail, extra in results:
        status = 'PASS' if ok else 'FAIL'
        if not ok:
            all_ok = False
        print(f'{status}: {name} | {detail} | {extra}')

    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
