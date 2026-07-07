#!/usr/bin/env bash
# LiftCore — أسبوع 1 Multi-Tenant (بنية تحتية)
# شغّل على السيرفر بعد: git pull origin main
#
#   cd ~/liftcore/elevator-app && bash deploy/week1_multitenant.sh
#
# متغيرات:
#   SKIP_CHECKPOINT=1     تخطي نقطة الحفظ
#   SKIP_POSTGRES=1       تخطي تثبيت PostgreSQL
#   RUN_POSTGRES_BACKUP=0  نسخة pg فقط إن DATABASE_URL مضبوط

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
SKIP_CHECKPOINT="${SKIP_CHECKPOINT:-0}"
SKIP_POSTGRES="${SKIP_POSTGRES:-0}"
RUN_POSTGRES_BACKUP="${RUN_POSTGRES_BACKUP:-0}"

cd "$APP_DIR"

echo "=============================================="
echo "  LiftCore — Week 1 Multi-Tenant"
echo "  $(date)"
echo "=============================================="

echo ""
echo "==> A) Git version"
git log -1 --oneline 2>/dev/null || echo "  (not a git repo)"

if [ "$SKIP_CHECKPOINT" != "1" ]; then
  echo ""
  echo "==> B) Checkpoint (pre-multitenant)"
  bash "$SCRIPT_DIR/checkpoint_pre_multitenant.sh"
else
  echo ""
  echo "==> B) Checkpoint — skipped (SKIP_CHECKPOINT=1)"
fi

echo ""
echo "==> C) Platform env check"
bash "$SCRIPT_DIR/check_platform_env.sh" || true

echo ""
echo "==> D) Production ops check"
bash "$SCRIPT_DIR/check_production_ops.sh" "$APP_DIR" || true

if [ "$SKIP_POSTGRES" != "1" ]; then
  echo ""
  echo "==> E) PostgreSQL setup"
  bash "$SCRIPT_DIR/setup_postgres.sh"
else
  echo ""
  echo "==> E) PostgreSQL — skipped (SKIP_POSTGRES=1)"
fi

if [ "$RUN_POSTGRES_BACKUP" = "1" ]; then
  echo ""
  echo "==> F) PostgreSQL backup test"
  bash "$SCRIPT_DIR/backup_postgres.sh" "$APP_DIR"
else
  echo ""
  echo "==> F) PostgreSQL backup — skipped (set RUN_POSTGRES_BACKUP=1 after DATABASE_URL)"
fi

echo ""
echo "=============================================="
echo "  Week 1 automated steps done."
echo ""
echo "  YOU must do manually (see docs/MULTI-TENANT.md):"
echo "    1) GCP Disk Snapshot (Console)"
echo "    2) Migrate DNS to Google Cloud DNS + wildcard A"
echo "    3) certbot --dns-google + certbot renew --dry-run"
echo "    4) Add DATABASE_URL to platform.env (do NOT restart prod app yet)"
echo "    5) PostgreSQL on your dev PC"
echo "=============================================="
