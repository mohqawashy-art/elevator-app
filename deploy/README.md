# رفع LiftCore على السيرفر

> **نقطة الدخول الموحّدة:** `bash deploy/install.sh help`  
> **محلياً (Windows):** `run_local.bat`  
> **Onboarding:** `deploy/ONBOARDING.md`

السيرفر: **https://app.liftcoreapp.com**  
الإنتاج: **Hetzner** `2.29.6.41` (CX43 · Falkenstein) — Cloudflare + SSL  
سجل النقل: [`deploy/hetzner/README.md`](hetzner/README.md) — GCP أُلغي أغسطس 2026  
الكود على: **https://github.com/mohqawashy-art/elevator-app**

### تثبيت تطبيق الإدارة (جوال / تابلت)

1. افتح **https://app.liftcoreapp.com/login** وسجّل الدخول
2. **iPhone:** Safari → مشاركة → إضافة إلى الشاشة الرئيسية
3. **Android:** Chrome → تثبيت التطبيق
4. الاسم: **LiftCore** — يفتح لوحة التحكم مباشرة

| الجهاز | التخطيط |
|--------|---------|
| جوال | بطاقات عمودين، قائمة ☰ |
| تابلت | 3 أعمدة، ساعة في الهيدر |
| كمبيوتر | شريط علوي كامل |

تطبيق **الفني** منفصل: `/field/login`

### بعد كل `git push` على `main`

الإنتاج **لا يتحدّث تلقائياً** إلا إذا فُعِّل cron التحديث (أسفل). وإلا SSH على Hetzner:

```bash
cd ~/liftcore/elevator-app && bash deploy/server_update_now.sh
```

تحقق محلياً قبل الرفع:

```bash
python scripts/qa_preflight.py --e2e --url https://app.liftcoreapp.com
```

---

## الطريقة 1 — SSH على Hetzner

```bash
ssh info@2.29.6.41
cd ~/liftcore/elevator-app
bash deploy/server_update_now.sh
```

أو:

```bash
cd ~/liftcore/elevator-app 2>/dev/null || cd /var/www/elevator-app
bash deploy/install.sh update
```

---

## الطريقة 2 — من جهازك (Windows)

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

> يجب أن يكون مفتاح SSH الخاص بك مضافاً على السيرفر (مستخدم `info`).

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

**تفعيل مرة واحدة** — SSH على Hetzner:

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

---

## فحص سريع للسيرفر

```bash
bash ~/liftcore/elevator-app/deploy/hetzner/status.sh
bash ~/liftcore/elevator-app/deploy/check_production_ops.sh
curl -s https://app.liftcoreapp.com/api/health
```
