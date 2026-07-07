# توصيات إلزامية قبل وأثناء تنفيذ MULTI-TENANT.md

**الجمهور:** Cursor / مطوّر LiftCore  
**الحالة:** تعديلات على خطة `docs/MULTI-TENANT.md` — تُقرأ مع الخطة الأصلية وتَحكُمها عند التعارض  
**آخر تحديث:** يوليو 2026

---

## قواعد عامة (تسري على كل المهام أدناه)

1. **Step 0 إلزامي:** قبل أي تعديل، اعرض الملفات والدوال والـ IDs التي ستلمسها وانتظر الموافقة.
2. **ممنوع نهائياً** تعديل CSS أو keyframes أو أي JavaScript خاص بالأنيميشن.
3. اعرض النتائج والخطة قبل التنفيذ — لا تنفّذ تعديلات جماعية بدون مراجعة.
4. كل مهمة تنتهي باختبار يثبت نجاحها.

---

## التوصية 1 — عزل المستأجر أوتوماتيكياً (أهم بند في الملف)

### المشكلة

خطة MULTI-TENANT.md تعتمد على الانضباط اليدوي: استبدال ~100+ استعلام بـ `tenant_query()` والاعتماد على code review لمنع النسيان. الخطة نفسها تصنّف "نسيان organization_id في query جديد" كخطر **عالي الاحتمال**. أي استعلام منسي = تسريب بيانات بين الشركات.

### الحل المطلوب

عزل على مستوى SQLAlchemy نفسه بحيث يُضاف فلتر `organization_id` **تلقائياً على كل SELECT** حتى لو نسي المطوّر:

```python
# tenant_scope.py — يُضاف فوق الدوال الموجودة في الخطة الأصلية

from flask import g
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

class TenantMixin:
    """كل موديل تشغيلي يرث منه — يضمن وجود organization_id."""
    organization_id = db.Column(
        db.Integer, db.ForeignKey('organizations.id'),
        nullable=False, index=True
    )

@event.listens_for(db.session, "do_orm_execute")
def add_tenant_filter(execute_state):
    if execute_state.is_select and not execute_state.execution_options.get("skip_tenant"):
        oid = getattr(g, 'organization_id', None)
        if oid:
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(
                    TenantMixin,
                    lambda cls: cls.organization_id == oid,
                    include_aliases=True
                )
            )
```

### متطلبات التنفيذ

- كل الجداول التشغيلية (~31 جدولاً في القسم 5.2 من الخطة) ترث `TenantMixin` بدل إضافة العمود يدوياً في كل موديل.
- الاستعلامات على مستوى المنصة (لوحة إدارة LiftCore، سكربتات الترحيل) تستخدم صراحةً:
  `db.session.execute(stmt, execution_options={"skip_tenant": True})`
- `tenant_query()` و `tenant_get_or_404()` تبقى كما هي — طبقة حماية ثانية، والفلتر التلقائي شبكة الأمان.
- **الكتابة (INSERT) ليست مشمولة بالفلتر:** `assign_organization(obj)` يبقى إلزامياً في كل POST كما في القسم 6.5.

### حارس إضافي في CI

سكربت `scripts/check_tenant_queries.sh`:

```bash
#!/bin/bash
# يفشل إذا وُجد استعلام مباشر خارج tenant_scope.py وسكربتات المنصة
VIOLATIONS=$(grep -rn "\.query\." app.py operations.py customer_billing.py \
  report_data.py entity_links.py installation/routes.py \
  | grep -v "tenant_query\|tenant_get_or_404\|skip_tenant" || true)
if [ -n "$VIOLATIONS" ]; then
  echo "❌ استعلامات مباشرة بدون عزل tenant:"
  echo "$VIOLATIONS"
  exit 1
fi
echo "✅ لا استعلامات مباشرة"
```

### اختبار القبول

```python
def test_forgotten_filter_is_still_isolated(client, org_a, org_b):
    """حتى استعلام خام Customer.query.all() داخل سياق org_a
    يجب ألا يعيد سجلات org_b — بفضل الفلتر التلقائي."""
    with app.test_request_context(headers={'Host': 'a.liftcoreapp.com'}):
        resolve_tenant()
        results = Customer.query.all()  # متعمد بدون tenant_query
        assert all(c.organization_id == org_a.id for c in results)
```

---

## التوصية 2 — زاتكا لكل مؤسسة (فجوة غير مذكورة في الخطة)

### المشكلة

