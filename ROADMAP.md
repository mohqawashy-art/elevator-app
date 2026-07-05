# LiftCore — خارطة الإصلاحات قبل التسويق

**آخر تحديث:** يوليو 2026  
**القاعدة:** نُغلق كل بند نهائياً — لا نعود له إلا إذا تغيّر scope التسويق.

---

## حالة التقدّم

| المرحلة | الوصف | الحالة |
|---------|--------|--------|
| **P0** | أمان + صلاحيات + استقرار حرج | ✅ 100% |
| **P1** | QA + نشر + ميزات ناقصة | ✅ 100% |
| **P2** | UX + i18n + مواد تسويق | ✅ 100% |
| **P3** | SaaS / ZATCA كامل / Offline (حسب الوعد) | ⏳ |

**Definition of Done للتسويق:** P0 = 100% · P1 ≥ 90% · P2 polish · سيناريو جما بدون blockers

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
- [x] G2 — `/api/translate`: **مؤجّل P3** — قرار في `docs/I18N.md`
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
- [x] I1 — modal CSS موحّد في `liftcore-shell.css` (تقليل تكرار القوالب تدريجياً)
- [x] I2 — responsive 768/480 — shell + صفحات outlier
- [x] I3 — empty/loading/toast — `.lc-empty`, `.lc-loading`, `LiftCoreToast()`
- [x] I4 — Google Maps: `PlaceAutocompleteElement` أولاً في `client_map_picker.js`
- [x] I5 — QA طباعة (`tests/test_print_documents.py`)
- [x] I6 — viewer UI كامل + `MutationObserver` (`tests/test_viewer_ui.py`)

### J. i18n
- [x] J1 — pytest تغطية `liftcore-translations.js`
- [x] J2 — `liftcore_api_i18n.py` + رسائل API ثنائية
- [x] J3 — قرار المحتوى الديناميكي — `docs/I18N.md`

### K. بوابة الفني
- [x] K1 — smoke pytest + Playwright `e2e/field-smoke.spec.js`
- [x] K2 — `deploy/FIELD-PIN.md`
- [x] K3 — Offline PWA: **P3** — غير موعود للتسويق الحالي

### L. مواد تسويق
- [x] L1 — `docs/marketing/USER-GUIDE.md`
- [x] L2 — `docs/marketing/ADMIN-GUIDE.md`
- [x] L3 — `docs/marketing/DEMO-VIDEO.md` (خطة إنتاج خارجية)
- [x] L4 — `docs/marketing/ONE-PAGER.md`
- [x] L5 — `docs/marketing/PRIVACY.md` + `TERMS.md`

---

## P3 — حسب الوعد التسويقي فقط

- [ ] SaaS multi-tenant + billing
- [ ] ZATCA Phase 2 (XML + clearance)
- [ ] WhatsApp Business API + تذكيرات مجدولة
- [ ] Offline Field PWA
- [ ] `/api/translate` (G2)

---

## سجل التنفيذ

| التاريخ | البند | Commit / ملاحظة |
|---------|-------|-----------------|
| 2026-06-23 | P0 A+B+C foundations | rbac + security + audit + csrf + tests |
| 2026-06-23 | P1 E1/E3/E4/E5 + F1/F2/F3 | install.sh, CI, tests, run_local.bat |
| 2026-07-05 | P1 إغلاق + H3 | ZATCA, Alembic, Sentry, billing, PostgreSQL |
| 2026-07-05 | P2 إغلاق | UX, i18n, field, marketing docs |

---

## أوامر التحقق

```bash
python -m pytest tests/ -q
npm run test:e2e
# viewer: محاولة POST → 403
# admin123 في prod → رفض تشغيل أو إجبار تغيير كلمة المرور
```
