# بيئات LiftCore — ثلاثة مجلدات منفصلة

> **قاعدة:** كل بيئة لها مجلد git خاص، فرع خاص، خدمة systemd خاصة، وقاعدة بيانات خاصة.
> **ممنوع** `cp` / `rsync` / `gcp_update.sh` بين البيئات.

| البيئة | النطاق | مجلد الكود على السيرفر | الفرع | الخدمة | قاعدة البيانات |
|--------|--------|------------------------|-------|--------|----------------|
| **إنتاج** | app.liftcoreapp.com | `~/liftcore/elevator-app` | `main` | `liftcore` | PostgreSQL إنتاج |
| **جما (demo/QA)** | jama.liftcoreapp.com | `~/liftcore/jama-elevator-app` | `main` | `liftcore-jama` | `jama.db` |
| **تجربة (test)** | test.liftcoreapp.com | `~/liftcore/test-elevator-app` | `staging/department-hubs` | `liftcore-staging` | `liftcore_staging` |

## التشغيل على السيرفر

الإنتاج وجما يُحدَّثان تلقائياً من `main` عبر `deploy/auto_update.sh`.

**test لا يُحدَّث تلقائياً** — فقط يدوياً:

```bash
cd ~/liftcore/test-elevator-app
git pull --ff-only origin staging/department-hubs
sudo bash deploy/staging/deploy_staging.sh
```

## أول تثبيت test (مرة واحدة)

```bash
cd ~/liftcore/elevator-app
git pull --ff-only origin main
bash deploy/staging/provision_test_clone.sh
sudo bash deploy/staging/bootstrap_staging.sh
```

## محلياً (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File deploy\clone_test_local.ps1
```

يفتح مجلداً منفصلاً: `D:\LiftCore\test-elevator-app` على فرع `staging/department-hubs`.

## نشر تعديلات test من Windows

```powershell
powershell -ExecutionPolicy Bypass -File deploy\push_test_staging.ps1
```

يرفع إلى فرع `staging/department-hubs` ثم يشغّل `deploy_staging.sh` على السيرفر.

## ما لا تفعله

| ❌ ممنوع | ✅ البديل |
|----------|-----------|
| `bash deploy/gcp_update.sh` في test | `sudo bash deploy/staging/deploy_staging.sh` |
| `bash deploy/sync_liftcore_with_jama.sh` لـ test | اعمل في `test-elevator-app` فقط |
| نسخ `platform.env` إلى staging | استخدم `/etc/liftcore/staging.env` |
| دمج test إلى `main` بدون مراجعة | PR من `staging/department-hubs` |

تفاصيل staging: [`deploy/staging/README.md`](staging/README.md)
