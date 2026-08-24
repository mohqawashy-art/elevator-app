# LiftCore staging

بيئة تجربة معزولة على نفس VM دون لمس خدمة أو قاعدة أو uploads الإنتاج.

## العزل

- الفرع: `staging/department-hubs`
- الخدمة: `liftcore-staging`
- المنفذ: `127.0.0.1:5003`
- النطاق: `test.liftcoreapp.com`
- قاعدة PostgreSQL: `liftcore_staging`
- البيئة: `/etc/liftcore/staging.env`
- البيانات: `/var/lib/liftcore-staging`
- الإصدارات: `/opt/liftcore-staging/releases`
- النسخ الاحتياطية: `/var/backups/liftcore-staging`

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

بعد دفع التغييرات إلى فرع التجربة فقط:

```bash
cd /tmp/liftcore-staging-bootstrap
git pull --ff-only origin staging/department-hubs
sudo bash deploy/staging/deploy_staging.sh
```

## التحقق

```bash
sudo STAGING_BASIC_AUTH='tester:PASSWORD' \
  bash deploy/staging/verify_staging.sh
```

لا تستخدم `deploy/gcp_update.sh` للـstaging لأنه يسحب `main` ويشغّل خدمة
الإنتاج. لا تنسخ `platform.env` ولا قاعدة الإنتاج إلى staging إلا بعد تنقية
بيانات العملاء والأسرار.
