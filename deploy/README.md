# رفع LiftCore على السيرفر

> **نقطة الدخول الموحّدة:** `bash deploy/install.sh help`  
> **محلياً (Windows):** `run_local.bat`  
> **Onboarding:** `deploy/ONBOARDING.md`

السيرفر: **https://app.liftcoreapp.com**  
IP: `34.18.56.21`  
الكود على: **https://github.com/mohqawashy-art/elevator-app**

### بعد كل `git push` على `main`

الإنتاج **لا يتحدّث تلقائياً** إلا إذا فُعِّل cron التحديث (أسفل). وإلا من **GCP Console → SSH**:

```bash
cd ~/liftcore/elevator-app && bash deploy/gcp_update.sh
```

تحقق محلياً قبل الرفع:

```bash
python scripts/qa_preflight.py --e2e --url https://app.liftcoreapp.com
```

---

## الطريقة 1 — من Google Cloud (الأسهل)

1. افتح [Google Cloud Console](https://console.cloud.google.com/) → **Compute Engine** → **VM instances**
2. اضغط **SSH** بجانب السيرفر
3. الصق هذا الأمر:

```bash
cd ~/liftcore/elevator-app 2>/dev/null || cd /var/www/elevator-app
bash deploy/install.sh update
```

إذا ظهر خطأ في المسار، جرّب:

```bash
find ~ /var/www -maxdepth 3 -name elevator-app -type d 2>/dev/null
```

---

## الطريقة 2 — من جهازك (SSH)

```bat
deploy\deploy_to_server.bat
```

**مزامنة LiftCore مع جما** (نفس كود جما على app.liftcoreapp.com):

```bat
deploy\push_sync_liftcore.ps1
```

أو يدوياً على السيرفر:

```bash
bash ~/liftcore/elevator-app/deploy/sync_liftcore_with_jama.sh
```

أو يدوياً:

```bash
ssh USER@34.18.56.21
cd ~/liftcore/elevator-app
bash deploy/gcp_update.sh
```

> يجب أن يكون مفتاح SSH الخاص بك مضافاً على السيرفر (مستخدم `info` أو حسب إعداد GCP).

---

## بعد الرفع — تحقق

- https://app.liftcoreapp.com/inventory
- https://app.liftcoreapp.com/purchase-orders

يجب أن تعمل إضافة الصنف وطلب الشراء والتواريخ `dd/mm/yyyy`.

---

## إعادة تشغيل يدوية

```bash
sudo systemctl restart liftcore
sudo systemctl status liftcore
```

---

## التحديث التلقائي (موصى به)

بعد كل `git push` على `main`، السيرفر يسحب التحديث ويعيد تشغيل الخدمات **بدون SSH يدوي**.

**تفعيل مرة واحدة** — من GCP Console SSH:

```bash
cd ~/liftcore/elevator-app
git pull --ff-only origin main
bash deploy/install_auto_update_cron.sh
```

يفحص كل **5 دقائق**: `liftcore` + `liftcore-jama`.

**اختبار فوري:**

```bash
bash ~/liftcore/elevator-app/deploy/auto_update.sh
tail -30 ~/liftcore/logs/auto_update.log
```

**تحديث إجباري** (حتى بدون commit جديد):

```bash
bash ~/liftcore/elevator-app/deploy/auto_update.sh --force
```

**إلغاء التحديث التلقائي:**

```bash
crontab -l | grep -v liftcore-auto-update | crontab -
```
