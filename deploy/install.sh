#!/usr/bin/env bash
# LiftCore — نقطة دخول موحّدة (محلي + سيرفر)
#   bash deploy/install.sh help
#   bash deploy/install.sh local          # إعداد venv + اختبارات
#   bash deploy/install.sh test         # pytest + security audit
#   bash deploy/install.sh update       # تحديث سيرفر (gcp_update)
#   bash deploy/install.sh tenant NAME DIR
#   bash deploy/install.sh backup [APP_DIR]
#   bash deploy/install.sh verify URL

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CMD="${1:-help}"

usage() {
  cat <<'EOF'
LiftCore install.sh — أوامر:

  local       إعداد بيئة محلية (.venv + pip + اختبارات)
  test        pytest + security audit
  update      git pull + restart (سيرفر — يستدعي gcp_update.sh)
  tenant      تحديث tenant: install.sh tenant liftcore-jama ~/liftcore/jama-elevator-app
  backup      نسخة احتياطية لقاعدة البيانات
  backup-cron تفعيل cron يومي للنسخ الاحتياطي
  ops         إعداد تشغيلي كامل (backup + auto-update + فحص)
  ops-check   فحص النواقص التشغيلية على السيرفر
  verify      تحقق من نشر: install.sh verify https://jama.liftcoreapp.com
  checkpoint  حفظ نقطة رجوع قبل Multi-Tenant (قواعد + uploads + nginx)
  week1       أسبوع 1 Multi-Tenant: checkpoint + postgres + فحوصات
  hetzner     تعليمات نقل الإنتاج إلى Hetzner (bootstrap / export / import)
  help        هذه الرسالة

محلياً على Windows: run_local.bat
EOF
}

run_test() {
  cd "$ROOT"
  PYTHON="${PYTHON:-python3}"
  if [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON="$ROOT/.venv/bin/python"
  fi
  "$PYTHON" -m pip install -q -r requirements.txt
  "$PYTHON" scripts/security_audit.py
  "$PYTHON" -m pytest tests/ -q --tb=short
  echo "==> tests OK"
}

run_local() {
  cd "$ROOT"
  if [ ! -d .venv ]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -r requirements.txt
  run_test
  echo ""
  echo "==> جاهز محلياً:"
  echo "    source .venv/bin/activate && python app.py"
  echo "    أو: run_local.bat (Windows)"
}

case "$CMD" in
  help|-h|--help)
    usage
    ;;
  test)
    run_test
    ;;
  local)
    run_local
    ;;
  update)
    bash "$SCRIPT_DIR/gcp_update.sh"
    ;;
  tenant)
    bash "$SCRIPT_DIR/tenant_update.sh" "${2:?SERVICE_NAME}" "${3:?APP_DIR}"
    ;;
  backup)
    APP_DIR="${2:-$ROOT}"
    bash "$SCRIPT_DIR/backup_daily.sh" "$APP_DIR"
    ;;
  backup-cron)
    APP_DIR="${2:-$HOME/liftcore/elevator-app}"
    bash "$SCRIPT_DIR/install_backup_cron.sh" "$APP_DIR"
    ;;
  ops)
    APP_DIR="${2:-$HOME/liftcore/elevator-app}"
    APP_DIR="$APP_DIR" bash "$SCRIPT_DIR/setup_production_ops.sh"
    ;;
  ops-check)
    bash "$SCRIPT_DIR/check_production_ops.sh" "${2:-$HOME/liftcore/elevator-app}"
    ;;
  verify)
    bash "$SCRIPT_DIR/verify_deploy.sh" "${2:?BASE_URL}"
    ;;
  checkpoint)
    bash "$SCRIPT_DIR/checkpoint_pre_multitenant.sh"
    ;;
  week1)
    bash "$SCRIPT_DIR/week1_multitenant.sh"
    ;;
  hetzner)
    cat "$SCRIPT_DIR/hetzner/README.md"
    ;;
  *)
    echo "أمر غير معروف: $CMD"
    usage
    exit 1
    ;;
esac
