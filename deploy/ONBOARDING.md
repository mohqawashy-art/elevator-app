# LiftCore — Onboarding عميل جديد

> **ملاحظة:** `jama.liftcoreapp.com` = **بيئة اختبار (demo)** وليس عميلاً مدفوعاً.  
> العميل الحقيقي الجديد يُسجَّل عبر `/signup` بعد Multi-Tenant (`docs/MULTI-TENANT.md`).

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
- **`/etc/liftcore/platform.env`** — على الأقل:
  ```env
  SECRET_KEY=<مولّد عشوائي 32+ حرف>
  LIFTCORE_HTTPS=1
  GOOGLE_MAPS_API_KEY=<اختياري>
  ```
  توليد: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
  تحقق: `bash deploy/check_platform_env.sh`
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

### إعداد تشغيلي كامل (مرة واحدة على السيرفر)

```bash
cd ~/liftcore/elevator-app
bash deploy/setup_production_ops.sh
# أو: bash deploy/install.sh ops
bash deploy/check_production_ops.sh
python scripts/verify_production_ops.py --url https://client.liftcoreapp.com
```

أضف `SENTRY_DSN` في `/etc/liftcore/platform.env` ثم `sudo systemctl restart liftcore`.

### بريد المنصة (Resend)

انظر الدليل الكامل: [`deploy/MAIL.md`](MAIL.md)

```env
MAIL_API_KEY=re_...
MAIL_FROM=LiftCore <noreply@liftcoreapp.com>
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
| جما demo (اختبار QA فقط — ليس عميل B2B) | `scripts/reset_jama_demo.py` |

## 4. قرارات المنتج (ثابتة حتى P3)

| الميزة | الوضع |
|--------|--------|
| SaaS / الباقة | مخفي — بيع B2B مخصص |
| ZATCA | QR Phase 1 فقط على الطباعة |
| WhatsApp | روابط wa.me يدوية |
| موديول التركيب | `LIFTCORE_INSTALL_MODULE=1` على السيرفر |
| PIN بوابة الفني | `deploy/FIELD-PIN.md` |
