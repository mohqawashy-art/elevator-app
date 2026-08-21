# نقل LiftCore إلى Hetzner + Cloudflare

الإنتاج الحالي يبقى على GCP حتى نجاح الاختبار وتحويل DNS. لا تُوقف GCP في نفس يوم إنشاء السيرفر.

**المقاس الموصى به (أغسطس 2026):** Hetzner **CX43** — 8 vCPU / 16 GB / 160 GB — منطقة **Falkenstein (FSN1)** — Ubuntu **24.04**.
بعد تعديل أسعار يونيو 2026 هذا المقاس يغطي الخطة (8/16) بسعر أقل بكثير من CCX المخصّص.

---

## المرحلة 0 — حساب Hetzner (مرة واحدة)

1. افتح [console.hetzner.cloud](https://console.hetzner.cloud) وسجّل حساباً.
2. **Security → SSH Keys** → أضف مفتاحك العام.
3. **Add Server:**
   - Location: Falkenstein
   - Image: Ubuntu 24.04
   - Type: **CX43**
   - SSH key: المفتاح الذي أضفته
   - Networking: IPv4 + IPv6
   - Name: `liftcore-prod`
4. انسخ الـ **IPv4** الظاهر بعد الإنشاء. هذا هو `NEW_IP`.
5. Firewall في لوحة Hetzner (اختياري إضافةً لـ UFW): اسمح 22 / 80 / 443 فقط.

من PowerShell على جهازك:

```powershell
ssh root@NEW_IP
```

---

## المرحلة 1 — تجهيز السيرفر

على السيرفر الجديد كـ `root`:

```bash
apt-get update && apt-get install -y git
git clone https://github.com/mohqawashy-art/elevator-app.git /tmp/liftcore-src
bash /tmp/liftcore-src/deploy/hetzner/bootstrap.sh
```

إن كان المستودع خاصاً: أضف Deploy Key في GitHub ثم `GIT_URL=git@github.com:mohqawashy-art/elevator-app.git bash ...`

بعد الاكتمال:

```bash
bash /home/info/liftcore/elevator-app/deploy/hetzner/status.sh
curl http://NEW_IP/api/health
```

اختبار الواجهة قبل DNS — في `C:\Windows\System32\drivers\etc\hosts` كمسؤول:

```
NEW_IP  app.liftcoreapp.com jama.liftcoreapp.com
```

ثم https://app.liftcoreapp.com/login (تحذير الشهادة متوقع).

---

## المرحلة 2 — نسخ البيانات من GCP

على GCP (لا يوقف الموقع):

```bash
cd ~/liftcore/elevator-app && git pull --ff-only origin main
bash deploy/hetzner/export_from_gcp.sh
```

انقل الملف إلى السيرفر الجديد من جهازك:

```powershell
scp info@34.18.56.21:~/liftcore/migration-export-*.tar.gz .
scp .\migration-export-*.tar.gz info@NEW_IP:/home/info/
```

ثم على السيرفر الجديد:

```bash
sudo bash /home/info/liftcore/elevator-app/deploy/hetzner/import_to_new.sh /home/info/migration-export-YYYYMMDD-HHMMSS.tar.gz
sudo -u info bash /home/info/liftcore/elevator-app/deploy/install_backup_cron.sh /home/info/liftcore/elevator-app
```

تحقق: تسجيل دخول المستأجر، الشعارات، المرفقات.

---

## المرحلة 3 — Cloudflare (توجيه فقط — بدون نقل ملكية الدومين)

1. حساب Cloudflare → Add site → `liftcoreapp.com`.
2. الخطة: **Free** كافية للبداية (Pro اختياري لاحقاً).
3. Cloudflare يعرض nameservers. في Squarespace/Google Domains غيّر **Nameservers** فقط.
4. انقل سجلات DNS الحالية كما هي (A / CNAME / MX / TXT / SPF / DKIM). **لا تحذف MX** حتى لا ينقطع البريد.
5. قبل القطع: سجّل `app` و `jama` كـ **DNS only** (سحابة رمادية) نحو `NEW_IP` للتجربة، أو أبقِ GCP حتى نافذة الصيانة.

### نافذة القطع

1. نسخة GCP حديثة (`export_from_gcp.sh`) ثم `import_to_new.sh` مرة أخيرة.
2. A records: `app` و `jama` و `@` / `www` → `NEW_IP`.
3. Proxy: سحابة برتقالية بعد نجاح SSL.
4. SSL/TLS في Cloudflare: **Full (strict)**.
5. Origin Certificate: SSL/TLS → Origin Server → Create Certificate (15 سنة، `*.liftcoreapp.com` + apex).
6. على السيرفر:

```bash
sudo bash /home/info/liftcore/elevator-app/deploy/hetzner/enable_cloudflare_ssl.sh /path/origin.pem /path/origin.key
sudo bash /home/info/liftcore/elevator-app/deploy/hetzner/cloudflare-realip.sh
```

7. احذف سطر `hosts` من جهازك.
8. راقب 48 ساعة ثم أوقف VM على GCP.

---

## بعد القطع — النشر

المسار يبقى `~/liftcore/elevator-app` والخدمة `liftcore`:

```bash
cd ~/liftcore/elevator-app && \
rm -f .git/refs/remotes/origin/main.lock .git/refs/heads/main.lock 2>/dev/null; \
git fetch origin main && git reset --hard origin/main && \
sudo systemctl restart liftcore
```

تفعيل السحب التلقائي بعد استقرار القطع:

```bash
sudo -u info bash /home/info/liftcore/elevator-app/deploy/install_auto_update_cron.sh
```

---

## قائمة تحقق قبل إيقاف GCP

- [ ] نسخة احتياطية حديثة (DB + uploads)
- [ ] تسجيل دخول المستأجر على السيرفر الجديد
- [ ] الشعارات والمرفقات تظهر
- [ ] SSL يعمل بعد DNS (قفل أخضر عبر Cloudflare)
- [ ] النسخ الاحتياطي اليومي مفعّل (02:30 بتوقيت الرياض)
- [ ] MX/البريد لم يتغير
- [ ] اتفاق نافذة صيانة قصيرة مع المستأجر
