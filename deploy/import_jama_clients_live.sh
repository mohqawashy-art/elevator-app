#!/usr/bin/env bash
# استيراد عملاء جما من Excel إلى PostgreSQL (slug=jama)
#
# 1) من GCP Console SSH: Upload file → ارفع Jama-Clients-Import-Template.xlsx إلى /home/info/
# 2) ثم:
#    cd ~/liftcore/elevator-app && git pull --ff-only origin main
#    bash deploy/import_jama_clients_live.sh ~/Jama-Clients-Import-Template.xlsx
#
# أو بدون git pull إذا نسخت السكربت يدوياً:
#    bash deploy/import_jama_clients_live.sh ~/jama_clients.xlsx

set -euo pipefail

XLSX="${1:-$HOME/Jama-Clients-Import-Template.xlsx}"
APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"

cd "$APP_DIR"

if [ -f "$PLATFORM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$PLATFORM_ENV"
  set +a
fi

PY=""
for c in \
  "$APP_DIR/.venv/bin/python" \
  "$HOME/liftcore/jama-elevator-app/.venv/bin/python" \
  "$(command -v python3 2>/dev/null || true)"
do
  if [ -n "$c" ] && [ -x "$c" ]; then
    PY="$c"
    break
  fi
done

if [ -z "$PY" ]; then
  echo "ERROR: لا يوجد python"
  exit 1
fi

if [ ! -f "$XLSX" ]; then
  echo "ERROR: الملف غير موجود: $XLSX"
  echo "ارفعه من GCP SSH → Upload file إلى /home/info/"
  exit 1
fi

echo "==> Python: $PY"
echo "==> Excel:  $XLSX"
"$PY" -m pip install -q openpyxl

if [ ! -f scripts/import_clients_xlsx_tenant.py ]; then
  echo "ERROR: scripts/import_clients_xlsx_tenant.py غير موجود — نفّذ git pull أولاً"
  exit 1
fi

echo "==> معاينة"
"$PY" scripts/import_clients_xlsx_tenant.py "$XLSX" --slug jama --dry-run

echo "==> استيراد"
"$PY" scripts/import_clients_xlsx_tenant.py "$XLSX" --slug jama --yes

sudo systemctl restart liftcore
echo ""
echo "تم — https://jama.liftcoreapp.com/clients"
