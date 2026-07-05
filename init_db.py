"""
LiftCore — إنشاء قاعدة البيانات وإضافة مستخدم admin
init_db.py

شغّل مرة واحدة فقط:
    python init_db.py
"""

from app import app, db, hash_password
from models import User, Settings

with app.app_context():
    # إنشاء كل الجداول
    db.create_all()
    print("[OK] Database tables created")

    # إضافة مستخدم admin إذا مش موجود
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username   = 'admin',
            password_hash = hash_password('admin123'),
            full_name  = 'محمد القواشي',
            email      = 'admin@liftcore.sa',
            role       = 'admin',
            is_active  = True,
            must_change_password = True,
        )
        db.session.add(admin)
        print("[OK] Admin user created: admin / admin123")

    # إعدادات افتراضية
    if not Settings.query.first():
        settings = Settings(
            company_name    = 'شركة جما تقنية للمصاعد',
            company_name_en = 'Jama Elevator Technology Co.',
            phone           = '0500000000',
            email           = 'info@liftcore.sa',
            city            = 'مكة المكرمة',
            tax_pct         = 15,
            currency        = 'ر.س',
            language        = 'ar',
        )
        db.session.add(settings)
        print("[OK] Default settings added")

    db.session.commit()
    print("Database tables ready.")
    print("Run: python seed_data.py --reset   (to load demo data)")
    print("Login: http://127.0.0.1:5000  |  admin / admin123")
