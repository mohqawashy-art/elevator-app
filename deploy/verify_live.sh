#!/usr/bin/env bash
# فحص سريع — هل التحديث شغّال على السيرفر؟
#   cd ~/liftcore/elevator-app && bash deploy/verify_live.sh

set -euo pipefail

for try in "$HOME/liftcore/elevator-app" "/var/www/elevator-app"; do
  if [ -d "$try/.git" ]; then APP_DIR="$try"; break; fi
done
APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
cd "$APP_DIR"

echo "========== LiftCore — فحص التحديث =========="
echo ""
echo "1) آخر commit:"
git log -1 --oneline 2>/dev/null || echo "  (لا git)"
echo ""
echo "2) مجلد الموديول:"
test -d installation && echo "  installation/: موجود" || echo "  installation/: مفقود!"
test -f static/installation-execution.css && echo "  واجهة التنفيذ الجديدة: موجودة" || echo "  واجهة التنفيذ: قديمة"
grep -q pay_advance_pct installation/models.py 2>/dev/null && echo "  نسب الدفعات: موجودة" || echo "  نسب الدفعات: مفقودة"
echo ""
echo "3) متغيرات systemd:"
systemctl show liftcore -p Environment 2>/dev/null | tr ' ' '\n' | grep -E 'LIFTCORE_' || echo "  (تعذر قراءة systemd)"
echo ""
echo "4) API محلي (جرّب المنافذ):"
FOUND=0
for PORT in 5000 5001 8000; do
  OUT="$(curl -sS --max-time 3 "http://127.0.0.1:${PORT}/api/version" 2>/dev/null || true)"
  if [ -n "$OUT" ]; then
    echo "  :${PORT} => $OUT"
    FOUND=1
    break
  fi
done
if [ "$FOUND" = 0 ]; then
  echo "  لا رد من أي منفذ — الخدمة قد تكون متوقفة"
  echo "  شغّل: bash deploy/fix_502.sh"
fi
echo ""
echo "5) الموقع العام:"
curl -sS --max-time 5 "https://app.liftcoreapp.com/api/version" 2>/dev/null | head -c 400 || echo "  تعذر الوصول"
echo ""
echo "=========================================="
echo "إذا install_enabled: true — الموديول مفعّل."
echo "افتح بعد تسجيل الدخول:"
echo "  https://app.liftcoreapp.com/installation/"
echo "  https://app.liftcoreapp.com/dashboard  (قسم: تركيب تجريبي)"
echo "=========================================="
