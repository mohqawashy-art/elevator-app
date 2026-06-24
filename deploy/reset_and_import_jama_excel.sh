#!/usr/bin/env bash
# تفريغ جما ثم استيراد كل بيانات Excel (كامل البرنامج)
#
# 1) ارفع ملفات Excel إلى مجلد على السيرفر، مثلاً:
#    ~/liftcore/jama-elevator-app/deploy/data/jama_import/
#
# 2) أسماء الملفات يجب أن تحتوي على (أي جزء من الاسم):
#    العملاء | العقود | المصاعد | الفنيين | سجل الزيارات | المصروفات | إيرادات | بيان تركيب قطع الغيار
#
# 3) التنفيذ:
#    bash deploy/reset_and_import_jama_excel.sh --dry-run
#    bash deploy/reset_and_import_jama_excel.sh
#
# متغيرات:
#   JAMA_DIR      مجلد التطبيق
#   DATA_DIR      مجلد ملفات Excel
#   SKIP_RESET=1  استيراد بدون تفريغ (إضافة فوق الموجود — غير موصى به)

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
DATA_DIR="${DATA_DIR:-$JAMA_DIR/deploy/data/jama_import}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
DRY=0
SKIP_RESET="${SKIP_RESET:-0}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --skip-reset) SKIP_RESET=1 ;;
  esac
done

if [ ! -d "$JAMA_DIR" ]; then
  echo "ERROR: مجلد جما غير موجود: $JAMA_DIR"
  exit 1
fi

if [ ! -d "$DATA_DIR" ]; then
  echo "ERROR: مجلد البيانات غير موجود: $DATA_DIR"
  echo "أنشئه وارفع ملفات Excel:"
  echo "  mkdir -p $DATA_DIR"
  exit 1
fi

shopt -s nullglob
xlsx_count=$(find "$DATA_DIR" -maxdepth 1 -name '*.xlsx' ! -name '~$*' 2>/dev/null | wc -l)
if [ "$xlsx_count" -eq 0 ]; then
  echo "ERROR: لا توجد ملفات .xlsx في $DATA_DIR"
  exit 1
fi

echo "=============================================="
echo "  جما — تفريغ + استيراد Excel"
echo "  التطبيق: $JAMA_DIR"
echo "  البيانات: $DATA_DIR ($xlsx_count ملف)"
echo "  معاينة: $([ "$DRY" = "1" ] && echo نعم || echo لا)"
echo "=============================================="
echo ""
echo "ملفات Excel:"
find "$DATA_DIR" -maxdepth 1 -name '*.xlsx' ! -name '~$*' -printf '  - %f\n' 2>/dev/null || \
  ls -1 "$DATA_DIR"/*.xlsx 2>/dev/null | sed 's/^/  - /'

cd "$JAMA_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q openpyxl pandas

export DATABASE_URL="sqlite:///${DB_FILE}"

if [ "$DRY" = "1" ]; then
  echo ""
  echo "==> معاينة الملفات التي سيتم التعرف عليها"
  python - <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from import_real_data import find_excel_files
folder = os.environ.get("DATA_DIR", ".")
found = find_excel_files(folder)
if not found:
    print("ERROR: لم يُعثر على ملفات مطابقة. تأكد من أسماء الملفات.")
    sys.exit(1)
labels = {
    "customers": "العملاء",
    "contracts": "العقود",
    "elevators": "المصاعد",
    "technicians": "الفنيين",
    "visits": "سجل الزيارات",
    "expenses": "المصروفات",
    "revenues": "إيرادات",
    "spare_parts": "بيان تركيب قطع الغيار",
}
for key, path in found.items():
    print(f"  [{labels.get(key, key)}] {os.path.basename(path)}")
missing = set(labels) - set(found)
if missing:
    print("\nتحذير — ملفات غير موجودة (اختيارية):")
    for k in sorted(missing):
        print(f"  - {labels[k]}")
PY
  exit 0
fi

if [ "$SKIP_RESET" != "1" ]; then
  echo ""
  echo "==> تفريغ قاعدة جما"
  SEED=0 JAMA_DIR="$JAMA_DIR" bash "$JAMA_DIR/deploy/reset_jama_db.sh"
fi

echo ""
echo "==> استيراد البيانات من Excel"
export DATA_DIR
python - <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.environ.get('DB_FILE', 'instance/jama.db')}")
from app import app, db
from import_real_data import import_all, find_excel_files

folder = os.environ["DATA_DIR"]
with app.app_context():
    db.create_all()
    found = find_excel_files(folder)
    if not found:
        raise SystemExit(f"لم يُعثر على ملفات Excel مطابقة في: {folder}")
    stats = import_all(folder, reset=False)
    print("\nاكتمل الاستيراد:")
    labels = {
        "files_found": "ملفات",
        "customers": "عملاء",
        "contracts": "عقود",
        "elevators": "مصاعد",
        "technicians": "فنيون",
        "visits": "زيارات",
        "expenses": "مصروفات",
        "revenues": "إيرادات",
        "spare_parts": "قطع غيار",
    }
    for k, v in stats.items():
        print(f"  {labels.get(k, k)}: {v}")
PY

if [ -f "$JAMA_DIR/deploy/geocode_jama_clients.sh" ]; then
  echo ""
  echo "==> تحديد إحداثيات الخريطة للعملاء"
  bash "$JAMA_DIR/deploy/geocode_jama_clients.sh" || echo "WARN: geocode skipped"
fi

sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
sleep 2

echo ""
echo "=============================================="
echo "  تم — https://jama.liftcoreapp.com"
echo "  الدخول: admin / admin123"
echo "=============================================="
