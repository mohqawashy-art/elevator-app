# تسليم جلسة Cursor — LiftCore
**التاريخ:** 2026-06-10 (نهاية يوم الشغل)  
**المشروع:** `D:\elevator-app` — branch `main`  
**GitHub:** `github.com/mohqawashy-art/elevator-app`  
**الإنتاج:** `https://app.liftcoreapp.com`

---

## في البيت — ابدأ هنا

1. انسخ مجلد `docs/cursor-handoff/` من USB إلى `D:\elevator-app\docs\`
2. افتح Cursor على مشروع `elevator-app`
3. **محادثة جديدة** + Attach هذا الملف، أو اكتب:

```
اقرأ docs/cursor-handoff/LATEST.md وكمل من حيث توقفنا.
```

4. عدّل السطر الأخير: Deploy [نعم/لا] — القسم الحالي: [...]

---

## ما تم اليوم (تقني)

| Commit | الموضوع |
|--------|---------|
| `be4c746` | **حفظ صورة المبنى** — المعاينة كانت تمسح الملف قبل الإرسال |
| `3c57be8` | **كارت العميل** — `esc()` ناقصة؛ الكود قابل للنقر |
| `d5cd277` | **صورة المبنى** — لا تظهر في أعلى الكارت؛ فقط من «صورة المبنى» |
| `8963f89` | **EN** — نوافذ مخفية + تركيز خاطئ على inputs |
| `1add43e` | **مصاعد** — خريطة النموذج → OpenStreetMap إذا فشل Google |

**آخر commit على GitHub:** `1add43e`

### Deploy على السيرفر

```bash
cd /path/to/elevator-app
git pull
sudo systemctl restart liftcore
```

ثم **Ctrl+Shift+R** في المتصفح.

> **Deploy على السيرفر:** [ ] نعم  [ ] لا — (عبّي في البيت)

---

## ما تم اليوم (تنظيم + عمل)

- مناقشة **تقييم أسلوب الشغل** — المراجعة قسم بقسم صحيحة؛ الرجوع غالباً **regression** من ملفات مشتركة
- حل **مزامنة الشات** شغل ↔ بيت: ملف `LATEST.md` + USB (هذا الملف)
- إنشاء مجلد `docs/cursor-handoff/` + `HOW-TO.md`

### ⚠️ لم يُرفع على GitHub بعد

```
docs/cursor-handoff/LATEST.md
docs/cursor-handoff/HOW-TO.md
```

**انسخهم على USB اليوم.** (اختياري لاحقاً: `git add docs/cursor-handoff` + push)

---

## حالة الأقسام

| القسم | الحالة | اختبر بعد deploy |
|-------|--------|------------------|
| **العملاء** | قريب من الإغلاق | حفظ + كارت + اسم/كود + صورة (عند الطلب) + EN |
| **المصاعد** | قيد المراجعة | إضافة مصعد + خريطة OSM + اختيار عميل |
| **Dashboard** | لم يُبدأ إغلاقه | التالي بعد إقفال عملاء/مصاعد |
| **عقود / EN عام** | جزئي | أي تعديل i18n → راجع 2–3 صفحات |

---

## checklist اختبار سريع (بعد deploy)

### عملاء `/clients`
- [ ] إضافة عميل + صورة → تُحفظ على السيرفر
- [ ] ضغط الاسم/الكود → يفتح الكارت
- [ ] «صورة المبنى» من قسم الموقع فقط
- [ ] EN: لا وميض ولا «input مضغوط»

### مصاعد `/elevators`
- [ ] إضافة مصعد → خريطة (OSM إذا Google فاشل)
- [ ] اختيار عميل يملأ المدينة/الموقع

---

## مشاكل مفتوحة

1. **Google Maps API** — خطأ في الواجهة؛ OSM بديل في map picker
2. **Regression** — تعديل `liftcore-i18n.js` / `client_map_picker.js` قد يمس صفحات أخرى
3. **«مفيش تغيير»** → غالباً deploy أو كاش — ليس فشل الكود

---

## ملفات حساسة (أي لمس = راجع)

- `static/liftcore-i18n.js` — v23 في partials
- `static/liftcore-display.js`
- `static/client_map_picker.js`
- `templates/partials/google_maps_head.html`
- `templates/clients.html`
- `templates/elevators.html`

---

## سياق للمساعد (لا تعيد الشرح)

- المستخدم: **صاحب مشروع live** — يراجع من الهد، كل زر، ثم يقفل القسم
- Deploy **يدوي** — الوكيل لا SSH للسيرفر
- بعد كل fix: اذكر **ما يجب إعادة اختباره** و**هل يمس أقساماً مقفولة**
- مسار الشغل: `D:\elevator-app` — OneDrive/Documents في workspace Cursor

---

## الخطوة التالية (بكرة / في البيت)

1. [ ] Deploy حتى `1add43e` على السيرفر
2. [ ] checklist عملاء + مصاعد أعلاه
3. [ ] إن OK → **Dashboard**
4. [ ] نهاية الجلسة: «جهّز ملف نهاية اليوم»

---

## رسالة جاهزة للمساعد (نسخ ولصق)

```
نكمل LiftCore. اقرأ docs/cursor-handoff/LATEST.md (مرفق).
آخر commit: 1add43e على main.
Deploy على السيرفر: [نعم/لا].
القسم الحالي: [عملاء / مصاعد / dashboard].
المطلوب: [اكتب هنا].
```

---

*آخر تحديث: نهاية يوم 2026-06-10 — انسخ هذا الملف + HOW-TO.md على USB.*
