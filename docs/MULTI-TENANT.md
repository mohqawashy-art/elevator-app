# LiftCore — دليل التحويل الكامل إلى Multi-Tenant

**آخر تحديث:** يوليو 2026  
**الحالة:** خطة تنفيذ — لم يُنفَّذ بعد  
**الجمهور:** مطوّر LiftCore / مسؤول النشر

> **مرافق إلزامي:** [`docs/CURSOR-RECOMMENDATIONS-MULTI-TENANT.md`](CURSOR-RECOMMENDATIONS-MULTI-TENANT.md)  
> عند التعارض بين هذا الملف والتوصيات — **التوصيات تَحكُم**.  
> أهم بنود التوصيات: عزل SQLAlchemy التلقائي (`TenantMixin`)، زاتكا لكل مؤسسة، نقل DNS إلى Cloud DNS، إغلاق `SECRET_KEY`/`debug` قبل cutover.

### قواعد تنفيذ (Cursor)

1. **Step 0:** اعرض الملفات والدوال قبل التعديل وانتظر الموافقة.
2. لا تعديل CSS/keyframes/JS أنيميشن ضمن مشروع Multi-Tenant.
3. كل مرحلة تنتهي باختبار يثبت نجاحها.
4. PostgreSQL على التطوير من اليوم الأول — لا الاعتماد على SQLite فقط.

---

## 1. الملخص التنفيذي

### الوضع الحالي (Multi-Instance)

كل عميل = **نسخة منفصلة** من التطبيق:

- مجلد كود خاص (`~/liftcore/jama-elevator-app`)
- قاعدة SQLite منفصلة (`jama.db`)
- خدمة systemd منفصلة (`liftcore-jama`)
- موقع nginx منفصلة (`jama.liftcoreapp.com`)
- سكربت تجهيز يدوي: `deploy/provision_jama.sh` (~ساعتين لكل عميل)

### الوضع المستهدف (Multi-Tenant)

كل عميل = **حساب** داخل تطبيق واحد:

- تطبيق Flask واحد + Gunicorn واحد
- قاعدة PostgreSQL واحدة
- nginx واحد مع `*.liftcoreapp.com`
- التسجيل من `/signup` → جاهز خلال ثوانٍ
- عزل البيانات عبر `organization_id` على كل الجداول

### لماذا التحويل؟

| المشكلة الحالية | بعد Multi-Tenant |
|-----------------|------------------|
| ~ساعتين لتجهيز عميل جديد | أقل من دقيقة |
| لا تسجيل ذاتي | مثل إنشاء إيميل جديد |
| صعب التوسع لـ 50+ عميل | نفس السيرفر يخدم المئات |
| تحديث كود لكل نسخة | `git pull` مرة واحدة |
| منافس يوعد «15 دقيقة» | نفس التجربة ممكنة |

---

## 2. قرارات معمارية (ثابتة قبل البدء)

| # | القرار | الخيار المعتمد | بدائل مرفوضة |
|---|--------|----------------|--------------|
| 1 | تمييز العميل | **Subdomain:** `{slug}.liftcoreapp.com` | مسار `/t/jama` — أضعف للتسويق |
| 2 | عزل البيانات | **عمود `organization_id`** على كل جدول تشغيلي | schema منفصل لكل عميل — أعقد |
| 3 | قاعدة البيانات | **PostgreSQL** إنتاجاً | SQLite — لا يناسب multi-tenant |
| 4 | مفتاح الخرائط | **منصة** (`GOOGLE_MAPS_API_KEY` في env) | لكل عميل — مكلف |
| 5 | رفع الملفات | مجلد لكل عميل: `uploads/{slug}/` | bucket منفصل لكل عميل — لاحقاً |
| 6 | uniqueness | مركّب: `(organization_id, code)` | unique عالمي — يتعارض بين العملاء |
| 7 | العملاء الحاليون | ترحيل إلى tenants | الإبقاء على النموذج القديم — ازدواجية |

---

## 3. البنية: قبل وبعد

### قبل

```
┌──────────────────┐     ┌──────────────────┐
│ liftcore (main)  │     │ liftcore-jama      │
│ liftcore.db      │     │ jama.db            │
│ :5001            │     │ :5002              │
│ app.liftcore...  │     │ jama.liftcore...   │
└──────────────────┘     └──────────────────┘
         ↑ يدوي: provision_jama.sh لكل عميل جديد
```

