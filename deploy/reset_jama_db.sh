#!/usr/bin/env bash
# تفريغ قاعدة بيانات جما وإعادة التهيئة
#   cd ~/liftcore/elevator-app && bash deploy/reset_jama_db.sh
#
# خيارات:
#   SEED=1      بيانات تجريبية بعد التفريغ (افتراضي)
#   SEED=0      قاعدة فارغة تماماً (admin فقط)
#   FULL=1      مسح كامل — حذف الملف وإعادة الإنشاء (يفقد إعدادات الشركة المخصصة)

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
SEED="${SEED:-1}"
FULL="${FULL:-0}"

echo "==> تفريغ قاعدة بيانات جما"
echo "    DB: $DB_FILE"

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: مجلد جما غير موجود — شغّل أولاً: bash deploy/provision_jama.sh"
  exit 1
fi

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
export DATABASE_URL="sqlite:///${DB_FILE}"

if [ -f "$DB_FILE" ]; then
  cp "$DB_FILE" "${DB_FILE}.bak.$(date +%Y%m%d%H%M%S)"
  echo "  نسخة احتياطية محفوظة"
fi

sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true

if [ "$FULL" = "1" ]; then
  echo "==> مسح كامل (ملف جديد)"
  rm -f "$DB_FILE"
  python init_db.py
  python scripts/init_install_module.py
  if [ "$SEED" = "1" ]; then
    python seed_data.py || true
  fi
else
  echo "==> مسح البيانات التشغيلية (يبقي المستخدمين والإعدادات)"
  python -c "
from app import app, db
import installation.models  # noqa
from seed_data import clear_business_data
from installation.models import (
    InstallTimelineStep, InstallQuotationLine, InstallQuotation,
    InstallProject, InstallLead,
)
with app.app_context():
    db.create_all()
    InstallTimelineStep.query.delete()
    InstallQuotationLine.query.delete()
    InstallQuotation.query.delete()
    InstallProject.query.delete()
    InstallLead.query.delete()
    clear_business_data()
    db.session.commit()
    print('[OK] operational data cleared')
"
  if [ "$SEED" = "1" ]; then
    python seed_data.py --reset || python seed_data.py || true
  fi
fi

sudo systemctl start "$SERVICE_NAME"
sleep 2
echo ""
echo "==> تم"
echo "  https://jama.liftcoreapp.com/login"
echo "  admin / admin123"
