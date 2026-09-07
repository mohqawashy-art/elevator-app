# LiftCore staging (test)

بيئة تجربة معزولة على نفس VM — **مجلد git منفصل** مثل `jama-elevator-app`،
دون لمس `elevator-app` (إنتاج) أو `jama-elevator-app`.

راجع أيضاً: [`deploy/ENVIRONMENTS.md`](../ENVIRONMENTS.md)

## العزل

| | إنتاج | جما | **test** |
|---|--------|-----|----------|
| مجلد الكود | `~/liftcore/elevator-app` | `~/liftcore/jama-elevator-app` | **`~/liftcore/test-elevator-app`** |
| الفرع | `main` | `main` | **`staging/department-hubs`** (أو `STAGING_BRANCH=main` للنشر من main) |
| الخدمة | `liftcore` | `liftcore-jama` | **`liftcore-staging`** |

- المنفذ: `127.0.0.1:5003`
- النطاق: `test.liftcoreapp.com`
- قاعدة PostgreSQL: `liftcore_staging` (**منفصلة تماماً عن `liftcore` الإنتاج**)
- البيئة: `/etc/liftcore/staging.env`
- البيانات: `/var/lib/liftcore-staging`
- الإصدارات (runtime): `/opt/liftcore-staging/releases`
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
2. على السيرفر:

```bash
cd ~/liftcore/elevator-app && git pull --ff-only origin main
bash deploy/staging/provision_test_clone.sh
sudo bash ~/liftcore/test-elevator-app/deploy/staging/bootstrap_staging.sh
```

**محلياً (Windows):**

```powershell
powershell -ExecutionPolicy Bypass -File deploy\clone_test_local.ps1
```

3. شهادة الأصل (Cloudflare Origin) على 443 — لا تستخدم certbot إذا كان النطاق خلف Cloudflare Proxied.

بعد نجاح الصحة محلياً: في Cloudflare غيّر سجل A لـ `test` إلى IP السيرفر، ويفضّل **Proxied**.

## كل تحديث تجريبي

**لا تستخدم `STAGING_BRANCH=main`** إلا لاختبار تغييرات محددة من الإنتاج. الوضع الافتراضي للتجربة هو فرع `staging/department-hubs` (منصات الأقسام والواجهات المنفصلة).

بعد دفع التغييرات إلى فرع `staging/department-hubs` فقط:

```bash
cd ~/liftcore/test-elevator-app
git pull --ff-only origin staging/department-hubs
sudo bash deploy/staging/deploy_staging.sh
```

من Windows:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\push_test_staging.ps1
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