### بعد

```
                    ┌─────────────────────────────┐
                    │  nginx *.liftcoreapp.com    │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Gunicorn :5001 (واحد)      │
                    │  Flask + resolve_tenant()   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  PostgreSQL (liftcore)      │
                    │  organizations              │
                    │  customers (+ org_id)       │
                    │  elevators (+ org_id)       │
                    │  ...                        │
                    └─────────────────────────────┘
```

### تدفق طلب HTTP

```
1. GET https://jama.liftcoreapp.com/clients
2. nginx → proxy → Gunicorn
3. before_request: resolve_tenant()
      Host = jama.liftcoreapp.com → slug = jama
      Organization.query.filter_by(slug='jama')
      g.organization_id = 2
4. enforce_auth() → user يجب أن ينتمي لـ organization_id=2
5. Customer.query.filter_by(organization_id=2)
6. response — لا يرى بيانات عميل آخر أبداً
```

---

## 4. المتطلبات والأدوات

### 4.1 بنية تحتية (إلزامي)

| الأداة | الغرض | ملاحظة |
|--------|-------|--------|
| **GCP VM** e2-standard-4 | 4 vCPU / 8 GB | ترقية من e2-medium |
| **PostgreSQL 15+** | قاعدة موحّدة | `deploy/POSTGRES.md` |
| **nginx** | reverse proxy | موجود |
| **Wildcard DNS** | `*.liftcoreapp.com` → IP السيرفر | مرة واحدة |
| **SSL wildcard** | `*.liftcoreapp.com` | certbot DNS challenge |
| **خدمة بريد** | تأكيد تسجيل / استعادة كلمة مرور | Resend أو SendGrid |

### 4.2 برمجية (موجودة في المشروع)

| الأداة | الملف | الحالة |
|--------|-------|--------|
| Flask + SQLAlchemy | `app.py`, `models.py` | ✅ |
| Alembic / Flask-Migrate | `migrations/` | ✅ |
| psycopg | `requirements.txt` | ✅ |
| gunicorn + systemd | `deploy/gcp_update.sh` | ✅ |

### 4.3 لاحقاً (بعد 30–50 عميل)

| الأداة | متى |
|--------|-----|
| Redis | جلسات / rate limit / طوابير |
| Google Cloud Storage | رفع ملفات سحابي |
| Cloud SQL | PostgreSQL مُدار |
| Moyasar / Tap | اشتراكات مدفوعة |

### 4.4 تكلفة تقديرية إضافية

| البند | شهري (ر.س) |
|-------|------------|
| ترقية VM | +150–250 |
| بريد (Resend) | 0–75 |
| GCS (لاحقاً) | 20–100 |
| **المجموع MVP** | **~200–400** |

---

## 5. نموذج البيانات

### 5.1 جدول جديد: `organizations`

```python
class Organization(db.Model):
    __tablename__ = 'organizations'

    id              = db.Column(db.Integer, primary_key=True)
    slug            = db.Column(db.String(63), unique=True, nullable=False, index=True)
    name            = db.Column(db.String(200), nullable=False)
    name_en         = db.Column(db.String(200))
    status          = db.Column(db.String(20), default='trial')  # trial | active | suspended
    plan            = db.Column(db.String(30), default='basic')  # basic | pro | advanced | enterprise
    admin_email     = db.Column(db.String(100))
    trial_ends_at   = db.Column(db.DateTime)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    suspended_at    = db.Column(db.DateTime)
    notes           = db.Column(db.Text)  # داخلي — فريق LiftCore
```

**قواعد `slug`:**

- أحرف إنجليزية صغيرة + أرقام + شرطة
- 3–63 حرفاً
- محجوز: `www`, `app`, `api`, `admin`, `mail`, `staging`
- مثال: `jama` → `jama.liftcoreapp.com`

### 5.2 جداول تحتاج `organization_id`

#### النواة (`models.py`)

