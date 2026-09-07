# LiftCore staging

بيئة تجربة معزولة على نفس VM دون لمس خدمة أو قاعدة أو uploads الإنتاج.

## العزل

- الفرع: `staging/department-hubs` (أو `STAGING_BRANCH=main` للنشر من main)
- الخدمة: `liftcore-staging`
- المنفذ: `127.0.0.1:5003`
- النطاق: `test.liftcoreapp.com`
- قاعدة PostgreSQL: `liftcore_staging` (**منفصلة تماماً عن `liftcore` الإنتاج**)
- البيئة: `/etc/liftcore/staging.env`
- البيانات: `/var/lib/liftcore-staging`
- الإصدارات: `/opt/liftcore-staging/releases`
- النسخ الاحتياطية: `/var/backups/liftcore-staging`

**مهم:** لا تنسخ قاعدة الإنتاج إلى staging. أي سكربت صيانة على staging يُشغَّل عبر:

```bash
sudo bash deploy/staging/run_staging_script.sh scripts/set_user_login.py --help
```

استعادة بيئة تجربة نظيفة (قبل أي نسخ من جما):

```bash
sudo bash deploy/staging/restore_clean_test.sh
```

الخدمة تضبط `LIFTCORE_ENV_FILE`، ولذلك لا يقرأ التطبيق
`/etc/liftcore/platform.env` أو مفاتيح الدفع والبريد الخاصة بالإنتاج.

## أول تثبيت

1. أنشئ DNS من `test.liftcoreapp.com` إلى IP الخادم.
2. على الخادم:

```bash
cd /tmp
git clone --branch staging/department-hubs --single-branch \
  https://github.com/mohqawashy-art/elevator-app.git liftcore-staging-bootstrap
cd liftcore-staging-bootstrap
sudo bash deploy/staging/bootstrap_staging.sh
```

3. شهادة الأصل (Cloudflare Origin) على 443 — لا تستخدم certbot إذا كان النطاق خلف Cloudflare Proxied.

بعد نجاح الصحة محلياً: في Cloudflare غيّر سجل A لـ `test` إلى IP السيرفر، ويفضّل **Proxied**.

## كل تحديث تجريبي

**لا تستخدم `STAGING_BRANCH=main`** إلا لاختبار تغييرات محددة من الإنتاج. الوضع الافتراضي للتجربة هو فرع `staging/department-hubs` (منصات الأقسام والواجهات المنفصلة).

```bash
sudo bash deploy/staging/deploy_staging.sh
```

استعادة كاملة لأواخر أغسطس (قاعدة + كود + واجهات) **بدون لمس جما أو الإنتاج**:

```bash
sudo bash deploy/staging/restore_august_test.sh
```

## التحقق

```bash
sudo STAGING_BASIC_AUTH='tester:PASSWORD' \
  bash deploy/staging/verify_staging.sh
```

لا تستخدم `deploy/gcp_update.sh` للـstaging لأنه يسحب `main` ويشغّل خدمة
الإنتاج. لا تنسخ `platform.env` ولا قاعدة الإنتاج إلى staging إلا بعد تنقية
بيانات العملاء والأسرار.