شهادات زاتكا (CSID) والرقم الضريبي **خاصة بكل شركة على حدة**. الخطة الحالية لا تذكر ترحيل بيانات اعتماد زاتكا إلى نموذج multi-tenant. بدون هذا، أول tenant حقيقي سيُصدر فواتير ببيانات الشركة الأم — مخالفة ضريبية مباشرة.

### الحل المطلوب

جدول جديد `zatca_credentials` (لا تخزّن الشهادات في `organizations` مباشرة):

```python
class ZatcaCredentials(db.Model):
    __tablename__ = 'zatca_credentials'

    id                = db.Column(db.Integer, primary_key=True)
    organization_id   = db.Column(db.Integer, db.ForeignKey('organizations.id'),
                                  unique=True, nullable=False, index=True)
    vat_number        = db.Column(db.String(15), nullable=False)   # الرقم الضريبي
    cr_number         = db.Column(db.String(20))                   # السجل التجاري
    csid              = db.Column(db.Text)                         # مشفّر
    private_key       = db.Column(db.Text)                         # مشفّر
    certificate       = db.Column(db.Text)                         # مشفّر
    environment       = db.Column(db.String(10), default='sandbox') # sandbox | production
    onboarded_at      = db.Column(db.DateTime)
    status            = db.Column(db.String(20), default='pending') # pending | active | expired
```

### متطلبات التنفيذ

- **تشفير الحقول الحساسة** (csid, private_key, certificate) بمفتاح من env — لا نص صريح في القاعدة أبداً.
- شاشة "إعدادات الفوترة الإلكترونية" داخل إعدادات كل tenant: إدخال الرقم الضريبي + معالج onboarding مع الهيئة.
- **حارس صريح في مسار إصدار الفاتورة:**

```python
creds = tenant_query(ZatcaCredentials).filter_by(status='active').first()
if not creds:
    abort(422, description='أكمل إعداد الفوترة الإلكترونية أولاً من الإعدادات')
```

- ممنوع أي fallback لبيانات زاتكا من الإعدادات العامة أو من env المنصة.
- يُضاف كبند صريح في **أسبوع 6** من خطة التنفيذ.

### اختبار القبول

```python
def test_invoice_blocked_without_tenant_zatca(client, org_new):
    """tenant جديد بدون CSID لا يستطيع إصدار فاتورة —
    ولا تُستخدم بيانات أي tenant آخر."""
    login(client, org_new, 'admin', 'pass')
    r = client.post('/invoices/issue/1', headers={'Host': 'new.liftcoreapp.com'})
    assert r.status_code == 422
```

---

## التوصية 3 — حسم SSL Wildcard قبل أي كود (أسبوع 1)

### المشكلة

الخطة تقترح `certbot --dns-google`، وهذا يعمل **فقط** إذا كان DNS مُداراً على Google Cloud DNS. النطاق حالياً على Hostinger — الأمر كما هو مكتوب سيفشل.

### القرار المطلوب (خيار واحد، يُحسم قبل كتابة أي كود)

| الخيار | الإيجابيات | السلبيات | التوصية |
|--------|------------|----------|---------|
| **أ) نقل NS إلى Google Cloud DNS** | تجديد تلقائي كامل، متوافق مع GCP | خطوة نقل لمرة واحدة (انتشار DNS حتى 48 ساعة) | ✅ **الموصى به** |
| ب) DNS challenge يدوي على Hostinger | لا نقل | تجديد يدوي كل 90 يوماً = انقطاع مضمون يوماً ما | ❌ |

### متطلبات التنفيذ (الخيار أ)

1. إنشاء Zone في Cloud DNS + نسخ كل السجلات الحالية (A, MX, TXT...) قبل تغيير NS.
2. تغيير nameservers عند Hostinger → انتظار الانتشار → التحقق بـ `dig`.
3. `certbot certonly --dns-google -d liftcoreapp.com -d '*.liftcoreapp.com'` مع service account محدود الصلاحيات.
4. اختبار التجديد: `certbot renew --dry-run` ✅ قبل اعتبار البند مكتملاً.
5. **البريد لا ينقطع:** التحقق من سجلات MX/SPF/DKIM بعد النقل.

---

## التوصية 4 — إغلاق الثغرات القديمة صار حرجاً (أسبوع 1)

### المشكلة

ثغرتان موثقتان من المراجعة الأمنية السابقة كانتا "متوسطة الخطورة" في multi-instance، وأصبحتا **حرجة** في multi-tenant لأن الاختراق الواحد يكشف بيانات كل العملاء دفعة واحدة.