| الجدول | ملاحظة |
|--------|--------|
| `customers` | + `UniqueConstraint('organization_id', 'code')` |
| `elevators` | + unique مركّب على `code` |
| `contracts` | |
| `contract_elevators` | عبر contract |
| `technicians` | |
| `technician_documents` | عبر technician |
| `maintenance_teams` | |
| `maintenance_visits` | |
| `visit_technicians` | |
| `faults` | |
| `fault_technicians` | |
| `revenues` | |
| `expenses` | |
| `invoices` | |
| `inventory_items` | |
| `stock_movements` | |
| `parts_billing` | |
| `purchase_orders` | |
| `purchase_order_lines` | |
| `elevator_estimates` | |
| `elevator_estimate_lines` | |
| `signatories` | |
| `settings` | **صف واحد لكل organization** (ليس صفاً عالمياً) |
| `users` | + `UniqueConstraint('organization_id', 'username')` |
| `audit_logs` | |
| `app_live_state` | اختياري — أو جدول منصة منفصل |

#### موديول التركيب (`installation/models.py`)

| الجدول |
|--------|
| `install_leads` |
| `install_projects` |
| `install_quotations` |
| `install_quotation_lines` |
| `install_timeline_steps` |

**المجموع:** ~31 جدولاً.

### 5.3 تغييرات uniqueness حرجة

| الحقل الحالي | بعد التحويل |
|--------------|-------------|
| `User.username` unique عالمي | `(organization_id, username)` |
| `Customer.code` unique عالمي | `(organization_id, code)` |
| `Elevator.code` unique عالمي | `(organization_id, code)` |
| `Settings` صف واحد (`query.first()`) | `filter_by(organization_id=...).first()` |

### 5.4 علاقة User ↔ Organization

```python
class User(db.Model):
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    username        = db.Column(db.String(50), nullable=False)
    # ...
    __table_args__ = (db.UniqueConstraint('organization_id', 'username', name='uq_user_org_username'),)
```

**تسجيل الدخول:** المستخدم يُحدَّد من:

1. `organization_id` المستمد من الـ subdomain
2. `username` + `password` من النموذج

### 5.5 زاتكا لكل مؤسسة (`zatca_credentials`)

> **إلزامي** — راجع التوصية 2 في `CURSOR-RECOMMENDATIONS-MULTI-TENANT.md`.

شهادات CSID والرقم الضريبي **خاصة بكل tenant**. ممنوع fallback لبيانات المنصة أو tenant آخر.

```python
class ZatcaCredentials(db.Model):
    __tablename__ = 'zatca_credentials'

    id              = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'),
                                unique=True, nullable=False, index=True)
    vat_number      = db.Column(db.String(15), nullable=False)
    cr_number       = db.Column(db.String(20))
    csid            = db.Column(db.Text)          # مشفّر
    private_key     = db.Column(db.Text)          # مشفّر
    certificate     = db.Column(db.Text)          # مشفّر
    environment     = db.Column(db.String(10), default='sandbox')
    onboarded_at    = db.Column(db.DateTime)
    status          = db.Column(db.String(20), default='pending')
```

- تشفير `csid`, `private_key`, `certificate` بمفتاح من env.
- شاشة «إعدادات الفوترة الإلكترونية» لكل tenant.
- حارس إصدار الفاتورة: بدون `status='active'` → HTTP 422.
- **أسبوع 6** في خطة التنفيذ.

---

## 6. تغييرات الكود

### 6.1 ملف جديد: `tenant_scope.py` (عزل يدوي + تلقائي)

**طبقتان:** فلتر SQLAlchemy التلقائي (شبكة أمان) + `tenant_query()` (وضوح في الكود).

```python
"""عزل المستأجر — فلتر تلقائي + helpers."""

from flask import g, abort
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria
from models import db

class TenantMixin:
    """كل موديل تشغيلي يرث منه."""
    organization_id = db.Column(
        db.Integer, db.ForeignKey('organizations.id'),
        nullable=False, index=True,
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
                    include_aliases=True,
                )
            )

def current_organization_id():
    oid = getattr(g, 'organization_id', None)
    if oid is None:
        abort(404, description='المؤسسة غير معروفة')
    return oid

def tenant_query(model):
    return model.query.filter_by(organization_id=current_organization_id())

def tenant_get_or_404(model, id):
    return tenant_query(model).filter_by(id=id).first_or_404()

def assign_organization(obj):
    obj.organization_id = current_organization_id()
    return obj
```

