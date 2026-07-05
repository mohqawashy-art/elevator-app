# LiftCore — Onboarding عميل جديد

## 1. محلياً (التطوير)

```bat
run_local.bat
```

أو Linux/Mac:

```bash
bash deploy/install.sh local
```

يفتح: http://127.0.0.1:5001 — `admin` / `admin123` (غيّر كلمة المرور فوراً).

## 2. سيرفر جديد (عميل)

### المتطلبات
- Ubuntu VM + Python 3.11+
- nginx + systemd
- `SECRET_KEY` في `/etc/liftcore/platform.env`
- `GOOGLE_MAPS_API_KEY` (اختياري للخرائط)
- `SENTRY_DSN` (اختياري — تنبيه أخطاء الإنتاج عبر Sentry)

### خطوات

```bash
git clone https://github.com/mohqawashy-art/elevator-app.git ~/liftcore/CLIENT-app
cd ~/liftcore/CLIENT-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python init_db.py
```

### systemd
- خدمة: `liftcore-CLIENT`
- `Environment=LIFTCORE_HTTPS=1`
- `EnvironmentFile=/etc/liftcore/platform.env`
- موديول التركيب: `LIFTCORE_INSTALL_MODULE=1` (إن طُلب)

### تحديث لاحق

```bash
bash deploy/install.sh tenant liftcore-CLIENT ~/liftcore/CLIENT-app
```

### نسخ احتياطي

```bash
bash deploy/install.sh backup ~/liftcore/CLIENT-app
bash deploy/install.sh backup-cron ~/liftcore/CLIENT-app
```

### نسخ احتياطي و PostgreSQL
- SQLite: `bash deploy/backup_daily.sh`
- PostgreSQL: `DATABASE_URL=postgresql://... python scripts/backup_database.py`
- ترحيل من SQLite: `deploy/POSTGRES.md`

```bash
bash deploy/verify_deploy.sh https://client.liftcoreapp.com
```

## 3. استيراد بيانات

| الكيان | الأداة |
|--------|--------|
| عملاء | Excel من `/clients` → استيراد |
| مصاعد | `/elevators` → قالب Excel |
| عقود | scripts/import أو يدوي |
| جما demo | `scripts/reset_jama_demo.py` |

## 4. قرارات المنتج (ثابتة حتى P3)

| الميزة | الوضع |
|--------|--------|
| SaaS / الباقة | مخفي — بيع B2B مخصص |
| ZATCA | QR Phase 1 فقط على الطباعة |
| WhatsApp | روابط wa.me يدوية |
| موديول التركيب | `LIFTCORE_INSTALL_MODULE=1` على السيرفر |
| PIN بوابة الفني | `deploy/FIELD-PIN.md` |
