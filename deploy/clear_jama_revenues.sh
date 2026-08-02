#!/usr/bin/env bash
# مسح جميع إيرادات مستأجر جما (PostgreSQL على elevator-app)
# لا يوقف الخدمة (لتجنب 502) — الحذف آمن أثناء التشغيل.
#
#   cd ~/liftcore/elevator-app
#   bash deploy/clear_jama_revenues.sh --dry-run
#   bash deploy/clear_jama_revenues.sh --yes

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
SERVICE="${SERVICE:-liftcore}"
SLUG="${SLUG:-jama}"
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) EXTRA+=(--dry-run) ;;
    --yes) EXTRA+=(--yes) ;;
    --slug=*) SLUG="${arg#--slug=}" ;;
    *) EXTRA+=("$arg") ;;
  esac
done

cd "$APP_DIR"

if [ -f "$PLATFORM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$PLATFORM_ENV"
  set +a
  echo "==> محمّل: $PLATFORM_ENV"
else
  echo "WARN: لا يوجد $PLATFORM_ENV"
fi

if [ -d "$APP_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$APP_DIR/.venv/bin/activate"
elif [ -d "$HOME/liftcore/venv" ]; then
  # shellcheck disable=SC1091
  source "$HOME/liftcore/venv/bin/activate"
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL فارغ بعد تحميل $PLATFORM_ENV"
  echo "بدون هذا المتغير لن يُمسَح شيء من قاعدة جما الحية."
  exit 1
fi

echo "==> Clear revenues + receipt vouchers for slug=$SLUG"
echo "    App: $APP_DIR"
echo "    DATABASE_URL set: yes"

# لا نوقف الخدمة — الحذف أثناء التشغيل آمن
sudo systemctl start "$SERVICE" 2>/dev/null || true

python3 scripts/clear_jama_revenues.py --slug "$SLUG" "${EXTRA[@]}"
EXIT=$?

if [[ $EXIT -ne 0 ]]; then
  echo "ERROR: clear failed (exit $EXIT) — لم يُكتمل المسح"
  exit "$EXIT"
fi

echo ""
if [[ " ${EXTRA[*]} " == *" --dry-run "* ]]; then
  echo "معاينة فقط — لم يُحذف شيء"
  echo "للمسح الفعلي: bash deploy/clear_jama_revenues.sh --yes"
else
  echo "Done — تحقق:"
  echo "  https://jama.liftcoreapp.com/revenues"
  echo "  https://jama.liftcoreapp.com/invoices"
fi
