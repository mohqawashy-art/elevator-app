#!/usr/bin/env bash
# تصفير بوابة الفني (أعطال مفتوحة + زيارات نشطة) دون مسح بقية البيانات
#
#   cd ~/liftcore/jama-elevator-app && git pull
#   bash deploy/zero_field_portal.sh
#   bash deploy/zero_field_portal.sh app   # منصة app بدل jama

set -euo pipefail

SLUG="${1:-jama}"
APP_DIR="${APP_DIR:-$HOME/liftcore/${SLUG}-elevator-app}"
if [[ "$SLUG" == "app" ]]; then
  APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
fi
VENV="${VENV:-$APP_DIR/.venv}"
SERVICE="${SERVICE:-liftcore-${SLUG}}"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Missing app dir: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"
if [[ -f /etc/liftcore/platform.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/liftcore/platform.env
  set +a
fi

if [[ -f "$VENV/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

echo "==> Zero field portal ($SLUG)"
python3 scripts/zero_field_portal.py --slug "$SLUG" --dry-run

if [[ "${ZERO_FIELD_CONFIRM:-}" != "yes" ]]; then
  read -r -p "تنفيذ التصفير؟ [y/N] " ans
  if [[ "${ans,,}" != "y" ]]; then
    echo "أُلغي."
    exit 0
  fi
fi

python3 scripts/zero_field_portal.py --slug "$SLUG" --yes

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl restart "$SERVICE" 2>/dev/null || true
fi

echo "==> Done — https://${SLUG}.liftcoreapp.com/field/login"
