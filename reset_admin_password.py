"""Reset admin password for local dev."""
from app import app, db, hash_password
from models import User

NEW_PASSWORD = 'LiftCore2026'

with app.app_context():
    u = User.query.filter_by(username='admin').first()
    if not u:
        u = User(
            username='admin',
            full_name='مدير النظام',
            role='admin',
            is_active=True,
        )
        db.session.add(u)
    u.password_hash = hash_password(NEW_PASSWORD)
    u.must_change_password = False
    u.is_active = True
    db.session.commit()
    print(f'[OK] admin / {NEW_PASSWORD}')
