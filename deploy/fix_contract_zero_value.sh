#!/usr/bin/env bash
# تشخيص + إصلاح: السماح بحفظ العقد بقيمة 0 على جما
# الاستخدام على السيرفر:
#   bash deploy/fix_contract_zero_value.sh

set -euo pipefail

SERVICE="${SERVICE_NAME:-liftcore-jama}"
WD="$(sudo systemctl show "$SERVICE" -p WorkingDirectory --value 2>/dev/null || true)"
if [[ -z "$WD" || "$WD" == "/" ]]; then
  WD="${HOME}/liftcore/jama-elevator-app"
fi

echo "==> service: $SERVICE"
echo "==> WorkingDirectory: $WD"
echo "==> cwd now: $(pwd)"

if [[ ! -f "$WD/templates/contracts.html" ]]; then
  echo "ERROR: لا يوجد $WD/templates/contracts.html"
  exit 1
fi

echo "==> git in WD:"
git -C "$WD" log -1 --oneline 2>/dev/null || echo "(no git)"

ALERT='قيمة العقد يجب أن تكون أكبر من صفر'
HINT='contract-value-optional-hint'

echo "==> markers in $WD/templates/contracts.html"
if grep -q "$ALERT" "$WD/templates/contracts.html"; then
  echo "  ALERT_STRING: STILL_PRESENT (سيتم حذفه)"
else
  echo "  ALERT_STRING: gone"
fi
if grep -q "$HINT" "$WD/templates/contracts.html"; then
  echo "  ZERO_HINT: present"
else
  echo "  ZERO_HINT: MISSING"
fi

# مزامنة من GitHub إلى مجلد الخدمة الفعلي
if [[ -d "$WD/.git" ]]; then
  echo "==> sync $WD to origin/main"
  git -C "$WD" fetch origin main
  git -C "$WD" reset --hard origin/main
fi

# حذف أي بقايا للتحقق القديم إن وُجدت
python3 - <<PY
from pathlib import Path
import re
p = Path(r"$WD") / "templates" / "contracts.html"
t = p.read_text(encoding="utf-8")
alert = "قيمة العقد يجب أن تكون أكبر من صفر"
before = alert in t
# احذف كتلة التحقق القديمة إن بقيت
pat = re.compile(
    r"\s*var contractVal = parseFloat\([^;]*;\s*"
    r"if\s*\(\s*!contractVal\s*\|\|\s*contractVal\s*<=\s*0\s*\)\s*\{\s*"
    r"alert\(\s*['\"]قيمة العقد يجب أن تكون أكبر من صفر['\"]\s*\)\s*;\s*"
    r"return\s*;\s*\}\s*",
    re.M,
)
t2, n = pat.subn("\n", t)
# أزل أي alert متبقٍ بنفس النص
t2, n2 = re.subn(
    r"alert\(\s*['\"]قيمة العقد يجب أن تكون أكبر من صفر['\"]\s*\)\s*;?",
    "/* zero-value allowed */",
    t2,
)
if t2 != t:
    p.write_text(t2, encoding="utf-8")
print(f"  patched blocks={n} alerts={n2} had_alert_before={before}")
print(f"  alert_after={alert in p.read_text(encoding='utf-8')}")
PY

echo "==> restart $SERVICE"
sudo systemctl restart "$SERVICE"
sleep 2
sudo systemctl is-active "$SERVICE"

echo ""
echo "==> تحقق الآن في المتصفح:"
echo "  1) أغلق كل تبويبات jama.liftcoreapp.com"
echo "  2) افتح نافذة Incognito جديدة"
echo "  3) العقود → تعديل → يجب ظهور جملة ذهبية: اختياري — يمكن حفظ العقد بقيمة 0"
echo "  4) احفظ بـ 0"
echo ""
echo "إن ظهرت الرسالة القديمة: View Source وابحث عن: قيمة العقد يجب"
echo "إذا وجدتها فالصفحة ليست من $WD"
