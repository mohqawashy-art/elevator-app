#!/usr/bin/env bash
# استعادة نقطة حفظ من checkpoint_pre_multitenant.sh
#
#   bash deploy/restore_checkpoint.sh ~/liftcore/checkpoints/pre-multitenant-YYYYMMDD-HHMMSS
#
# متغيرات:
#   RESTORE_MAIN=1|0     استعادة التطبيق الرئيسي (افتراضي 1)
#   RESTORE_JAMA=1|0     استعادة جما (افتراضي 1)
#   RESTORE_UPLOADS=1|0  فك uploads (افتراضي 1)
#   DRY_RUN=1            عرض فقط بدون نسخ

set -euo pipefail

CHECKPOINT="${1:?usage: restore_checkpoint.sh CHECKPOINT_DIR}"

MAIN_APP="${MAIN_APP:-$HOME/liftcore/elevator-app}"
JAMA_APP="${JAMA_APP:-$HOME/liftcore/jama-elevator-app}"
RESTORE_MAIN="${RESTORE_MAIN:-1}"
RESTORE_JAMA="${RESTORE_JAMA:-1}"
RESTORE_UPLOADS="${RESTORE_UPLOADS:-1}"
DRY_RUN="${DRY_RUN:-0}"

if [ ! -d "$CHECKPOINT" ]; then
  echo "ERROR: checkpoint not found: $CHECKPOINT"
  exit 1
fi

_run() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] $*"
  else
    echo "==> $*"
    eval "$@"
  fi
}

echo "==> Restore from: $CHECKPOINT"
[ -f "$CHECKPOINT/MANIFEST.txt" ] && head -20 "$CHECKPOINT/MANIFEST.txt"
echo ""

if [ "$RESTORE_MAIN" = "1" ]; then
  for src in "$CHECKPOINT"/main-*.db; do
    [ -f "$src" ] || continue
    _run "sudo systemctl stop liftcore 2>/dev/null || true"
  mkdir -p "$MAIN_APP/instance"
  _run "cp '$src' '$MAIN_APP/instance/$(basename "$src" | sed 's/^main-//')'"
  _run "sudo systemctl start liftcore 2>/dev/null || true"
  done
  if [ "$RESTORE_UPLOADS" = "1" ] && [ -f "$CHECKPOINT/uploads-main.tar.gz" ]; then
    _run "tar -xzf '$CHECKPOINT/uploads-main.tar.gz' -C '$MAIN_APP/static'"
  fi
fi

if [ "$RESTORE_JAMA" = "1" ]; then
  for src in "$CHECKPOINT"/jama-*.db; do
    [ -f "$src" ] || continue
    _run "sudo systemctl stop liftcore-jama 2>/dev/null || true"
  mkdir -p "$JAMA_APP/instance"
  _run "cp '$src' '$JAMA_APP/instance/$(basename "$src" | sed 's/^jama-//')'"
  _run "sudo systemctl start liftcore-jama 2>/dev/null || true"
  done
  if [ "$RESTORE_UPLOADS" = "1" ] && [ -f "$CHECKPOINT/uploads-jama.tar.gz" ]; then
    _run "tar -xzf '$CHECKPOINT/uploads-jama.tar.gz' -C '$JAMA_APP/static'"
  fi
fi

echo ""
echo "==> Restore finished (DRY_RUN=$DRY_RUN)"
echo "    تحقق: bash deploy/verify_deploy.sh https://jama.liftcoreapp.com"
