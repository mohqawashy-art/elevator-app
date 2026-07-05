# LiftCore — خارطة الإصلاحات قبل التسويق

**آخر تحديث:** 23 يونيو 2026  
**القاعدة:** نُغلق كل بند نهائياً — لا نعود له إلا إذا تغيّر scope التسويق.

---

## حالة التقدّم

| المرحلة | الوصف | الحالة |
|---------|--------|--------|
| **P0** | أمان + صلاحيات + استقرار حرج | ✅ 100% |
| **P1** | QA + نشر + ميزات ناقصة | ✅ 100% |
| **P2** | UX + i18n + مواد تسويق | ⏳ |
| **P3** | SaaS / ZATCA كامل / Offline (حسب الوعد) | ⏳ |

**Definition of Done للتسويق:** P0 = 100% · P1 ≥ 90% · سيناريو جما بدون blockers

---

## P0 — حرج (لا تسويق قبل الإغلاق)

### A. البنية المركزية (مرة واحدة — لا تكرار)
- [x] `ROADMAP.md` — هذه الوثيقة
- [x] `liftcore_rbac.py` — صلاحيات admin / manager / viewer
- [x] `liftcore_security.py` — CSRF، rate limit، env، كلمات مرور، uploads
- [x] `audit_log.py` — سجل تدقيق
- [x] `static/liftcore-csrf.js` — CSRF لـ fetch
- [x] `tests/test_rbac.py` + `tests/test_security.py`

### B. الأمان والمصادقة
- [x] B1 — تفعيل viewer: منع POST/PUT/PATCH/DELETE (403)
- [x] B2 — manager: منع إعدادات الشركة / المستخدمين / التوقيعات (admin فقط)
- [x] B3 — إلزام `SECRET_KEY` قوي في الإنتاج (`LIFTCORE_HTTPS=1`)
- [x] B4 — `must_change_password` + منع كلمات مرور افتراضية
- [x] B5 — CSRF لكل الطلبات الم mutating (ما عدا `/field/*`)
- [x] B6 — Rate limiting على `/login` و `/field/login`
- [x] B7 — سياسة كلمة مرور: 8+ أحرف + قائمة محظورة
- [x] B8 — رفع ملفات: حد حجم + MIME
- [x] B9 — مراجعة IDOR / XSS (`scripts/security_audit.py`)

### C. الصلاحيات والحذف
- [x] C1 — `enforce_admin_delete()` على كل routes الحذف (تدقيق)
- [x] C2 — أزرار حذف `.lc-admin-delete` لغير admin
- [x] C3 — سجل تدقيق: حذف + إعدادات + تغيير كلمة مرور
- [x] C4 — سجل تدقيق: تسجيل دخول فاشل

### D. UI حرج
- [x] D1 — modal-overlay مخفي حتى `.open`
- [x] D2 — تدقيق z-index (مركزي في `liftcore-shell.css` z-index:9000)
- [x] D3 — صفر أخطاء Console (صفحات رئيسية) — smoke tests + فحص يدوي

### I. UX (بدأنا مبكراً)
- [x] I6 — إخفاء أزرار الإضافة/التعديل لـ viewer (`liftcore-viewer-ui.js`)

---

## P1 — ضروري (قبل أول عميل مدفوع)

### E. الاختبارات
- [x] E1 — pytest: login, CRUD عميل, فاتورة, زيارة, حذف admin + smoke + whatsapp
- [x] E2 — Playwright: 5–8 سيناريوهات
- [x] E3 — GitHub Actions CI
- [x] E4 — Checklist regression قبل كل نشر
- [x] E5 — اختبار restore من backup

### F. النشر والتشغيل
- [x] F1 — `deploy/install.sh` موحّد + أرشفة السكربتات القديمة
- [x] F2 — Runbook onboarding عميل جديد
- [x] F3 — cron backup يومي + retention 30 يوم
- [x] F4 — `/api/health` (DB + disk + version)
- [x] F5 — Sentry أو تنبيه أخطاء (`liftcore_monitoring.py`, `SENTRY_DSN`)
- [x] F6 — `.env.example` كامل
- [x] F7 — PostgreSQL path للإنتاج (`liftcore_database.py`, `deploy/POSTGRES.md`, ترحيل SQLite)
- [x] F8 — verify tenant (`deploy/verify_deploy.sh`)

### G. ميزات ناقصة
- [x] G1 — `report-parts.html` + route `/reports/parts-billing`
- [ ] G2 — `/api/translate`: **مؤجّل P2** (i18n ثابت كافٍ للتسويق)
- [x] G3 — WhatsApp QA: رسائل خطأ عربية + pytest `test_whatsapp.py`
- [x] G4 — قرار موديول التركيب (ONBOARDING: `LIFTCORE_INSTALL_MODULE=1`)
- [x] G5 — قرار تبويب الباقة SaaS (مخفي — B2B مخصص، موثّق في ONBOARDING)
- [x] G6 — Alembic migrations (`migrations/`, `deploy/migrate_db.py`)
- [x] G7 — consistency cache عقود/فواتير (`billing_consistency.py`, `scripts/repair_billing_cache.py`)

### H. المالية
- [x] H1 — ZATCA QR QA كل أنواع الفواتير (`tests/test_zatca_qr.py`)
- [x] H2 — كشف حساب عميل QA (فواتير + سندات + إيرادات)
- [x] H3 — تقرير فروقات مالية (`/reports/billing-discrepancies`)

---

## P2 — Polish

### I. UX
- [ ] I1 — توحيد modal CSS → `liftcore-shell.css`
- [ ] I2 — responsive 768/480 كل الصفحات
- [ ] I3 — empty states + loading + toast موحّد
- [ ] I4 — Google Maps deprecated APIs
- [x] I5 — QA طباعة كل المستندات (`tests/test_print_documents.py`)
- [ ] I6 — إخفاء أزرار الإضافة/التعديل لـ viewer في الواجهة

### J. i18n
- [ ] J1 — مراجعة EN كاملة
- [ ] J2 — رسائل API ثنائية اللغة
- [ ] J3 — قرار ترجمة المحتوى الديناميكي

### K. بوابة الفني
- [ ] K1 — QA iOS/Android
- [ ] K2 — توثيق PIN setup
- [ ] K3 — Offline PWA (P3 إن وُعد به)

### L. مواد تسويق
- [ ] L1 — دليل مستخدم PDF
- [ ] L2 — دليل مدير نظام
- [ ] L3 — فيديو demo
- [ ] L4 — One-pager (ما يشمل / ما لا يشمل)
- [ ] L5 — Privacy + Terms

---

## P3 — حسب الوعد التسويقي فقط

- [ ] SaaS multi-tenant + billing
- [ ] ZATCA Phase 2 (XML + clearance)
- [ ] WhatsApp Business API + تذكيرات مجدولة
- [ ] Offline Field PWA

---

## سجل التنفيذ

| التاريخ | البند | Commit / ملاحظة |
|---------|-------|-----------------|
| 2026-06-23 | P0 A+B+C foundations | rbac + security + audit + csrf + tests |
| 2026-06-23 | P1 E1/E3/E4/E5 + F1/F2/F3 | install.sh, CI, tests, run_local.bat |

---

## أوامر التحقق بعد P0

```bash
python -m pytest tests/ -q
python scripts/test_upload_auth.py
# viewer: محاولة POST → 403
# admin123 في prod → رفض تشغيل أو إجبار تغيير كلمة المرور
```
