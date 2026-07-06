#!/usr/bin/env bash
# LiftCore — تحديث على Google Cloud VM
# على السيرفر:
#   bash deploy/gcp_update.sh

set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

if [ -n "${APP_DIR:-}" ] && [ -d "$APP_DIR/.git" ]; then
  :
elif [ "$(basename "$SCRIPT_ROOT")" = "jama-elevator-app" ] && [ -d "$SCRIPT_ROOT/.git" ]; then
  APP_DIR="$SCRIPT_ROOT"
  SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
elif [ -d "$HOME/liftcore/elevator-app/.git" ]; then
  APP_DIR="$HOME/liftcore/elevator-app"
elif [ -d "/var/www/elevator-app/.git" ]; then
  APP_DIR="/var/www/elevator-app"
else
  APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
fi

SERVICE_NAME="${SERVICE_NAME:-liftcore}"
VENV="$(lc_resolve_venv "$APP_DIR" "$SERVICE_NAME")"

echo "==> LiftCore update in $APP_DIR (service: $SERVICE_NAME, venv: $VENV)"
cd "$APP_DIR"

echo "==> backup database"
for db in "$APP_DIR/instance/liftcore.db" "$APP_DIR/liftcore.db"; do
  if [ -f "$db" ]; then
    cp "$db" "${db}.bak.$(date +%Y%m%d%H%M%S)"
    echo "  backed up $db"
    break
  fi
done

echo "==> git pull (never reset --hard)"
git fetch origin main
git pull --ff-only origin main

if [ -x "$VENV/bin/python" ]; then
  echo "==> pip install ($VENV)"
  lc_pip_install_requirements "$VENV" "$APP_DIR"
else
  echo "ERROR: لا يوجد venv صالح — توقّع: $APP_DIR/.venv أو $HOME/liftcore/venv"
  exit 1
fi

echo "==> ensure platform env + HTTPS + install module (systemd drop-in)"
DROP_IN="/etc/systemd/system/${SERVICE_NAME}.service.d"
PLATFORM_ENV="/etc/liftcore/platform.env"
if [ -f "$APP_DIR/deploy/check_platform_env.sh" ]; then
  if ! bash "$APP_DIR/deploy/check_platform_env.sh"; then
    echo "ERROR: أصلح $PLATFORM_ENV قبل إعادة التشغيل (SECRET_KEY مطلوب مع LIFTCORE_HTTPS=1)"
    exit 1
  fi
fi
if command -v systemctl >/dev/null 2>&1; then
  sudo mkdir -p "$DROP_IN"
  printf '%s\n' '[Service]' 'Environment=LIFTCORE_HTTPS=1' | sudo tee "$DROP_IN/https.conf" >/dev/null
  printf '%s\n' '[Service]' 'Environment=LIFTCORE_INSTALL_MODULE=1' | sudo tee "$DROP_IN/install-module.conf" >/dev/null
  if [ -f "$PLATFORM_ENV" ]; then
    lc_fix_platform_env_perms "$PLATFORM_ENV"
    printf '%s\n' '[Service]' "EnvironmentFile=$PLATFORM_ENV" | sudo tee "$DROP_IN/platform-env.conf" >/dev/null
    echo "  platform env: $PLATFORM_ENV"
  elif [ -f "$APP_DIR/.env" ] && grep -q GOOGLE_MAPS_API_KEY "$APP_DIR/.env" 2>/dev/null; then
    grep '^GOOGLE_MAPS_API_KEY=' "$APP_DIR/.env" | sudo tee "$DROP_IN/maps-key.conf.tmp" >/dev/null
    {
      printf '%s\n' '[Service]'
      sudo sed 's/^/Environment=/' "$DROP_IN/maps-key.conf.tmp"
    } | sudo tee "$DROP_IN/maps-key.conf" >/dev/null
    sudo rm -f "$DROP_IN/maps-key.conf.tmp"
    echo "  maps key from $APP_DIR/.env (consider /etc/liftcore/platform.env for all tenants)"
  fi
  lc_write_version_dropin "$DROP_IN" "$APP_DIR"
  sudo systemctl daemon-reload
fi

if [ -x "$VENV/bin/python" ] && [ -f "$APP_DIR/deploy/migrate_db.py" ]; then
  echo "==> database migrations (Alembic)"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  python "$APP_DIR/deploy/migrate_db.py" || echo "  WARN: migrate_db failed"