**قواعد:**

- كل جداول القسم 5.2 ترث `TenantMixin`.
- استعلامات المنصة/الترحيل: `execution_options={"skip_tenant": True}`.
- INSERT: `assign_organization()` إلزامي — الفلتر التلقائي لا يغطي الكتابة.
- CI: `scripts/check_tenant_queries.sh` (انظر التوصيات).

### 6.2 Middleware: `resolve_tenant()`

يُضاف في `app.py` **قبل** `enforce_auth()`:

```python
PLATFORM_HOSTS = {'liftcoreapp.com', 'www.liftcoreapp.com'}
MARKETING_SLUGS = {'www', 'app', 'api', 'admin', 'staging'}

@app.before_request
def resolve_tenant():
    host = (request.host or '').split(':')[0].lower()
    parts = host.split('.')
    # jama.liftcoreapp.com → slug=jama
    if len(parts) < 3 or host in PLATFORM_HOSTS:
        g.organization = None
        g.organization_id = None
        return
    slug = parts[0]
    if slug in MARKETING_SLUGS:
        g.organization = None
        g.organization_id = None
        return
    from models import Organization
    org = Organization.query.filter_by(slug=slug).first()
    if not org or org.status == 'suspended':
        abort(404)
    g.organization = org
    g.organization_id = org.id
```

**مسارات بدون tenant:**

- `/signup`, `/api/signup` — على النطاق الرئيسي
- `/api/health` — عام
- لوحة إدارة المنصة (لاحقاً): `admin.liftcoreapp.com`

### 6.3 تعديل `enforce_auth()`

```python
# بعد التحقق من user:
if g.organization_id and user.organization_id != g.organization_id:
    session.clear()
    abort(403)  # مستخدم من مؤسسة أخرى
```

### 6.4 استبدال الاستعلامات

| قبل | بعد |
|-----|-----|
| `Customer.query.all()` | `tenant_query(Customer).all()` |
| `Settings.query.first()` | `tenant_query(Settings).first()` |
| `User.query.filter_by(username=u)` | `tenant_query(User).filter_by(username=u)` |
| `Customer.query.get_or_404(id)` | `tenant_get_or_404(Customer, id)` |

**نطاق التعديل:**

- `app.py` — ~100+ موضع
- `operations.py`, `customer_billing.py`, `report_data.py`, `entity_links.py`
- `installation/routes.py`
- سكربتات الاستيراد — تمرير `organization_id`

### 6.5 إنشاء سجلات جديدة

كل `POST` يضيف:

```python
c = Customer(...)
assign_organization(c)
db.session.add(c)
```

### 6.6 الملفات المرفوعة

```
قبل:  static/uploads/clients/{id}/
بعد:  static/uploads/{org_slug}/clients/{id}/
```

تحديث:

- `_client_dir()`, `TECH_UPLOAD_ROOT`, إلخ — بادئة `{org_slug}`
- `serve_upload_file` — التحقق من أن المسار ضمن tenant الحالي

### 6.7 بوابة الفني `/field`

- نفس الـ subdomain: `jama.liftcoreapp.com/field/login`
- `Technician` يُفلتر بـ `organization_id`
- PIN والجلسة مربوطة بالمؤسسة

### 6.8 التسجيل الذاتي `/signup`

**النطاق:** `https://liftcoreapp.com/signup` (بدون subdomain)

```
POST /api/signup
{
  "company_name": "جما لتقنية المصاعد",
  "slug": "jama",
  "admin_email": "admin@jama.sa",
  "admin_name": "محمد",
  "password": "..."
}
```

**المنطق:**

1. التحقق: slug فريد، email صالح، كلمة مرور قوية
2. `INSERT organizations`
3. `INSERT users` (role=admin, organization_id)
4. `INSERT settings` (company_name, tax_pct=15, ...)
5. `init_install_module` إن `LIFTCORE_INSTALL_MODULE=1`
6. إيميل ترحيب + رابط `https://jama.liftcoreapp.com/login`
7. **لا** systemd، **لا** nginx، **لا** clone

### 6.9 Alembic

