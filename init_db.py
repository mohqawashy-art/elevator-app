"""
LiftCore — إنشاء قاعدة البيانات وإضافة مستخدم admin
init_db.py

شغّل مرة واحدة فقط:
    python init_db.py
"""

from app import app, db, hash_password
from models import Organization, Settings, User

with app.app_context():
    # إنشاء كل الجداول
    db.create_all()
    print("[OK] Database tables created")

    org = Organization.query.filter_by(slug='default').first()
    if not org:
        org = Organization(
            slug='default',
            name='LiftCore Default',
            status='active',
        )
        db.session.add(org)
        db.session.flush()
        print("[OK] Default organization created")

    # إضافة مستخدم admin إذا مش موجود
    if not User.query.filter_by(username='admin', organization_id=org.id).first():
        admin = User(
            username   = 'admin',
            password_hash = hash_password('admin123'),
            full_name  = 'محمد القواشي',
            email      = 'admin@liftcore.sa',
            role       = 'admin',
            is_active  = True,
            must_change_password = True,
            organization_id = org.id,
        )
        db.session.add(admin)
        print("[OK] Admin user created: admin / admin123")

    # إعدادات افتراضية
    if not Settings.query.filter_by(organization_id=org.id).first():
        settings = Settings(
            company_name    = 'شركة جما تقنية للمصاعد',
            company_name_en = 'Jama Elevator Technology Co.',
            phone           = '0500000000',
            email           = 'info@liftcore.sa',
            city            = 'مكة المكرمة',
            tax_pct         = 15,
            currency        = 'ر.س',
            language        = 'ar',
            organization_id = org.id,
        )
        db.session.add(settings)
        print("[OK] Default settings added")

    db.session.commit()
    print("Database tables ready.")
    print("Run: python seed_data.py --reset   (to load demo data)")
    print("Login: http://127.0.0.1:5000  |  admin / admin123")
