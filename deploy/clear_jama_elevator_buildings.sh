#!/usr/bin/env bash
# تفريغ عمود اسم المبنى لكل مصاعد jama (PostgreSQL متعدد المستأجرين)
#   cd ~/liftcore/elevator-app && bash deploy/clear_jama_elevator_buildings.sh --dry-run
#   cd ~/liftcore/elevator-app && bash deploy/clear_jama_elevator_buildings.sh --yes

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
VENV="${VENV:-$APP_DIR/.venv}"
PLATFORM_ENV="${PLATFORM_ENV:-/etc/liftcore/platform.env}"

cd "$APP_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
if [ -f "$PLATFORM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$PLATFORM_ENV"
  set +a
fi

ARGS=()
while [ $# -gt 0 ]; do
  ARGS+=("$1")
  shift
done

echo "==> Clear elevator building_name (slug=jama)"
python scripts/clear_tenant_elevator_buildings.py --slug jama "${ARGS[@]}"

if printf '%s\n' "${ARGS[@]}" | grep -qx -- '--yes'; then
  sudo systemctl restart liftcore 2>/dev/null || true
  echo "==> Done — https://jama.liftcoreapp.com/elevators"
fi