### 4.1 SECRET_KEY

```python
# قبل (الوضع الحالي — مرفوض):
app.secret_key = os.environ.get('SECRET_KEY', 'dev-fallback-key')

# بعد (المطلوب):
app.secret_key = os.environ['SECRET_KEY']  # يفشل التشغيل إذا غاب — وهذا مقصود
```

- توليد المفتاح: `python -c "import secrets; print(secrets.token_urlsafe(48))"` → في `/etc/liftcore/platform.env` فقط.
- **تنبيه:** تغيير المفتاح يُسقط كل الجلسات الحالية — يُنفَّذ مع نافذة الصيانة في أسبوع 1.

**الوضع الحالي في `app.py`:** fallback `'liftcore-secret-2025'` — يجب إزالته قبل cutover.

### 4.2 debug=True

```python
# مرفوض في الإنتاج نهائياً:
app.run(debug=True)

# المطلوب:
if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=5001)
```

الإنتاج يعمل عبر Gunicorn حصراً (لا يمر على `app.run` أصلاً) — لكن السطر يُصحَّح لمنع تشغيل خاطئ.

**الوضع الحالي في `app.py`:** `app.run(debug=True, port=5000)` — يجب تصحيحه.

### 4.3 نسخ احتياطي + تصدير لكل tenant

- `deploy/backup_postgres.sh` يومي عبر cron + **اختبار استعادة فعلي** مرة على staging قبل الـ cutover (نسخة لم تُستعد = لا نسخة).
- الاحتفاظ بآخر 14 نسخة، وحذف الأقدم تلقائياً.
- ميزة جديدة: زر "تصدير بياناتي" في إعدادات كل tenant (Excel لكل الجداول التشغيلية الخاصة به عبر `tenant_query`). قيمة أمان + نقطة بيع تسويقية.

---

## التوصية 5 — تعديلات على خطة التنفيذ الزمنية

| البند في الخطة الأصلية | التعديل | السبب |
|------------------------|---------|--------|
| MVP 6 أسابيع يستبعد موديول التركيبات | **يبقى موديول التركيبات في النطاق** | التميز التنافسي الوحيد ضد ElevatorM — لا يُطلَق بدونه |
| بوابة الدفع | تأجيل ✅ (تحصيل يدوي بتحويل بنكي لأول 10 عملاء) | لا تعطّل الإطلاق |
| التقارير الثانوية | تأجيل ✅ | لا تعطّل الإطلاق |
| بيئة التطوير SQLite | **PostgreSQL من اليوم الأول** على جهازي التطوير (المكتب + المنزل) | منع اكتشاف فروقات السلوك في أسبوع الـ cutover |
| `/signup` عام في أسبوع 7 | لا يُفتح للعامة قبل **خضرة اختبارات العزل كاملة** (التوصية 1 + IDOR) | العزل قبل النمو |

---

## ترتيب التنفيذ المُحدَّث (أسبوع 1–2)

```
أسبوع 1:
[ ] حسم DNS/SSL (التوصية 3) — نقل Cloud DNS + wildcard cert + renew dry-run
[ ] SECRET_KEY بدون fallback + إصلاح debug (التوصية 4)
[ ] PostgreSQL على السيرفر + جهازي التطوير
[ ] backup_postgres.sh + cron + اختبار استعادة

أسبوع 2:
[ ] TenantMixin + الفلتر التلقائي do_orm_execute (التوصية 1)
[ ] Organization model + resolve_tenant()
[ ] tests/test_tenant_isolation.py بما فيها test_forgotten_filter_is_still_isolated
[ ] scripts/check_tenant_queries.sh في الـ CI

أسبوع 6 (إضافة):
[ ] جدول zatca_credentials + التشفير + شاشة الإعداد + حارس الفاتورة (التوصية 2)
```

---

## تعريف الاكتمال (يُضاف لقسم 16 في الخطة الأصلية)

- [ ] اختبار "الاستعلام المنسي" أخضر (التوصية 1)
- [ ] `check_tenant_queries.sh` في الـ CI ويمنع الدمج عند الفشل
- [ ] tenant بدون CSID لا يُصدر فواتير، وكل فاتورة تحمل بيانات مؤسستها فقط
- [ ] `certbot renew --dry-run` ناجح
- [ ] لا SECRET_KEY fallback ولا `debug=True` في أي مسار إنتاجي
- [ ] استعادة نسخة احتياطية مُجرَّبة فعلياً على staging
