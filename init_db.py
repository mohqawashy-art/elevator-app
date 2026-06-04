"""
LiftCore — إنشاء قاعدة البيانات وإضافة مستخدم admin
init_db.py

شغّل مرة واحدة فقط:
    python init_db.py
"""

from app import app, db
from models import User, Settings

with app.app_context():
    # إنشاء كل الجداول
    db.create_all()
    print("✅ تم إنشاء جداول قاعدة البيانات")

    # إضافة مستخدم admin إذا مش موجود
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username   = 'admin',
            password_hash = 'admin123',   # غيّرها بعد أول تسجيل دخول
            full_name  = 'محمد القواشي',
            email      = 'admin@liftcore.sa',
            role       = 'admin',
            is_active  = True,
        )
        db.session.add(admin)
        print("✅ تم إنشاء المستخدم: admin / admin123")

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
        print("✅ تم إضافة الإعدادات الافتراضية")

    db.session.commit()
    print("\n🎉 قاعدة البيانات جاهزة!")
    print("   ادخل على: http://127.0.0.1:5000")
    print("   اسم المستخدم: admin")
    print("   كلمة المرور: admin123")