```bash
# بعد تعديل models.py
export DATABASE_URL=postgresql://liftcore:PASS@127.0.0.1:5432/liftcore
flask db migrate -m "multi-tenant organizations and organization_id"
flask db upgrade
```

**ملاحظة:** ترقيات `ALTER TABLE` اليدوية في `app.py` تعمل على SQLite فقط — بعد التحويل اعتمد على Alembic حصرياً في الإنتاج.

---

## 7. إعداد البنية التحتية (خطوة بخطوة)

### 7.1 PostgreSQL

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres createuser liftcore --pwprompt
sudo -u postgres createdb -O liftcore liftcore
```

في `/etc/liftcore/platform.env`:

```env
DATABASE_URL=postgresql://liftcore:STRONG_PASSWORD@127.0.0.1:5432/liftcore
SECRET_KEY=<token_urlsafe 48>
LIFTCORE_HTTPS=1
GOOGLE_MAPS_API_KEY=<optional>
MAIL_API_KEY=<resend>
MAIL_FROM=noreply@liftcoreapp.com
```

### 7.2 Wildcard DNS — **حسم قبل أي كود**

> النطاق حالياً على **Hostinger**. `certbot --dns-google` يعمل فقط إذا DNS على **Google Cloud DNS**.

**الخيار المعتمد:** نقل nameservers إلى Cloud DNS (مرة واحدة، انتشار حتى 48 ساعة).

1. إنشاء Zone في Cloud DNS ونسخ كل السجلات (A, MX, TXT, SPF, DKIM).
2. تغيير NS عند Hostinger → التحقق بـ `dig liftcoreapp.com NS`.
3. إضافة:

```
*.liftcoreapp.com.  IN  A  34.18.56.21
liftcoreapp.com.    IN  A  34.18.56.21
```

4. **تحقق البريد:** MX/SPF/DKIM لم تتكسر بعد النقل.

### 7.3 SSL wildcard

```bash
sudo certbot certonly --dns-google \
  -d liftcoreapp.com -d '*.liftcoreapp.com'
