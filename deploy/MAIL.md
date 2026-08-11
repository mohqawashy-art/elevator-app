# LiftCore — ربط البريد (Resend)

المنصة ترسل عبر **Resend API** (`liftcore_mail.py`): ترحيب التسجيل ودعوات الانضمام.

## 1) حساب Resend

1. افتح [resend.com](https://resend.com) وسجّل الدخول.
2. **API Keys** → Create → انسخ المفتاح (`re_...`).
3. **Domains** → Add Domain → `liftcoreapp.com`.

## 2) سجلات DNS (Cloud DNS لمنطقة liftcoreapp.com)

أضف بالضبط السجلات التي يعرضها Resend (عادة):

| النوع | الاسم | القيمة |
|--------|--------|--------|
| TXT | `resend._domainkey` (أو كما يظهر) | مفتاح DKIM |
| TXT | `@` أو اسم SPF | يتضمن `include:amazonses.com` أو ما يطلبه Resend |

لا تحذف SPF/MX الحالية للبريد الوارد إن وُجدت — ادمج مع Resend حسب تعليماتهم.

بعد الإضافة: في Resend اضغط **Verify**. الحالة يجب أن تصبح **Verified**.

## 3) السيرفر — `/etc/liftcore/platform.env`

```env
MAIL_API_KEY=re_xxxxxxxx
MAIL_FROM=LiftCore <noreply@liftcoreapp.com>
```

ثم:

```bash
bash deploy/check_platform_env.sh
sudo systemctl restart liftcore
# إن وُجدت خدمة جما منفصلة:
# sudo systemctl restart liftcore-jama
```

## 4) اختبار إرسال

من السيرفر (داخل مجلد التطبيق + venv):

```bash
cd ~/liftcore/elevator-app
source .venv/bin/activate   # أو المسار الفعلي للـ venv
python - <<'PY'
from liftcore_mail import mail_configured, send_welcome_email
print('configured:', mail_configured())
# غيّر البريد لعنوانك
print(send_welcome_email('you@example.com', company_name='اختبار', slug='test', login_url='https://app.liftcoreapp.com'))
PY
```

أو من لوحة المشغّل: أعد إرسال دعوة انضمام (`/operator/onboarding/.../resend`).

## أعطال شائعة

| العرض | السبب |
|--------|--------|
| `mail_not_configured` | `MAIL_API_KEY` فارغ أو الخدمة لم تُعد تحميل `EnvironmentFile` |
| `domain is not verified` | DNS لم يتحقق بعد في Resend |
| Cloudflare 1010 | نادر — تأكد أن الكود يرسل `User-Agent` (موجود في `liftcore_mail.py`) |
