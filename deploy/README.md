# رفع LiftCore على السيرفر

السيرفر: **https://app.liftcoreapp.com**  
IP: `34.18.56.21`  
الكود على: **https://github.com/mohqawashy-art/elevator-app**

---

## الطريقة 1 — من Google Cloud (الأسهل)

1. افتح [Google Cloud Console](https://console.cloud.google.com/) → **Compute Engine** → **VM instances**
2. اضغط **SSH** بجانب السيرفر
3. الصق هذا الأمر:

```bash
cd ~/liftcore/elevator-app 2>/dev/null || cd /var/www/elevator-app
bash deploy/gcp_update.sh
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