fi

if [ -x "$VENV/bin/python" ] && [ -f "$APP_DIR/scripts/init_install_module.py" ]; then
  echo "==> installation module DB tables"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  python "$APP_DIR/scripts/init_install_module.py" || echo "  WARN: init_install_module failed"
fi

if [ -x "$VENV/bin/python" ]; then
  echo "==> test app import (production env)"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  export LIFTCORE_HTTPS=1
  if [ -f "$PLATFORM_ENV" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$PLATFORM_ENV"
    set +a
  fi
  if ! python -c "from app import app; print('  app import OK')" 2>&1; then
    echo "ERROR: التطبيق لا يشتغل — راجع: sudo journalctl -u $SERVICE_NAME -n 40 --no-pager"
    exit 1
  fi
fi

echo "==> restart service: $SERVICE_NAME"
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl restart "$SERVICE_NAME"
  sleep 3
  if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "ERROR: الخدمة متوقفة — شغّل: bash deploy/fix_502.sh"
    sudo journalctl -u "$SERVICE_NAME" -n 30 --no-pager || true
    exit 1
  fi
  echo "  service active OK"
elif command -v supervisorctl >/dev/null 2>&1; then
  sudo supervisorctl restart "$SERVICE_NAME" || sudo supervisorctl restart all
else
  echo "WARN: restart manually: sudo systemctl restart $SERVICE_NAME"
fi

echo "==> verify"
test -d "$APP_DIR/installation" && echo "  installation module OK"
grep -q "register_install_module" "$APP_DIR/app.py" && echo "  install routes OK"
test -f "$APP_DIR/static/liftcore-dates.js" && echo "  liftcore-dates.js OK"
if [ -x "$VENV/bin/python" ]; then
  python "$APP_DIR/scripts/build_clients_template.py" 2>/dev/null && echo "  clients import template OK" || true
  python "$APP_DIR/scripts/build_elevators_template.py" 2>/dev/null && echo "  elevators import template OK" || true
fi
test -f "$APP_DIR/templates/purchase-orders.html" && echo "  purchase-orders.html OK"
grep -q "purchase-orders" "$APP_DIR/app.py" && echo "  purchase-orders route OK"
test -f "$APP_DIR/templates/settings.html" && grep -q "settings_user_add" "$APP_DIR/app.py" && echo "  full settings UI OK"
test -f "$APP_DIR/static/liftcore-shell.css" && echo "  liftcore-shell.css OK"
grep -q "letter-box" "$APP_DIR/templates/purchase-order-print.html" && echo "  PO print v2 (invoice layout + e-sig) OK"
grep -q "sig_clear" "$APP_DIR/templates/purchase-order-print.html" && echo "  PO print v2.5 (clear btn + header + i18n) OK" || echo "  WARN: PO print v2.5 missing — run: git pull origin main"
grep -q "table-body" "$APP_DIR/templates/elevators.html" && ! grep -q "let filtered = ELEVATORS" "$APP_DIR/templates/elevators.html" && echo "  elevators table JS fix OK" || echo "  WARN: elevators table fix missing — run: git pull origin main"
grep -q "f-entity-type" "$APP_DIR/templates/clients.html" && echo "  client entity type + ID/CR fields OK" || echo "  WARN: client entity type UI missing — run: git pull origin main"
grep -q "address_en" "$APP_DIR/app.py" && echo "  PO bilingual address OK"
test -f "$APP_DIR/static/js/html2pdf.bundle.min.js" && echo "  html2pdf.js OK"

VERIFY_BASE="${VERIFY_BASE_URL:-}"
if [ -z "$VERIFY_BASE" ]; then
  case "$SERVICE_NAME" in
    liftcore-jama) VERIFY_BASE="https://jama.liftcoreapp.com" ;;
    *) VERIFY_BASE="https://app.liftcoreapp.com" ;;
  esac
fi
if [ -f "$APP_DIR/deploy/verify_deploy.sh" ]; then
  echo "==> HTTP verify ($VERIFY_BASE)"
  bash "$APP_DIR/deploy/verify_deploy.sh" "$VERIFY_BASE" || echo "  WARN: verify_deploy failed"
fi

echo ""
echo "==> Done — $VERIFY_BASE"
echo "    تحقق: /settings (تبويبات الشركة/المستخدمين/حسابي/المظهر)"
