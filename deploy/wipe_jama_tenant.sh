#!/usr/bin/env bash
# تفريغ بيانات مستأجر جما على PostgreSQL (Multi-Tenant) ثم اختياريًا إعادة kickoff
#
# Usage (GCP SSH):
#   cd ~/liftcore/elevator-app && git pull --ff-only origin main
#   bash deploy/wipe_jama_tenant.sh --confirm JAMA_WIPE
#   bash deploy/wipe_jama_tenant.sh --confirm JAMA_WIPE --kickoff
#   bash deploy/wipe_jama_tenant.sh --print-only
#
# ملاحظة: لا يمسّ app/default. للمستأجر jama فقط.

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"
DO_KICKOFF=0
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --kickoff) DO_KICKOFF=1 ;;
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
fi

if [ -d "$APP_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$APP_DIR/.venv/bin/activate"
fi

echo "==> تفريغ مستأجر جما"
python scripts/wipe_tenant_data.py --slug jama "${EXTRA[@]}"

if [ "$DO_KICKOFF" = "1" ]; then
  echo ""
  echo "==> إعادة تجهيز المستخدمين واسم الشركة"
  python scripts/kickoff_jama_formal.py --days 21
fi

echo ""
echo "تحقق: https://jama.liftcoreapp.com/login"
