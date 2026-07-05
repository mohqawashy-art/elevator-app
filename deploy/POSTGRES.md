# PostgreSQL للإنتاج (F7)

LiftCore يدعم **SQLite** (افتراضي محلي) و **PostgreSQL** (موصى به للإنتاج عند نمو البيانات أو تعدد العمليات).

## 1. تثبيت PostgreSQL (Ubuntu)

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres createuser liftcore --pwprompt
sudo -u postgres createdb -O liftcore liftcore
```

## 2. متغيرات البيئة

في `/etc/liftcore/platform.env`:

```env
DATABASE_URL=postgresql://liftcore:STRONG_PASSWORD@127.0.0.1:5432/liftcore
```

ثم:

```bash
sudo systemctl restart liftcore
```

## 3. قاعدة جديدة (بدون بيانات)

```bash
cd ~/liftcore/elevator-app
source .venv/bin/activate
export DATABASE_URL=postgresql://...
python deploy/migrate_db.py
python init_db.py   # admin + إعدادات افتراضية
```

## 4. ترحيل من SQLite موجود

```bash
export DATABASE_URL=postgresql://liftcore:PASS@127.0.0.1:5432/liftcore
export SQLITE_SOURCE=/home/USER/liftcore/elevator-app/instance/liftcore.db
python scripts/migrate_sqlite_to_postgres.py
```

يُنشئ الجداول عبر Alembic ثم ينسخ البيانات بالترتيب الصحيح.

## 5. نسخ احتياطي

```bash
# SQLite (افتراضي)
bash deploy/backup_daily.sh

# PostgreSQL
export DATABASE_URL=postgresql://...
python scripts/backup_database.py
```

ملف `.dump` يُستعاد بـ `pg_restore -d liftcore backup.dump`.

## 6. ملاحظات

- ترقيات المخطط على PostgreSQL عبر **Alembic** فقط (`deploy/migrate_db.py` في `gcp_update.sh`).
- ترقيات `ALTER TABLE` اليدوية في `app.py` تعمل على **SQLite فقط**.
- محلياً يبقى SQLite ما لم تُعيّن `DATABASE_URL`.
