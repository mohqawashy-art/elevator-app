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

# استخدم مفسّر venv مباشرة — على بعض السيرفرات لا يوجد أمر باسم python
# وقد يكون venv داخل jama-elevator-app فقط
PY=""
for candidate in \
  "$APP_DIR/.venv/bin/python" \
  "${JAMA_PY:-$HOME/liftcore/jama-elevator-app/.venv/bin/python}" \
  "$(command -v python3 2>/dev/null || true)" \
  "$(command -v python 2>/dev/null || true)"
do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: لا يوجد python — أنشئ venv في elevator-app أو استخدم jama-elevator-app/.venv"
  exit 1
fi

echo "==> Python: $PY"
echo "==> تفريغ مستأجر جما"
"$PY" scripts/wipe_tenant_data.py --slug jama "${EXTRA[@]}"

if [ "$DO_KICKOFF" = "1" ]; then
  echo ""
  echo "==> إعادة تجهيز المستخدمين واسم الشركة"
  "$PY" scripts/kickoff_jama_formal.py --days 21
fi

echo ""
echo "تحقق: https://jama.liftcoreapp.com/login"
