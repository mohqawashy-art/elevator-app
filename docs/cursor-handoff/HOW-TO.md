# تسليم المحادثة — شغل ↔ بيت

Cursor **لا يزامن** الشات بين الأجهزة. هذا الملف يحل المشكلة يدوياً.

## في نهاية يوم الشغل

1. اطلب من المساعد: **«جهّز ملف نهاية اليوم»**
2. سيُحدَّث الملف: `docs/cursor-handoff/LATEST.md`
3. انسخ المجلد `docs/cursor-handoff/` إلى **USB** (أو OneDrive)
4. (اختياري) `git add` + `commit` + `push` إذا تفضّل GitHub بدل USB

## في البيت — فتح Cursor

1. انسخ `cursor-handoff` من USB إلى مشروع `elevator-app` (نفس المسار)
2. افتح المشروع في Cursor
3. ابدأ **محادثة جديدة** واكتب:

```
اقرأ docs/cursor-handoff/LATEST.md وكمل من حيث توقفنا.
المشروع: D:\elevator-app — branch main
```

4. (أفضل) **Attach** الملف `LATEST.md` في الشات

## محتوى الملف

- ماذا أنجزنا اليوم
- Commits على GitHub
- ما يحتاج deploy على السيرفر
- أقسام «مقفولة» vs «قيد المراجعة»
- المشاكل المفتوحة
- الخطوة التالية المقترحة

## ملاحظات

- **Ctrl+Shift+R** بعد كل deploy على الموقع
- Deploy: `git pull` ثم `sudo systemctl restart liftcore`
- هذا الملف **ملخص** — ليس نسخة كاملة لكل رسالة في الشات
