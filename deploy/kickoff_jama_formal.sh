#!/usr/bin/env bash
# بدء رسمي لفترة اختبار جما على السيرفر
# Usage (GCP SSH):
#   cd ~/liftcore/elevator-app && git pull --ff-only origin main
#   bash deploy/kickoff_jama_formal.sh
#   bash deploy/kickoff_jama_formal.sh --print-only
#   bash deploy/kickoff_jama_formal.sh --days 21
#   bash deploy/kickoff_jama_formal.sh --activate   # بعد انتهاء الاختبار وقرار Go-Live

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
SERVICE_NAME="${SERVICE_NAME:-liftcore}"

cd "$APP_DIR"

if [ -f "$PLATFORM_ENV" ]; then
  # shellcheck disable=SC1090
  set -a
  # shellcheck source=/dev/null
  source "$PLATFORM_ENV"
  set +a
  echo "==> محمّل: $PLATFORM_ENV"
else
  echo "WARN: لا يوجد $PLATFORM_ENV — سيُستخدم بيئة العملية الحالية"
fi

if [ -d "$APP_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$APP_DIR/.venv/bin/activate"
fi

echo "==> Kickoff جما الرسمي"
python scripts/kickoff_jama_formal.py "$@"

echo ""
echo "==> تحقق سريع"
curl -sS -o /dev/null -w "  https://jama.liftcoreapp.com/login → HTTP %{http_code}\n" \
  "https://jama.liftcoreapp.com/login" || true

echo ""
echo "بعد التسليم:"
echo "  1) أرسل HANDOVER + كلمات المرور عبر قناة آمنة"
echo "  2) افتح جدول الملاحظات FEEDBACK_TRACKER.csv"
echo "  3) غيّر/عطّل حساب admin التجريبي"
echo "  4) عند Go-Live: bash deploy/kickoff_jama_formal.sh --activate"
