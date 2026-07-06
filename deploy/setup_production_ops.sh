#!/usr/bin/env bash
# إغلاق النواقص التشغيلية — مرة واحدة على السيرفر
#   cd ~/liftcore/elevator-app && bash deploy/setup_production_ops.sh
#
# متغيرات:
#   INSTALL_AUTO_UPDATE=0   — لا تفعّل cron التحديث التلقائي
#   RUN_BACKUP_NOW=1        — نسخة احتياطية فورية (افتراضي: 1)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
INSTALL_AUTO_UPDATE="${INSTALL_AUTO_UPDATE:-1}"
RUN_BACKUP_NOW="${RUN_BACKUP_NOW:-1}"

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR not found"
  exit 1
fi

cd "$APP_DIR"
mkdir -p "$HOME/liftcore/logs" "$HOME/liftcore/backups"

echo "==> 1/5 platform.env (SECRET_KEY + HTTPS)"
bash "$SCRIPT_DIR/ensure_platform_env.sh"

echo ""
echo "==> 2/5 backup cron (يومي 02:30)"
bash "$SCRIPT_DIR/install_backup_cron.sh" "$APP_DIR"

if [ "$INSTALL_AUTO_UPDATE" = "1" ]; then
  echo ""
  echo "==> 3/5 auto-update cron (كل 5 دقائق)"
  bash "$SCRIPT_DIR/install_auto_update_cron.sh"
else
  echo ""
  echo "==> 3/5 auto-update cron — تخطي (INSTALL_AUTO_UPDATE=0)"
fi

if [ "$RUN_BACKUP_NOW" = "1" ]; then
  echo ""
  echo "==> 4/5 backup فوري"
  bash "$SCRIPT_DIR/backup_daily.sh" "$APP_DIR"
else
  echo ""
  echo "==> 4/5 backup فوري — تخطي"
fi

echo ""
echo "==> 5/5 فحص النواقص"
bash "$SCRIPT_DIR/check_production_ops.sh" "$APP_DIR"

echo ""
echo "==> تم إعداد التشغيل"
echo "    Sentry (اختياري): أضف SENTRY_DSN إلى /etc/liftcore/platform.env"
echo "    ثم: sudo systemctl restart liftcore"
echo "    تحقق: curl -s https://app.liftcoreapp.com/api/health | grep sentry"