sudo certbot renew --dry-run   # إلزامي قبل اعتبار الأسبوع 1 مكتملاً
```

❌ **مرفوض:** DNS challenge يدوي على Hostinger كل 90 يوماً.

### 7.4 nginx موحّد

ملف مقترح: `/etc/nginx/sites-available/liftcore-multitenant`

```nginx
server {
    listen 443 ssl http2;
    server_name liftcoreapp.com *.liftcoreapp.com;

    ssl_certificate     /etc/letsencrypt/live/liftcoreapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/liftcoreapp.com/privkey.pem;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 7.5 systemd — خدمة واحدة

```ini
# /etc/systemd/system/liftcore.service
[Service]
EnvironmentFile=/etc/liftcore/platform.env
Environment=LIFTCORE_HTTPS=1
WorkingDirectory=/home/USER/liftcore/elevator-app
ExecStart=/home/USER/liftcore/elevator-app/.venv/bin/gunicorn -w 4 -b 127.0.0.1:5001 --timeout 120 app:app
```

**إيقاف الخدمات القديمة بعد الترحيل:**

```bash
sudo systemctl stop liftcore-jama
sudo systemctl disable liftcore-jama
```

### 7.6 نسخ احتياطي PostgreSQL

```bash
# deploy/backup_postgres.sh (يُنشأ)
pg_dump -Fc liftcore > /var/backups/liftcore/liftcore_$(date +%Y%m%d).dump
```

- cron يومي + الاحتفاظ بآخر **14** نسخة.
- **اختبار استعادة فعلي** على staging قبل cutover — نسخة لم تُستعد = لا نسخة.
- زر «تصدير بياناتي» (Excel per tenant) — لاحقاً في الإعدادات.

### 7.7 إغلاق ثغرات حرجة (أسبوع 1 — قبل cutover)

| البند | الوضع الحالي (`app.py`) | المطلوب |
|-------|-------------------------|---------|
| `SECRET_KEY` | fallback `'liftcore-secret-2025'` | `os.environ['SECRET_KEY']` بدون fallback |
| `debug` | `app.run(debug=True)` | `FLASK_DEBUG=1` للتطوير فقط |
| الإنتاج | — | Gunicorn حصراً |

تغيير `SECRET_KEY` يُسقط الجلسات — نفّذه في نافذة صيانة.

---

## 8. ترحيل العملاء الحاليين

### 8.1 سكربت مقترح: `scripts/migrate_instance_to_tenant.py`

```bash
python scripts/migrate_instance_to_tenant.py \
  --slug jama \
  --name "جما لتقنية المصاعد" \
  --sqlite /home/USER/liftcore/jama-elevator-app/instance/jama.db \
  --uploads-source /home/USER/liftcore/jama-elevator-app/static/uploads \
  --dry-run

python scripts/migrate_instance_to_tenant.py ... # بدون --dry-run
```

**خطوات السكربت:**

1. إنشاء `Organization(slug='jama')`
2. قراءة SQLite المصدر
3. نسخ الجداول بالترتيب (FK): customers → elevators → contracts → ...
4. تعيين `organization_id` على كل صف
5. إعادة ربط `user.organization_id`
6. نسخ الملفات إلى `uploads/jama/`
7. تحديث مسارات `*_path` في DB
8. تقرير: عدد السجلات / الأخطاء

### 8.2 ترتيب الترحيل الموصى به

| # | Tenant | المصدر |
|---|--------|--------|
| 1 | `liftcore` | `instance/liftcore.db` (المنصة الرئيسية) |
| 2 | `jama` | `jama-elevator-app/instance/jama.db` |

### 8.3 التحقق بعد الترحيل

```bash
bash deploy/verify_deploy.sh https://jama.liftcoreapp.com
python scripts/verify_production_ops.py --url https://jama.liftcoreapp.com
pytest tests/test_tenant_isolation.py -q
```

**يدوياً:**

- [ ] تسجيل دخول admin جما
- [ ] عدد العملاء = العدد قبل الترحيل
- [ ] صورة مبنى تظهر
- [ ] فني ميداني `/field/login`
- [ ] tenant آخر لا يرى بيانات جما (اختبار عزل)

---

## 9. خطة التنفيذ (10 أسابيع — مُحدَّثة بالتوصيات)

| الأسبوع | المهام | مخرجات |
|---------|--------|--------|
| **1** | نقل DNS → Cloud DNS + SSL wildcard + `renew --dry-run` | DNS/SSL محسوم |
| **1** | PostgreSQL (سيرفر + تطوير) + `SECRET_KEY`/`debug` + backup + استعادة | أمان + بنية |
| **2** | `TenantMixin` + `do_orm_execute` + `Organization` + `resolve_tenant()` | عزل تلقائي |
| **2** | `test_tenant_isolation` + `test_forgotten_filter` + `check_tenant_queries.sh` في CI | حراس |
| **3** | `organization_id` على جداول النواة + Alembic | migration أولى |
| **4** | باقي الجداول + **موديول التركيب** (يبقى في النطاق) | schema كامل |
| **5** | تعديل `app.py` (عملاء، مصاعد، عقود، صيانة) | 50% routes |
| **6** | تقارير + فوترة + فني + uploads + **`zatca_credentials`** | 100% routes + زاتكا |
| **7** | `/signup` + بريد — **فقط بعد خضرة اختبارات العزل** | تسجيل محدود ثم عام |
| **8** | ترحيل jama + liftcore + staging | بيانات حية |
| **9** | cutover إنتاج + إيقاف multi-instance | عميل = حساب |
| **10** | مراقبة + توثيق + «تصدير بياناتي» | إغلاق |

### ما يُؤجَّل (لا يعطّل الإطلاق)

- بوابة دفع (تحصيل بنكي يدوي لأول 10 عملاء)
- بعض التقارير الثانوية
- Redis / Cloud SQL

### ما لا يُستبعد من MVP

- **موديول التركيبات** — تميز تنافسي ضد ElevatorM
- **اختبارات عزل كاملة** قبل فتح `/signup` للعامة

---

## 10. الاختبارات الإلزامية

### 10.1 `tests/test_tenant_isolation.py`

```python
def test_tenant_a_cannot_see_tenant_b_clients(client, org_a, org_b):
    login(client, org_a, 'admin', 'pass')
    r = client.get('/clients', headers={'Host': 'a.liftcoreapp.com'})
    assert org_b_customer_name not in r.get_data(as_text=True)

def test_cross_tenant_idor_returns_404(client, org_a, org_b):
    login(client, org_a, 'admin', 'pass')
    r = client.get(f'/clients/edit/{org_b_client_id}', headers={'Host': 'a.liftcoreapp.com'})
    assert r.status_code in (403, 404)

def test_forgotten_filter_is_still_isolated(client, org_a, org_b):
    """استعلام خام بدون tenant_query — يجب أن يبقى معزولاً."""
    with app.test_request_context(headers={'Host': 'a.liftcoreapp.com'}):
        resolve_tenant()
        results = Customer.query.all()
        assert all(c.organization_id == org_a.id for c in results)

def test_invoice_blocked_without_tenant_zatca(client, org_new):
    login(client, org_new, 'admin', 'pass')
    r = client.post('/invoices/issue/1', headers={'Host': 'new.liftcoreapp.com'})
    assert r.status_code == 422
```

### 10.2 Checklist يدوي

```
[ ] signup ينشئ organization + admin + settings
[ ] subdomain خاطئ → 404
[ ] organization معلّقة (suspended) → 404 أو صفحة توقف
[ ] مستخدم org_a على subdomain org_b → مرفوض
[ ] استيراد Excel يحفظ organization_id صحيح
[ ] طباعة عقد / فاتورة ببيانات الشركة الصحيحة
[ ] field login على نفس subdomain
[ ] pg_dump يستعيد بنجاح
```

---

## 11. التراجع (Rollback)

### قبل أي تطوير — حفظ نقطة الرجوع (إلزامي)

```bash
cd ~/liftcore/elevator-app && bash deploy/checkpoint_pre_multitenant.sh
# أو: bash deploy/install.sh checkpoint
```

يحفظ في `~/liftcore/checkpoints/pre-multitenant-YYYYMMDD-HHMMSS/`:

- قواعد SQLite (main + jama)
- `uploads` مضغوطة
- nginx + systemd + `platform.env` (أسرار — لا ترفع لـ git)
- `MANIFEST.txt` + `git-main.txt` / `git-jama.txt`

**استعادة:**

```bash
bash deploy/restore_checkpoint.sh ~/liftcore/checkpoints/pre-multitenant-YYYYMMDD-HHMMSS
```

**Git (على جهازك):**

```bash
git tag -a pre-multitenant-2026-07 -m "قبل Multi-Tenant"
git push origin pre-multitenant-2026-07
```

**GCP:** Disk Snapshot من Console — أقوى رجوع كامل.

### إذا فشل cutover الإنتاج (لاحقاً)

1. `restore_checkpoint.sh` أو GCP snapshot
2. إعادة تفعيل `liftcore-jama.service` القديم إن لزم
3. nginx يوجّه `jama.liftcoreapp.com` → port 5002
4. PostgreSQL multi-tenant يبقى للتطوير — لا تحذف حتى استقرار 72 ساعة

```bash
cp jama.db jama.db.pre-multitenant.$(date +%Y%m%d)
pg_dump -Fc liftcore > liftcore.pre-cutover.dump
```

---

## 12. ما يُلغى بعد التحويل

| يُلغى | البديل |
|-------|--------|
| `deploy/provision_jama.sh` لعملاء جدد | `/signup` |
| `deploy/provision_tenant.sh` (إن وُجد) | `/signup` |
| خدمة systemd لكل عميل | `liftcore.service` واحدة |
| nginx site لكل عميل | موقع wildcard واحد |
| SQLite إنتاجاً | PostgreSQL فقط |
| `tenant_update.sh` لكل نسخة | `bash deploy/gcp_update.sh` مرة واحدة |

**يُبقى:**

- `deploy/gcp_update.sh` — تحديث الكود
- `deploy/backup_postgres.sh` — نسخ احتياطي
- `deploy/verify_deploy.sh` — تحقق

---

## 13. سيناريو عميل جديد «جما» (بعد التحويل)

```
1. مدير جما يفتح https://liftcoreapp.com/signup
2. يملأ:
     - اسم الشركة: جما لتقنية المصاعد
     - الرابط: jama  →  jama.liftcoreapp.com
     - الإيميل + كلمة المرور
3. خلال ~30 ثانية:
     - INSERT INTO organizations ...
     - INSERT INTO users ...
     - INSERT INTO settings ...
     - إيميل: «حسابك جاهز»
4. يدخل https://jama.liftcoreapp.com/login
5. العملاء → استيراد Excel
6. المصاعد → استيراد Excel
7. يبدأ العمل — بدون SSH، بدون انتظارك
```

**أنت (اختياري):** استيراد بيانات قديمة عبر سكربت أو دعم يدوي — ليس شرطاً للتشغيل.

---

## 14. مخاطر ومعالجات

| الخطر | الاحتمال | المعالجة |
|-------|----------|----------|
| تسريب بيانات بين tenants | متوسط | `TenantMixin` + فلتر تلقائي + `tenant_query` + CI |
| نسيان `organization_id` في query جديد | عالٍ | `do_orm_execute` + `check_tenant_queries.sh` |
| فواتير ببيانات زاتكا خاطئة | عالٍ | `zatca_credentials` per tenant + حارس 422 |
| فشل SSL بعد 90 يوم | متوسط | Cloud DNS + `certbot renew --dry-run` |
| `SECRET_KEY` ضعيف / مشترك | حرج | إزالة fallback في أسبوع 1 |
| تعطل جما أثناء الترحيل | متوسط | staging + rollback plan |
| بطء PostgreSQL | منخفض | indexes على `organization_id` |
| تعارض usernames بين tenants | منخفض | unique مركّب |
| حجم `app.py` | موجود | `tenant_scope.py` + ت refactor تدريجي |

---

## 15. فهرس الملفات المرتبطة

| الملف | الدور |
|-------|-------|
| `docs/MULTI-TENANT.md` | هذا الدليل |
| `docs/CURSOR-RECOMMENDATIONS-MULTI-TENANT.md` | توصيات إلزامية — تَحكُم عند التعارض |
| `scripts/check_tenant_queries.sh` | **جديد** — حارس CI للاستعلامات |
| `tenant_scope.py` | **جديد** — TenantMixin + فلتر تلقائي |
| `deploy/POSTGRES.md` | تثبيت PostgreSQL |
| `deploy/ONBOARDING.md` | onboarding قديم — يُحدَّث بعد التحويل |
| `deploy/provision_jama.sh` | يُؤرشف بعد التحويل |
| `migrations/` | Alembic |
| `models.py` | إضافة Organization + organization_id |
| `tenant_scope.py` | **جديد** — عزل الاستعلامات |
| `scripts/migrate_instance_to_tenant.py` | **جديد** — ترحيل SQLite |
| `tests/test_tenant_isolation.py` | **جديد** — اختبارات عزل |

---

## 16. تعريف «تم التحويل» (Definition of Done)

- [ ] عميل جديد يسجّل من `/signup` بدون تدخل يدوي
- [ ] `jama.liftcoreapp.com` يعمل من PostgreSQL multi-tenant
- [ ] لا خدمة `liftcore-jama` منفصلة على الإنتاج
- [ ] اختبارات عزل خضراء (بما فيها `test_forgotten_filter_is_still_isolated`)
- [ ] `check_tenant_queries.sh` في CI ويمنع الدمج عند الفشل
- [ ] tenant بدون CSID لا يُصدر فواتير — لا fallback لزاتكا من منصة أخرى
- [ ] `certbot renew --dry-run` ناجح
- [ ] لا `SECRET_KEY` fallback ولا `debug=True` في مسار إنتاجي
- [ ] استعادة نسخة احتياطية مُجرَّبة على staging
- [ ] نسخ احتياطي PostgreSQL يومي يعمل
- [ ] `ONBOARDING.md` محدّث
- [ ] `provision_jama.sh` مُعلَّم deprecated في التعليقات

---

## 17. الخطوة التالية

1. **أسبوع 1 — بنية فقط:** نفّذ القسم 7 على السيرفر بدون تغيير كود
2. **أسبوع 2 — أول كود:** `Organization` + `resolve_tenant()` + `test_tenant_isolation.py`
3. راجع هذا الملف مع كل مرحلة وحدّث حالة البنود في القسم 16

---

*للأسئلة أو تحديث الخطة: راجع `ROADMAP.md` (P3 — SaaS) أو ناقش في جلسة تطوير.*
