#!/usr/bin/env bash
# إعادة ضبط admin + PIN الفنيين — بدون مسح البيانات
#   bash deploy/reset_passwords_now.sh
#   ADMIN_PASSWORD='MyPass123!' bash deploy/reset_passwords_now.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
VENV="$(lc_resolve_venv "$APP_DIR" liftcore)"

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR not found"
  exit 1
fi

cd "$APP_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

export ADMIN_PASSWORD="${ADMIN_PASSWORD:-LiftCore@2026}"
export FIELD_PIN="${FIELD_PIN:-123456}"

echo "==> LiftCore reset passwords (DB only — no data wipe)"
python scripts/reset_passwords.py --apply
