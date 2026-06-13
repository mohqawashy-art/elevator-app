# خرائط Google — إعداد المنصة (مرة واحدة لكل العملاء)

## المشكلة

- `app.liftcoreapp.com` → Google Maps ✅  
- `jama.liftcoreapp.com` → OpenStreetMap ❌  

**السبب الشائع:** مفتاح Google مسموح فقط لـ `app.liftcoreapp.com` — مش لـ `jama`.

**مش خلل في البرنامج** — إعداد Google Cloud + ملف منصة واحد على السيرفر.

---

## الحل (مرة واحدة — أي عميل جديد يشتغل تلقائياً)

### 1) Google Cloud Console

1. [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. افتح مفتاح **Maps JavaScript API** اللي LiftCore بيستخدمه
3. **Application restrictions → HTTP referrers**
4. أضف (مع القديم):

```
https://*.liftcoreapp.com/*
https://app.liftcoreapp.com/*
https://jama.liftcoreapp.com/*
http://localhost:5000/*
http://127.0.0.1:5000/*
```

> بعد كده أي عميل جديد `client.liftcoreapp.com` يشتغل **من غير** مفتاح جديد.

### 2) ملف منصة واحد على السيرفر (SSH)

```bash
sudo mkdir -p /etc/liftcore
sudo nano /etc/liftcore/platform.env
```

المحتوى (انسخ نفس المفتاح اللي LiftCore شغال بيه):

```
GOOGLE_MAPS_API_KEY=AIzaSy...نفس_المفتاح
LIFTCORE_HTTPS=1
```

```bash
sudo chmod 600 /etc/liftcore/platform.env
```

### 3) تحديث LiftCore + جما

```bash
# LiftCore الرئيسي
cd ~/liftcore/elevator-app
bash deploy/gcp_update.sh

# جما (عدّل المسار واسم الخدمة حسب السيرفر)
bash deploy/tenant_update.sh jama ~/jama/elevator-app
```

### 4) تحقق

- https://app.liftcoreapp.com/clients → خريطة Google  
- https://jama.liftcoreapp.com/clients → خريطة Google  
- Ctrl+Shift+R في المتصفح

---

## قاعدة للعملاء الجدد

| يُعدّ مرة واحدة | لكل عميل |
|-----------------|----------|
| مفتاح Google + `*.liftcoreapp.com` | DNS فرعي + قاعدة بيانات + خدمة systemd |
| `/etc/liftcore/platform.env` | **لا** مفتاح maps منفصل |

---

## لو لسه OSM

1. F12 → Console → ابحث عن `Google Maps JavaScript API error` أو `RefererNotAllowed`
2. تأكد خدمة `jama` تقرأ `platform.env`:

```bash
sudo systemctl show jama -p EnvironmentFiles
grep GOOGLE_MAPS /etc/liftcore/platform.env
```
