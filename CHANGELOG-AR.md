# سجل التحديثات — LiftCore
**التاريخ:** 8 يونيو 2025  
**المستودع:** https://github.com/mohqawashy-art/elevator-app — فرع `main`  
**آخر commit:** `b0c0ebd`

> نسخة بنفس المحتوى باسم إنجليزي لتسهيل `git pull` على السيرفر.

---

## تطبيق التحديث على السيرفر

```bash
cd ~/liftcore/elevator-app
git fetch origin main
git log -1 --oneline
# لازم يظهر: b0c0ebd Add Arabic release notes...
git pull origin main
sudo systemctl restart liftcore
```

**إذا `git pull` قال Already up to date لكن الموقع قديم:**
```bash
cd ~/liftcore/elevator-app
bash deploy/force_sync.sh
```

**تحقق من النسخة على الموقع:**
```
https://app.liftcoreapp.com/api/version
```

---

## ملخص سريع (آخر جلسة عمل)

| # | الموضوع | الحالة |
|---|---------|--------|
| 1 | إصلاح الرجوع وفتح تابات جديدة | ✅ |
| 2 | إغلاق تاب الطباعة عند الرجوع | ✅ |
| 3 | فورم طلب الشراء ثنائي اللغة (عربي + إنجليزي) | ✅ |
| 4 | تقرير طلب شراء إنجليزي فقط (EN) | ✅ |
| 5 | إصلاح التقرير الإنجليزي — بدون عربي في واجهة النظام | ✅ |
| 6 | إصلاح جدول الأعطال (وميض + صعوبة فتح التقرير) | ✅ |

---

## 1. التنقل والتابات

- ملف: `static/liftcore-nav.js`
- المحاضر تفتح في نفس التاب؛ الطباعة تُغلق عند الرجوع
- Commits: `2b62a9a`, `b0e1a75`

## 2. طلبات الشراء

- ثنائي اللغة: `/purchase-orders/{id}/print`
- إنجليزي فقط: `/purchase-orders/{id}/print-en` — زر **EN** في القائمة
- Commits: `fd427c5`, `ae55d2c`, `4c6365f`

## 3. الأعطال

- إلغاء النقر على الصف؛ التقرير من الأزرار فقط
- Commit: `4c6365f`

## 4. محضر الصيانة والتوقيعات (سابقاً)

- افتراضيات قائمة الفحص + توقيع رقمي
- Commits: `2781735` … `fb3acc8`

---

## ملفات مهمة

`static/liftcore-nav.js` · `templates/purchase-order-print.html` · `templates/faults.html` · `app.py`

---

## اختبار بعد النشر

- [ ] رجوع من محضر/طباعة بدون تاب مكرر
- [ ] طلب شراء EN + ثنائي اللغة
- [ ] تقرير عطل من الجدول بدون نافذة عرض

---

*LiftCore — mohqawashy-art/elevator-app*
