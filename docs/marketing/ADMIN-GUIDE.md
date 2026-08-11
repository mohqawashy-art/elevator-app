# LiftCore — دليل مدير النظام (L2)

> **مسودة قديمة جزئياً — تحديث تسويقي/تشغيلي لاحق.** للنشر والأمان الحالي راجع `deploy/` و`ROADMAP.md`.

**لدور admin — نشر، أمان، إعدادات**

## 1. الأدوار

| الدور | الصلاحيات |
|-------|-----------|
| **admin** | كامل + حذف + إعدادات + مستخدمون |
| **manager** | تشغيل يومي بدون إعدادات الشركة |
| **viewer** | قراءة فقط |

## 2. الإعدادات (`/settings`)

- بيانات الشركة: اسم، ضريبة، سجل، شعار، بنك
- **المستخدمون:** إضافة/تعطيل، أدوار
- **التوقيعات:** ممثل الشركة للطباعة
- **بوابة الفني:** PIN لكل فني — راجع `deploy/FIELD-PIN.md`
- **الخرائط:** مفتاح Google Maps API

## 3. النشر والتحديث

```bash
bash deploy/install.sh tenant SERVICE ~/app-path
bash deploy/verify_deploy.sh https://your-domain
bash deploy/gcp_update.sh   # على GCP
```

متغيرات مهمة في `/etc/liftcore/platform.env`:

- `SECRET_KEY` — عشوائي قوي
- `LIFTCORE_HTTPS=1`
- `SENTRY_DSN` (اختياري)
- `DATABASE_URL` (PostgreSQL اختياري — `deploy/POSTGRES.md`)

## 4. النسخ الاحتياطي

```bash
bash deploy/backup_daily.sh
# استعادة: deploy/REGRESSION_CHECKLIST.txt — E5
```

## 5. الأمان

- لا تستخدم `admin123` في الإنتاج
- فعّل قفل الجلسة (screensaver) للمكاتب المشتركة
- راجع `scripts/security_audit.py` دورياً

## 6. Alembic

```bash
LIFTCORE_ALEMBIC=1 python deploy/migrate_db.py upgrade
```

## 7. إصلاح cache الفواتير

```bash
python scripts/repair_billing_cache.py
# أو API admin: GET /api/admin/billing-cache/repair
```

## 8. الاختبارات قبل النشر

```bash
python -m pytest tests/ -q
npm run test:e2e
# deploy/REGRESSION_CHECKLIST.txt
```

## 9. موديول التركيب

`LIFTCORE_INSTALL_MODULE=1` في بيئة الخدمة — راجع `deploy/ONBOARDING.md`

## 10. i18n و API

- `docs/I18N.md` — استراتيجية الترجمة
- رسائل API: `liftcore_api_i18n.py`

---

*للطباعة: Ctrl+P → حفظ PDF*
