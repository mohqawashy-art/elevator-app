# Google Ads — صفحة الهبوط والتحويل

## روابط جاهزة

| الاستخدام | الرابط |
|-----------|--------|
| صفحة الإعلان (Final URL) | `https://liftcoreapp.com/start` |
| صفحة الشكر (تحويل) | `https://liftcoreapp.com/start/thanks` |
| مع تتبع حملة | `https://liftcoreapp.com/start?utm_source=google&utm_medium=cpc&utm_campaign=NAME` |

Google يضيف `gclid` تلقائياً عند تفعيل التتبع التلقائي للعلامات.

## متغيرات السيرفر (بعد إنشاء التحويل في Ads)

```bash
export LIFTCORE_GTAG_ID='G-XXXXXXXX'          # أو AW-XXXXXXXX من Google Ads / Analytics
export LIFTCORE_ADS_CONVERSION_ID='AW-XXXXXXXX'
export LIFTCORE_ADS_CONVERSION_LABEL='xxxxxx'  # من إعداد التحويل في Ads
```

بدون هذه المتغيرات الصفحة تعمل؛ لكن وسم التحويل لا يُطلق.

## مسار التحويل

1. الزائر يفتح `/start` (من الإعلان)
2. يرسل النموذج → يُحفظ الطلب في المنصة مع UTM/`gclid`
3. إعادة توجيه إلى `/start/thanks` مرة واحدة مع إطلاق `gtag('event','conversion',…)`

## في Google Ads

1. أنشئ حملة بحث (سعودية / عربية)
2. Final URL: `https://liftcoreapp.com/start`
3. أنشئ تحويل «إرسال نموذج» → انسخ ID والـ Label إلى المتغيرات أعلاه
4. بعد النشر: اختبر من رابط معاينة ثم راجع «التشخيصات» في التحويلات

## في المنصة

طلبات `/start` تظهر في `/platform/leads` مع المصدر وUTM تحت اسم الشركة.
