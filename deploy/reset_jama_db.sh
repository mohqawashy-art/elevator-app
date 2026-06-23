#!/usr/bin/env bash
# تفريغ قاعدة بيانات جما — ملف jama.db فقط
#   cd ~/liftcore/elevator-app && bash deploy/reset_jama_db.sh
#
# SEED=1   إضافة بيانات تجريبية بعد التفريغ
# SEED=0   فارغة (admin + إعدادات الشركة فقط) — الافتراضي

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
SEED="${SEED:-0}"

export DATABASE_URL="sqlite:///${DB_FILE}"

db_stats() {
  python -c "
import os
os.environ['DATABASE_URL'] = '${DATABASE_URL}'
from app import app, db
from models import Customer, Elevator, User
import installation.models  # noqa
from installation.models import InstallProject, InstallLead
with app.app_context():
    print('  DB file:', app.config['SQLALCHEMY_DATABASE_URI'])
    print('  customers:', Customer.query.count())
    print('  elevators:', Elevator.query.count())
    print('  install_projects:', InstallProject.query.count())
    print('  install_leads:', InstallLead.query.count())
    print('  users:', User.query.count())
"
}

echo "==> تفريغ قاعدة بيانات جما"
echo "    مجلد: $JAMA_DIR"
echo "    ملف:  $DB_FILE"

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: مجلد جما غير موجود"
  exit 1
fi

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo ""
echo "==> قبل التفريغ:"
db_stats 2>/dev/null || echo "  (لا قاعدة بعد)"

# احذف liftcore.db القديم — كان يسبب قراءة قاعدة خاطئة
if [ -f "$JAMA_DIR/instance/liftcore.db" ]; then
  echo ""
  echo "==> حذف instance/liftcore.db (قاعدة خاطئة في مجلد جما)"
  cp "$JAMA_DIR/instance/liftcore.db" "$JAMA_DIR/instance/liftcore.db.bak.$(date +%Y%m%d%H%M%S)" 2>/dev/null || true
  rm -f "$JAMA_DIR/instance/liftcore.db"
fi
if [ -f "$JAMA_DIR/liftcore.db" ]; then
  rm -f "$JAMA_DIR/liftcore.db"
fi

if [ -f "$DB_FILE" ]; then
  cp "$DB_FILE" "${DB_FILE}.bak.$(date +%Y%m%d%H%M%S)"
fi

sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true

echo ""
echo "==> إعادة إنشاء jama.db فارغة"
rm -f "$DB_FILE"
mkdir -p "$(dirname "$DB_FILE")"
export DATABASE_URL="sqlite:///${DB_FILE}"
python init_db.py
python scripts/init_install_module.py

if [ "$SEED" = "1" ]; then
  echo "==> إضافة بيانات تجريبية (10 عملاء)"
  python scripts/reset_jama_demo.py || python seed_data.py --jama
fi

sudo systemctl start "$SERVICE_NAME"
sleep 2

echo ""
echo "==> بعد التفريغ:"
db_stats

echo ""
echo "=============================================="
echo "  تم — https://jama.liftcoreapp.com/login"
echo "  admin / admin123"
if [ "$SEED" = "0" ]; then
  echo "  القاعدة فارغة (بدون عملاء/مصاعد)"
  echo "  لبيانات تجريبية: SEED=1 bash deploy/reset_jama_db.sh"
  echo "  لاستيراد بيانات Excel: bash deploy/import_jama_all.sh"
fi
echo "=============================================="
