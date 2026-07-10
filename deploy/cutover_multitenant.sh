#!/usr/bin/env bash
# LiftCore — Cutover Multi-Tenant (إنتاج / staging)
#
# يشغّل على السيرفر فقط بعد git pull.
#
# مراحل:
#   0    checkpoint فقط
#   1    week1 بنية (checkpoint + postgres + فحوصات)
#   8    ترحيل SQLite → PostgreSQL (tenant default لـ app.liftcoreapp.com)
#   all  0+1 ثم 8 إن وُجد DATABASE_URL
#
# أمثلة:
#   bash deploy/cutover_multitenant.sh --phase 0
#   bash deploy/cutover_multitenant.sh --phase 1
#   export DATABASE_URL=postgresql://liftcore:PASS@127.0.0.1:5432/liftcore
#   bash deploy/cutover_multitenant.sh --phase 8 --dry-run
#   bash deploy/cutover_multitenant.sh --phase 8
#
# مهم: app.liftcoreapp.com يربط slug=default (ليس app — app في MARKETING_SLUGS).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_DIR"

PHASE="all"
DRY_RUN=0
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --phase)
      shift
      PHASE="${1:-}"
      [ -n "$PHASE" ] || { echo "ERROR: --phase needs 0|1|8|all" >&2; exit 1; }
      ;;
    --phase=*)
      PHASE="${1#--phase=}"
      ;;
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE=1 ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      echo "ERROR: unknown arg: $1" >&2
      exit 1
      ;;
  esac
  shift
done

TENANT_SLUG="${TENANT_SLUG:-default}"
TENANT_NAME="${TENANT_NAME:-LiftCore}"
SQLITE_SOURCE="${SQLITE_SOURCE:-$APP_DIR/instance/liftcore.db}"

_log() { echo ""; echo "==> $*"; }
_die() { echo "ERROR: $*" >&2; exit 1; }

_phase0() {
  _log "Phase 0 — checkpoint pre-multitenant"
  bash "$SCRIPT_DIR/checkpoint_pre_multitenant.sh"
}

_phase1() {
  _log "Phase 1 — week1 infrastructure"
  bash "$SCRIPT_DIR/week1_multitenant.sh"
}

_phase8() {
  _log "Phase 8 — migrate SQLite → tenant slug=$TENANT_SLUG"
  [ -f "$SQLITE_SOURCE" ] || _die "SQLite not found: $SQLITE_SOURCE"
  [ -n "${DATABASE_URL:-}" ] || _die "set DATABASE_URL before phase 8"

  export SQLITE_SOURCE TENANT_SLUG TENANT_NAME DATABASE_URL
  WEEK8_ARGS=()
  [ "$DRY_RUN" -eq 1 ] && WEEK8_ARGS+=(--dry-run)
  [ "$FORCE" -eq 1 ] && WEEK8_ARGS+=(--force)
  bash "$SCRIPT_DIR/week8_staging_cutover.sh" "${WEEK8_ARGS[@]}"
}

_manual_next() {
  cat <<EOF

==============================================
  Cutover — خطوات يدوية بعد السكربت
==============================================
  1) GCP Console: Disk Snapshot
  2) Cloud DNS: سجل A لـ *.liftcoreapp.com
  3) certbot DNS + : sudo certbot renew --dry-run
  4) /etc/liftcore/platform.env:
       DATABASE_URL=postgresql://...
       SECRET_KEY=<عشوائي قوي — إلزامي مع LIFTCORE_HTTPS=1>
       LIFTCORE_HTTPS=1
  5) sudo systemctl restart liftcore
  6) bash deploy/verify_deploy.sh https://app.liftcoreapp.com
  7) (اختياري) tenant jama demo:
       TENANT_SLUG=jama TENANT_NAME='جما — اختبار' \\
         SQLITE_SOURCE=/path/to/jama.db \\
         bash deploy/week8_staging_cutover.sh
     أو: seed_data داخل tenant jama
  8) أوقف liftcore-jama إن وُجدت بعد استقرار 72 ساعة
==============================================
EOF
}

case "$PHASE" in
  0) _phase0 ;;
  1) _phase1; _manual_next ;;
  8) _phase8; _manual_next ;;
  all)
    _phase0
    _phase1
    if [ -n "${DATABASE_URL:-}" ]; then
      _phase8
    else
      _log "Phase 8 skipped — set DATABASE_URL ثم: bash deploy/cutover_multitenant.sh --phase 8"
    fi
    _manual_next
    ;;
  *)
    _die "unknown phase: $PHASE (use 0|1|8|all)"
    ;;
esac

_log "Done (phase=$PHASE dry_run=$DRY_RUN)"
